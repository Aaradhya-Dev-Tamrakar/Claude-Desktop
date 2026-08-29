from __future__ import annotations

from datetime import datetime, timezone, timedelta
import aiosqlite

from server.core.config import settings

async def run_supervisor_cycle() -> dict[str, int]:
    """
    Periodic self-healing supervisor loop:
    1. Identifies workers with stale heartbeats (> 120s) and marks them 'offline'.
    2. Reclaims any 'claimed' tasks held by offline workers, resetting them to 'pending'.
    3. Resets expired cooldown timers on workers.
    """
    now = datetime.now(timezone.utc)
    stale_threshold = (now - timedelta(seconds=settings.HEARTBEAT_TIMEOUT_SECONDS)).strftime("%Y-%m-%dT%H:%M:%SZ")
    now_iso = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    reclaimed_tasks = 0
    offline_workers = 0
    uncooled_workers = 0

    async with aiosqlite.connect(str(settings.DATABASE_PATH)) as db:
        db.row_factory = aiosqlite.Row

        # 1. Reset expired cooldowns
        cursor = await db.execute(
            "SELECT id FROM workers WHERE cooldown_until IS NOT NULL AND cooldown_until <= ?",
            (now_iso,)
        )
        expired_cooldowns = await cursor.fetchall()
        for w in expired_cooldowns:
            await db.execute(
                "UPDATE workers SET status = 'idle', cooldown_until = NULL, quota_used_current = 0 WHERE id = ?",
                (w["id"],)
            )
            uncooled_workers += 1

        # 2. Identify stale active workers (last_heartbeat < stale_threshold)
        cursor = await db.execute(
            "SELECT id FROM workers WHERE status IN ('idle', 'busy') AND (last_heartbeat IS NULL OR last_heartbeat < ?)",
            (stale_threshold,)
        )
        stale_workers = await cursor.fetchall()
        for w in stale_workers:
            worker_id = w["id"]
            await db.execute("UPDATE workers SET status = 'offline' WHERE id = ?", (worker_id,))
            offline_workers += 1

            # 3. Recover tasks claimed by this dead worker
            task_cursor = await db.execute(
                "SELECT id FROM tasks WHERE owner_worker_id = ? AND status = 'claimed'",
                (worker_id,)
            )
            orphaned_tasks = await task_cursor.fetchall()
            for t in orphaned_tasks:
                task_id = t["id"]
                await db.execute(
                    """
                    UPDATE tasks 
                    SET status = 'pending', owner_worker_id = NULL, claimed_at = NULL, updated_at = ?
                    WHERE id = ?
                    """,
                    (now_iso, task_id)
                )
                await db.execute(
                    "UPDATE task_attempts SET status = 'timeout', finished_at = ? WHERE task_id = ? AND worker_id = ? AND status = 'running'",
                    (now_iso, task_id, worker_id)
                )
                reclaimed_tasks += 1

        await db.commit()

    return {
        "reclaimed_tasks": reclaimed_tasks,
        "offline_workers": offline_workers,
        "uncooled_workers": uncooled_workers
    }
