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

    @staticmethod
    def is_stage_compatible(stage: str, caps: list[str]) -> bool:
        """Check if worker capabilities satisfy a task stage."""
        if "all" in caps or stage in caps:
            return True
        if stage == "draft" and "writing" in caps:
            return True
        if stage == "seo_optimize" and ("seo" in caps or "writing" in caps):
            return True
        if stage in ("format", "formatting", "markdown", "schema") and ("formatting" in caps or "writing" in caps or "code" in caps):
            return True
        if stage in ("qa", "qa_review", "audit") and ("qa" in caps or "qa_review" in caps or "audit" in caps or "review" in caps):
            return True
        return False

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
            if not self.is_stage_compatible(stage, caps):
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

    async def acquire_task_for_worker(
        self,
        worker_id: str,
        db: aiosqlite.Connection,
        capabilities: list[str] | None = None,
        lease_seconds: int | None = None,
    ) -> dict[str, Any] | None:
        """
        Pull-with-Scheduler-Arbitration (INV-WSR-002 Invariant A).
        Atomically inspects candidate tasks matching worker's capabilities, assigns, leases,
        and returns the claimed task with claim_token in a single atomic database transition.
        """
        from server.core.config import settings

        now = datetime.now(timezone.utc)
        now_iso = now.strftime("%Y-%m-%dT%H:%M:%SZ")
        lease_sec = max(1, min(lease_seconds or self.default_lease_seconds, 3600))
        lease_exp_iso = (now + timedelta(seconds=lease_sec)).strftime("%Y-%m-%dT%H:%M:%SZ")

        # 1. Fetch worker state and capabilities
        w_cursor = await db.execute("SELECT * FROM workers WHERE id = ?", (worker_id,))
        worker = await w_cursor.fetchone()
        if not worker:
            return None
        if worker["status"] == "offline":
            return None
        if worker["cooldown_until"] and worker["cooldown_until"] > now_iso:
            return None
        if (worker["quota_used_current"] or 0) >= (worker["quota_limit_per_window"] or 50):
            return None

        caps = capabilities if capabilities is not None else json.loads(worker["capabilities"])

        # 2. Find eligible candidate tasks:
        # First priority: tasks already assigned to this worker whose lease expired or needs pickup
        # Second priority: pending or expired tasks ordered by priority, created_at
        candidate_cursor = await db.execute(
            """
            SELECT * FROM tasks 
            WHERE (status = 'pending' OR (status = 'claimed' AND lease_expires_at IS NOT NULL AND lease_expires_at < ?))
            ORDER BY 
                CASE WHEN owner_worker_id = ? THEN 0 ELSE 1 END,
                priority ASC, 
                created_at ASC
            LIMIT 50
            """,
            (now_iso, worker_id)
        )
        candidate_tasks = await candidate_cursor.fetchall()

        for t in candidate_tasks:
            stage = t["stage"]
            if not self.is_stage_compatible(stage, caps):
                continue

            task_id = t["id"]
            claim_token = str(uuid.uuid4())

            # Atomic compare-and-swap lease claim
            update_cursor = await db.execute(
                """
                UPDATE tasks 
                SET status = 'claimed', owner_worker_id = ?, claimed_at = ?, lease_expires_at = ?, claim_token = ?, updated_at = ?
                WHERE id = ? AND (status = 'pending' OR (status = 'claimed' AND lease_expires_at IS NOT NULL AND lease_expires_at <= ?))
                """,
                (worker_id, now_iso, lease_exp_iso, claim_token, now_iso, task_id, now_iso)
            )
            if update_cursor.rowcount == 0:
                continue  # Lost race to another worker, check next candidate

            # Check attempt limit
            attempt_cursor = await db.execute("SELECT COUNT(*) FROM task_attempts WHERE task_id = ?", (task_id,))
            attempt_num = (await attempt_cursor.fetchone())[0] + 1
            if attempt_num > settings.MAX_TASK_ATTEMPTS:
                await db.execute(
                    "UPDATE tasks SET status = 'failed', owner_worker_id = NULL, claim_token = NULL, lease_expires_at = NULL, updated_at = ? WHERE id = ?",
                    (now_iso, task_id),
                )
                await db.commit()
                continue

            # Record attempt
            await db.execute(
                "INSERT INTO task_attempts (task_id, worker_id, attempt_number, status, started_at) VALUES (?, ?, ?, 'running', ?)",
                (task_id, worker_id, attempt_num, now_iso)
            )

            # Update worker status to busy and update heartbeat
            await db.execute("UPDATE workers SET status = 'busy', last_heartbeat = ? WHERE id = ?", (now_iso, worker_id))
            await db.commit()

            # Retrieve full task
            task_cursor = await db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
            claimed_row = await task_cursor.fetchone()

            return {
                "task": dict(claimed_row),
                "claim_token": claim_token,
                "lease_expires_at": lease_exp_iso,
            }

        return None

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

