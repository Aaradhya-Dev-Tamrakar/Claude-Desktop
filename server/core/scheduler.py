from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
import uuid
import aiosqlite

class QuotaAwareScheduler:
    """
    Evaluates pending tasks against registered workers using:
    Score(W) = w1 * Preference(W, C) + w2 * (1 - QuotaUsed/QuotaLimit) - w3 * ActiveTasks
    Filters out offline, cooldown, and capability-mismatched workers.
    Acquires race-safe atomic leases.
    """
    
    def __init__(
        self,
        w_capability: float = 0.5,
        w_quota: float = 0.3,
        w_concurrency: float = 0.2,
        w_provider_tier: float = 0.25,
        default_lease_seconds: int = 300,
        provider_tier_weights: dict[str, float] | None = None,
    ):
        self.w_capability = w_capability
        self.w_quota = w_quota
        self.w_concurrency = w_concurrency
        self.w_provider_tier = w_provider_tier
        self.default_lease_seconds = default_lease_seconds
        # Primary tier (Claude Desktop CDP) gets higher default weight;
        # Secondary tier (Copilot Headless / Free REST) provides zero-cost overflow capacity
        self.provider_tier_weights = provider_tier_weights or {
            "claude_desktop_cdp": 1.0,
            "claude_desktop": 1.0,
            "copilot_headless": 0.7,
            "gemini_free": 0.6,
            "groq": 0.5,
            "ollama_local": 0.4,
        }

    async def select_best_worker_for_task(self, task_id: str, db: aiosqlite.Connection) -> str | None:
        """Find the optimal worker ID to claim a given pending task or expired lease."""
        now = datetime.now(timezone.utc)
        now_iso = now.strftime("%Y-%m-%dT%H:%M:%SZ")

        # 1. Fetch task details (must be pending or have expired lease)
        cursor = await db.execute(
            """
            SELECT * FROM tasks 
            WHERE id = ? AND (status = 'pending' OR (status = 'claimed' AND lease_expires_at IS NOT NULL AND lease_expires_at < ?))
            """,
            (task_id, now_iso)
        )
        task = await cursor.fetchone()
        if not task:
            return None

        stage = task["stage"]

        # 2. Fetch candidate workers (status = 'idle' or 'busy', NOT in cooldown)
        worker_cursor = await db.execute(
            """
            SELECT * FROM workers 
            WHERE status != 'offline'
              AND (cooldown_until IS NULL OR cooldown_until <= ?)
              AND quota_used_current < quota_limit_per_window
            """,
            (now_iso,)
        )
        candidates = await worker_cursor.fetchall()
        if not candidates:
            return None

        best_worker_id = None
        best_score = -999.0

        for w in candidates:
            caps = json.loads(w["capabilities"])
            # Check capability match
            matched = False
            if stage in caps:
                matched = True
            elif stage == "draft" and "writing" in caps:
                matched = True
            elif stage == "seo_optimize" and ("seo" in caps or "writing" in caps):
                matched = True
            elif stage == "format" and ("formatting" in caps or "writing" in caps or "code" in caps):
                matched = True

            if not matched:
                continue

            # Compute headroom ratio (0.0 to 1.0)
            limit = w["quota_limit_per_window"] or 1
            used = w["quota_used_current"] or 0
            headroom = max(0.0, 1.0 - (used / limit))

            # Active tasks count (only active unexpired claims)
            act_cursor = await db.execute(
                """
                SELECT COUNT(*) FROM tasks 
                WHERE owner_worker_id = ? AND status = 'claimed' 
                  AND (lease_expires_at IS NULL OR lease_expires_at >= ?)
                """,
                (w["id"], now_iso)
            )
            active_count = (await act_cursor.fetchone())[0]

            # Provider tier preference (Claude primary, Copilot zero-GUI overflow, etc.)
            provider_type = w["provider"]
            tier_weight = self.provider_tier_weights.get(provider_type, 0.5)

            # Stage affinity bonus:
            # - Heavy reasoning / review (qa, audit) prefers primary CDP instances
            # - Repetitive grunt stages (format, overflow) perform excellently on copilot_headless
            affinity_bonus = 0.0
            if stage in ("qa", "qa_review", "audit") and "claude" in provider_type:
                affinity_bonus = 0.2
            elif stage in ("format", "formatting", "markdown", "schema", "overflow") and "copilot" in provider_type:
                affinity_bonus = 0.15

            score = (
                self.w_capability * 1.0 +
                self.w_quota * headroom +
                self.w_provider_tier * (tier_weight + affinity_bonus) -
                self.w_concurrency * active_count
            )

            if score > best_score:
                best_score = score
                best_worker_id = w["id"]

        return best_worker_id

    async def schedule_next_pending_tasks(self, db: aiosqlite.Connection, limit: int = 10, lease_seconds: int | None = None) -> list[dict[str, str]]:
        """Find pending tasks (or expired leases) and auto-assign to best available workers atomically."""
        lease_sec = lease_seconds or self.default_lease_seconds
        now = datetime.now(timezone.utc)
        now_iso = now.strftime("%Y-%m-%dT%H:%M:%SZ")
        lease_exp_iso = (now + timedelta(seconds=lease_sec)).strftime("%Y-%m-%dT%H:%M:%SZ")

        cursor = await db.execute(
            """
            SELECT id FROM tasks 
            WHERE status = 'pending' OR (status = 'claimed' AND lease_expires_at IS NOT NULL AND lease_expires_at < ?)
            ORDER BY priority ASC, created_at ASC 
            LIMIT ?
            """,
            (now_iso, limit)
        )
        pending_tasks = await cursor.fetchall()
        assignments = []

        for t in pending_tasks:
            task_id = t["id"]
            best_worker_id = await self.select_best_worker_for_task(task_id, db)
            if best_worker_id:
                claim_token = str(uuid.uuid4())
                # Perform atomic claim using compare-and-swap
                update_cursor = await db.execute(
                    """
                    UPDATE tasks 
                    SET status = 'claimed', owner_worker_id = ?, claimed_at = ?, lease_expires_at = ?, claim_token = ?, updated_at = ?
                    WHERE id = ? AND (status = 'pending' OR (status = 'claimed' AND lease_expires_at IS NOT NULL AND lease_expires_at < ?))
                    """,
                    (best_worker_id, now_iso, lease_exp_iso, claim_token, now_iso, task_id, now_iso)
                )
                if update_cursor.rowcount == 1:
                    await db.execute(
                        "UPDATE workers SET status = 'busy', last_heartbeat = ? WHERE id = ?",
                        (now_iso, best_worker_id)
                    )
                    assignments.append({"task_id": task_id, "worker_id": best_worker_id, "claim_token": claim_token})

        if assignments:
            await db.commit()

        return assignments

scheduler = QuotaAwareScheduler()

