from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
import aiosqlite

from server.core.config import settings

def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

class PipelineEngine:
    """
    Decomposes intake jobs into discrete, pipeline-staged tasks and manages
    stage advancement as tasks complete and pass QA.
    """

    @staticmethod
    def load_sku_template(sku_id: str) -> dict | None:
        """Load SKU definition JSON from sku-templates directory."""
        template_file = settings.SKU_TEMPLATES_DIR / f"{sku_id}.json"
        if not template_file.exists():
            return None
        return json.loads(template_file.read_text(encoding="utf-8"))

    @staticmethod
    async def decompose_job_into_tasks(
        job_id: str,
        items: list[dict],
        db: aiosqlite.Connection
    ) -> list[str]:
        """
        Takes a job and a list of parsed input items (e.g. from CSV/JSON).
        Creates Stage 1 (e.g. 'research' or 'draft') tasks for each item.
        """
        cursor = await db.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
        job = await cursor.fetchone()
        if not job:
            raise ValueError(f"Job '{job_id}' not found")

        pipeline = json.loads(job["pipeline"])
        if not pipeline:
            raise ValueError(f"Job '{job_id}' has empty pipeline")

        first_stage = pipeline[0]
        now = _now_iso()
        created_task_ids = []

        for idx, item in enumerate(items, start=1):
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            task_id = f"task_{today}_{job_id}_{first_stage}_{idx:03d}"
            
            spec = (
                f"Job: {job_id} | Stage 1 ({first_stage}) for Item #{idx}\n"
                f"Input Data: {json.dumps(item, ensure_ascii=False)}\n"
                f"Quality Rules: {job['quality_rules']}"
            )

            await db.execute(
                """
                INSERT OR REPLACE INTO tasks (id, job_id, stage, stage_order, kind, spec, status, priority, created_at, updated_at)
                VALUES (?, ?, ?, 1, 'text', ?, 'pending', 5, ?, ?)
                """,
                (task_id, job_id, first_stage, spec, now, now)
            )
            created_task_ids.append(task_id)

        # Update job status to 'running'
        await db.execute("UPDATE jobs SET status = 'running', updated_at = ? WHERE id = ?", (now, job_id))
        await db.commit()

        return created_task_ids

    @staticmethod
    async def advance_task_to_next_stage(
        completed_task_id: str,
        db: aiosqlite.Connection
    ) -> str | None:
        """
        When a task is verified (or passes QA), triggers generation of the next stage task
        using the previous stage checkpoint result_text as input.
        """
        cursor = await db.execute("SELECT * FROM tasks WHERE id = ?", (completed_task_id,))
        curr_task = await cursor.fetchone()
        if not curr_task or not curr_task["job_id"]:
            return None

        job_id = curr_task["job_id"]
        job_cursor = await db.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
        job = await job_cursor.fetchone()
        if not job:
            return None

        pipeline = json.loads(job["pipeline"])
        curr_stage_idx = curr_task["stage_order"] - 1 # 0-indexed
        
        # Check if there is a next stage
        if curr_stage_idx + 1 >= len(pipeline):
            # Final stage completed! Check if all tasks in job are done
            return None

        next_stage = pipeline[curr_stage_idx + 1]
        next_stage_order = curr_stage_idx + 2

        # Fetch checkpoint result from prior stage
        cp_cursor = await db.execute("SELECT result_text, summary FROM checkpoints WHERE task_id = ?", (completed_task_id,))
        cp = await cp_cursor.fetchone()
        prior_output = cp["result_text"] if cp else ""

        now = _now_iso()
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        next_task_id = f"task_{today}_{job_id}_{next_stage}_{completed_task_id.split('_')[-1]}"

        next_spec = (
            f"Job: {job_id} | Stage {next_stage_order} ({next_stage})\n"
            f"Prior Stage Output ({curr_task['stage']}):\n{prior_output}\n"
            f"Quality Rules: {job['quality_rules']}"
        )

        await db.execute(
            """
            INSERT OR REPLACE INTO tasks (id, job_id, parent_id, stage, stage_order, kind, spec, status, priority, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, 'text', ?, 'pending', 5, ?, ?)
            """,
            (next_task_id, job_id, completed_task_id, next_stage, next_stage_order, next_spec, now, now)
        )
        await db.commit()

        return next_task_id

    @staticmethod
    async def check_and_finalize_job(
        job_id: str,
        db: aiosqlite.Connection
    ) -> bool:
        """
        Checks whether all tasks for a job have reached terminal state (done/merged).
        If all stages are complete, aggregates deliverables and marks job 'completed'.
        """
        now = _now_iso()
        cursor = await db.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
        job = await cursor.fetchone()
        if not job:
            return False

        # Count active non-terminal tasks
        active_cursor = await db.execute(
            """
            SELECT COUNT(*) FROM tasks 
            WHERE job_id = ? AND status IN ('pending', 'claimed', 'blocked')
            """,
            (job_id,)
        )
        active_count = (await active_cursor.fetchone())[0]
        if active_count > 0:
            return False

        # Check total tasks
        total_cursor = await db.execute("SELECT COUNT(*) FROM tasks WHERE job_id = ?", (job_id,))
        total_count = (await total_cursor.fetchone())[0]
        if total_count == 0:
            return False

        # Verify final stage tasks are done or merged
        pipeline = json.loads(job["pipeline"])
        final_stage = pipeline[-1]
        final_stage_order = len(pipeline)

        final_tasks_cursor = await db.execute(
            """
            SELECT id, status FROM tasks 
            WHERE job_id = ? AND stage = ? AND stage_order = ?
            """,
            (job_id, final_stage, final_stage_order)
        )
        final_tasks = await final_tasks_cursor.fetchall()
        if not final_tasks or any(t["status"] not in ("done", "merged") for t in final_tasks):
            return False

        # Mark job as completed
        await db.execute(
            "UPDATE jobs SET status = 'completed', updated_at = ? WHERE id = ?",
            (now, job_id)
        )

        # Update metrics
        completed_cursor = await db.execute(
            "SELECT COUNT(*) FROM tasks WHERE job_id = ? AND status IN ('done', 'merged')",
            (job_id,)
        )
        completed_count = (await completed_cursor.fetchone())[0]

        await db.execute(
            """
            UPDATE job_metrics 
            SET total_tasks = ?, completed_tasks = ?, finished_at = ?
            WHERE job_id = ?
            """,
            (total_count, completed_count, now, job_id)
        )
        await db.commit()
        return True

pipeline_engine = PipelineEngine()

