from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, cast

import aiosqlite
from mcp.server.mcpserver import MCPServer

from server.core.config import settings
from server.core.database import get_db_conn
from server.core.pipeline_engine import pipeline_engine

mcp_server = MCPServer(
    name="remote-orchestrator",
    description=(
        "Hosted Remote Orchestration & Shared Context MCP server for Claude Desktop profiles. "
        "Provides cross-profile coordination, distributed task execution, SKU pipelines, "
        "shared team memory, and durable project context over HTTPS/SSE."
    ),
)

def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def _row_to_dict(row: aiosqlite.Row | None) -> dict[str, Any]:
    if row is None:
        return {}
    return {k: row[k] for k in row.keys()}

# =====================================================================
# 1. TASK MANAGEMENT TOOLS
# =====================================================================

@mcp_server.tool(
    name="create_task",
    description="Create a new task in the cloud orchestrator queue."
)
async def create_task(
    spec: str,
    stage: str = "research",
    kind: str = "text",
    priority: int = 5,
    job_id: str | None = None,
    parent_id: str | None = None,
    task_id: str | None = None,
) -> dict[str, Any]:
    db = await get_db_conn()
    try:
        if not task_id:
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            cursor = await db.execute("SELECT COUNT(*) FROM tasks WHERE id LIKE ?", (f"task_{today}_%",))
            count = (await cursor.fetchone())[0]
            task_id = f"task_{today}_{count + 1:03d}"

        now = _now_iso()
        await db.execute(
            """
            INSERT INTO tasks (id, job_id, parent_id, stage, stage_order, kind, spec, status, priority, created_at, updated_at)
            VALUES (?, ?, ?, ?, 1, ?, ?, 'pending', ?, ?, ?)
            """,
            (task_id, job_id, parent_id, stage, kind, spec, priority, now, now)
        )
        await db.commit()

        cursor = await db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        row = await cursor.fetchone()
        return _row_to_dict(row)
    finally:
        await db.close()

@mcp_server.tool(
    name="list_tasks",
    description="List tasks in the orchestrator, optionally filtered by status, stage, or job_id."
)
async def list_tasks(
    status: str | None = None,
    stage: str | None = None,
    job_id: str | None = None,
    parent_id: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    db = await get_db_conn()
    try:
        query = "SELECT * FROM tasks WHERE 1=1"
        params: list[Any] = []
        if status:
            query += " AND status = ?"
            params.append(status)
        if stage:
            query += " AND stage = ?"
            params.append(stage)
        if job_id:
            query += " AND job_id = ?"
            params.append(job_id)
        if parent_id:
            query += " AND parent_id = ?"
            params.append(parent_id)

        query += " ORDER BY priority ASC, created_at ASC LIMIT ?"
        params.append(max(1, min(limit, 200)))

        cursor = await db.execute(query, tuple(params))
        rows = await cursor.fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        await db.close()

@mcp_server.tool(
    name="get_task",
    description="Fetch full details for a single task by task_id."
)
async def get_task(task_id: str) -> dict[str, Any]:
    db = await get_db_conn()
    try:
        cursor = await db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        row = await cursor.fetchone()
        if not row:
            return {"error": f"Task '{task_id}' not found"}
        return _row_to_dict(row)
    finally:
        await db.close()

@mcp_server.tool(
    name="claim_task",
    description="Claim a pending or expired task with an atomic lease duration."
)
async def claim_task(
    task_id: str,
    worker_id: str,
    lease_seconds: int = 300,
    branch_name: str | None = None,
) -> dict[str, Any]:
    db = await get_db_conn()
    try:
        now = datetime.now(timezone.utc)
        now_iso = now.strftime("%Y-%m-%dT%H:%M:%SZ")
        lease_sec = max(10, min(lease_seconds, 3600))
        lease_exp_iso = (now + timedelta(seconds=lease_sec)).strftime("%Y-%m-%dT%H:%M:%SZ")
        claim_token = str(uuid.uuid4())

        cursor = await db.execute(
            """
            UPDATE tasks
            SET status = 'claimed', owner_worker_id = ?, claimed_at = ?, lease_expires_at = ?, claim_token = ?, updated_at = ?
            WHERE id = ? AND (status = 'pending' OR (status = 'claimed' AND lease_expires_at IS NOT NULL AND lease_expires_at <= ?))
            """,
            (worker_id, now_iso, lease_exp_iso, claim_token, now_iso, task_id, now_iso)
        )

        if cursor.rowcount == 0:
            check_cursor = await db.execute("SELECT status, owner_worker_id, lease_expires_at FROM tasks WHERE id = ?", (task_id,))
            check = await check_cursor.fetchone()
            if not check:
                return {"error": f"Task '{task_id}' not found"}
            return {
                "error": f"Task '{task_id}' already claimed by '{check['owner_worker_id']}' (status: {check['status']})"
            }

        # Record attempt
        attempt_cursor = await db.execute("SELECT COUNT(*) FROM task_attempts WHERE task_id = ?", (task_id,))
        attempt_num = (await attempt_cursor.fetchone())[0] + 1
        await db.execute(
            "INSERT INTO task_attempts (task_id, worker_id, attempt_number, status, started_at) VALUES (?, ?, ?, 'running', ?)",
            (task_id, worker_id, attempt_num, now_iso)
        )
        await db.execute("UPDATE workers SET status = 'busy', last_heartbeat = ? WHERE id = ?", (now_iso, worker_id))
        await db.commit()

        task_cursor = await db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        task_row = await task_cursor.fetchone()
        return {
            "success": True,
            "task": _row_to_dict(task_row),
            "claim_token": claim_token,
            "lease_expires_at": lease_exp_iso,
        }
    finally:
        await db.close()

@mcp_server.tool(
    name="renew_task_lease",
    description="Renew the lease expiration on an actively claimed task."
)
async def renew_task_lease(
    task_id: str,
    worker_id: str,
    claim_token: str | None = None,
    lease_seconds: int = 300,
) -> dict[str, Any]:
    db = await get_db_conn()
    try:
        now = datetime.now(timezone.utc)
        now_iso = now.strftime("%Y-%m-%dT%H:%M:%SZ")
        lease_sec = max(10, min(lease_seconds, 3600))
        lease_exp_iso = (now + timedelta(seconds=lease_sec)).strftime("%Y-%m-%dT%H:%M:%SZ")

        query = "UPDATE tasks SET lease_expires_at = ?, updated_at = ? WHERE id = ? AND status = 'claimed' AND owner_worker_id = ?"
        params = [lease_exp_iso, now_iso, task_id, worker_id]
        if claim_token:
            query += " AND claim_token = ?"
            params.append(claim_token)

        cursor = await db.execute(query, tuple(params))
        if cursor.rowcount == 0:
            return {"error": f"Cannot renew lease for '{task_id}': invalid owner or claim token"}

        await db.execute("UPDATE workers SET last_heartbeat = ? WHERE id = ?", (now_iso, worker_id))
        await db.commit()

        task_cursor = await db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        task_row = await task_cursor.fetchone()
        return {
            "success": True,
            "task": _row_to_dict(task_row),
            "lease_expires_at": lease_exp_iso,
        }
    finally:
        await db.close()

@mcp_server.tool(
    name="release_task",
    description="Release a claimed task back to pending queue."
)
async def release_task(
    task_id: str,
    worker_id: str,
    claim_token: str | None = None,
) -> dict[str, Any]:
    db = await get_db_conn()
    try:
        now = _now_iso()
        cursor = await db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        task = await cursor.fetchone()
        if not task:
            return {"error": f"Task '{task_id}' not found"}
        if task["owner_worker_id"] != worker_id:
            return {"error": f"Task owned by '{task['owner_worker_id']}', not '{worker_id}'"}

        await db.execute(
            """
            UPDATE tasks
            SET status = 'pending', owner_worker_id = NULL, claimed_at = NULL, lease_expires_at = NULL, claim_token = NULL, updated_at = ?
            WHERE id = ?
            """,
            (now, task_id)
        )
        await db.execute("UPDATE workers SET status = 'idle', last_heartbeat = ? WHERE id = ?", (now, worker_id))
        await db.commit()

        task_cursor = await db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        return {"success": True, "task": _row_to_dict(await task_cursor.fetchone())}
    finally:
        await db.close()

@mcp_server.tool(
    name="block_task",
    description="Mark a claimed task as blocked with a specific reason."
)
async def block_task(
    task_id: str,
    worker_id: str,
    reason: str,
) -> dict[str, Any]:
    db = await get_db_conn()
    try:
        now = _now_iso()
        cursor = await db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        task = await cursor.fetchone()
        if not task:
            return {"error": f"Task '{task_id}' not found"}
        if task["owner_worker_id"] != worker_id:
            return {"error": f"Task owned by '{task['owner_worker_id']}', not '{worker_id}'"}

        await db.execute(
            "UPDATE tasks SET status = 'blocked', blocked_reason = ?, updated_at = ? WHERE id = ?",
            (reason, now, task_id)
        )
        await db.commit()
        task_cursor = await db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        return {"success": True, "task": _row_to_dict(await task_cursor.fetchone())}
    finally:
        await db.close()

@mcp_server.tool(
    name="unblock_task",
    description="Unblock a blocked task and return it to pending or claimed state."
)
async def unblock_task(
    task_id: str,
    worker_id: str,
) -> dict[str, Any]:
    db = await get_db_conn()
    try:
        now = _now_iso()
        cursor = await db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        task = await cursor.fetchone()
        if not task:
            return {"error": f"Task '{task_id}' not found"}

        await db.execute(
            "UPDATE tasks SET status = 'pending', blocked_reason = NULL, updated_at = ? WHERE id = ?",
            (now, task_id)
        )
        await db.commit()
        task_cursor = await db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        return {"success": True, "task": _row_to_dict(await task_cursor.fetchone())}
    finally:
        await db.close()

@mcp_server.tool(
    name="submit_checkpoint",
    description="Submit completed task deliverable, mark task 'done', and auto-advance pipeline."
)
async def submit_checkpoint(
    task_id: str,
    submitted_by: str,
    summary: str,
    result_text: str | None = None,
    kind: str = "text",
    branch_name: str | None = None,
    commit_sha: str | None = None,
) -> dict[str, Any]:
    db = await get_db_conn()
    try:
        now = _now_iso()
        cursor = await db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        task = await cursor.fetchone()
        if not task:
            return {"error": f"Task '{task_id}' not found"}

        # Ensure worker exists to satisfy foreign key constraint
        await db.execute(
            """
            INSERT OR IGNORE INTO workers (id, provider, node_id, nickname, status, capabilities, quota_limit_per_window, cooldown_window_minutes, last_heartbeat, registered_at)
            VALUES (?, 'claude_desktop', 'local', ?, 'idle', '["writing","research","code","qa","seo","formatting"]', 1000, 0, ?, ?)
            """,
            (submitted_by, submitted_by, now, now)
        )

        await db.execute(
            """
            INSERT OR REPLACE INTO checkpoints (task_id, job_id, kind, summary, result_text, branch_name, commit_sha, submitted_by, submitted_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (task_id, task["job_id"], kind, summary, result_text, branch_name, commit_sha, submitted_by, now)
        )
        await db.execute("UPDATE tasks SET status = 'done', completed_at = ?, updated_at = ? WHERE id = ?", (now, now, task_id))
        await db.execute(
            "UPDATE task_attempts SET status = 'succeeded', finished_at = ? WHERE task_id = ? AND worker_id = ? AND status = 'running'",
            (now, task_id, submitted_by)
        )
        await db.execute(
            "UPDATE workers SET status = 'idle', quota_used_current = quota_used_current + 1, last_heartbeat = ? WHERE id = ?",
            (now, submitted_by)
        )
        await db.commit()

        # Advance stage if part of a job
        if task["job_id"]:
            next_task_id = await pipeline_engine.advance_task_to_next_stage(task_id, db)
            if not next_task_id:
                await pipeline_engine.check_and_finalize_job(task["job_id"], db)

        cp_cursor = await db.execute("SELECT * FROM checkpoints WHERE task_id = ?", (task_id,))
        return {"success": True, "checkpoint": _row_to_dict(await cp_cursor.fetchone())}
    finally:
        await db.close()

# =====================================================================
# 2. QA & VERIFICATION TOOLS
# =====================================================================

@mcp_server.tool(
    name="submit_qa_review",
    description="Submit QA verification review (pass, fail, revision_needed) for a task."
)
async def submit_qa_review(
    task_id: str,
    reviewer_worker_id: str,
    verdict: str,
    checks_passed: dict[str, bool] | None = None,
    rejection_reason: str | None = None,
) -> dict[str, Any]:
    db = await get_db_conn()
    try:
        now = _now_iso()
        cursor = await db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        task = await cursor.fetchone()
        if not task:
            return {"error": f"Task '{task_id}' not found"}

        # Ensure reviewer worker exists to satisfy foreign key constraint
        await db.execute(
            """
            INSERT OR IGNORE INTO workers (id, provider, node_id, nickname, status, capabilities, quota_limit_per_window, cooldown_window_minutes, last_heartbeat, registered_at)
            VALUES (?, 'system', 'local', ?, 'idle', '["qa"]', 1000, 0, ?, ?)
            """,
            (reviewer_worker_id, reviewer_worker_id, now, now)
        )

        checks_json = json.dumps(checks_passed or {})
        cursor = await db.execute(
            """
            INSERT INTO qa_reviews (task_id, job_id, reviewer_worker_id, verdict, rejection_reason, checks_passed, reviewed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (task_id, task["job_id"], reviewer_worker_id, verdict, rejection_reason, checks_json, now)
        )
        review_id = cursor.lastrowid

        if verdict in ("fail", "revision_needed"):
            await db.execute(
                "UPDATE tasks SET status = 'pending', owner_worker_id = NULL, claimed_at = NULL, lease_expires_at = NULL, claim_token = NULL, updated_at = ? WHERE id = ?",
                (now, task_id)
            )
            if task["job_id"]:
                await db.execute(
                    "UPDATE job_metrics SET rejected_tasks = rejected_tasks + 1, total_revisions = total_revisions + 1 WHERE job_id = ?",
                    (task["job_id"],)
                )
        elif verdict == "pass":
            await db.execute("UPDATE tasks SET status = 'merged', updated_at = ? WHERE id = ?", (now, task_id))
            if task["job_id"]:
                await db.execute(
                    "UPDATE job_metrics SET completed_tasks = completed_tasks + 1 WHERE job_id = ?",
                    (task["job_id"],)
                )
                next_task = await pipeline_engine.advance_task_to_next_stage(task_id, db)
                if not next_task:
                    await pipeline_engine.check_and_finalize_job(task["job_id"], db)

        await db.commit()
        return {
            "success": True,
            "review_id": review_id,
            "verdict": verdict,
            "task_id": task_id,
        }
    finally:
        await db.close()

# =====================================================================
# 3. JOB & SKU PIPELINE TOOLS
# =====================================================================

@mcp_server.tool(
    name="submit_job_from_template",
    description="Create a high-level job from a SKU template with auto-pipeline decomposition."
)
async def submit_job_from_template(
    template_name: str,
    client: str = "claude-desktop",
    input_uri: str = "manual",
    deadline: str | None = None,
    parameters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    db = await get_db_conn()
    try:
        params = parameters or {}
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        cursor = await db.execute("SELECT COUNT(*) FROM jobs WHERE id LIKE ?", (f"job_{today}_%",))
        count = (await cursor.fetchone())[0]
        job_id = f"job_{today}_{count + 1:03d}"

        template_to_pipeline = {
            "seo_content_batch": ["research", "draft", "seo_optimize", "qa", "format"],
            "30_day_social_package": ["research", "draft", "publish", "qa", "format"],
            "100_product_descriptions": ["research", "draft", "qa", "format"],
            "document_processing_50": ["ingest", "extract", "synthesize", "qa"],
            "default": ["research", "draft", "qa", "format"],
        }
        pipeline = params.get("pipeline", template_to_pipeline.get(template_name, template_to_pipeline["default"]))
        quality_rules = params.get("quality_rules", [])

        now = _now_iso()
        await db.execute(
            """
            INSERT INTO jobs (id, sku, client, input_uri, status, pipeline, quality_rules, deadline, created_at, updated_at)
            VALUES (?, ?, ?, ?, 'intake', ?, ?, ?, ?, ?)
            """,
            (job_id, template_name, client, input_uri, json.dumps(pipeline), json.dumps(quality_rules), deadline, now, now)
        )
        await db.execute("INSERT OR IGNORE INTO job_metrics (job_id, started_at) VALUES (?, ?)", (job_id, now))
        await db.commit()

        job_cursor = await db.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
        job_dict = _row_to_dict(await job_cursor.fetchone())
        job_dict["pipeline"] = json.loads(job_dict["pipeline"])
        job_dict["quality_rules"] = json.loads(job_dict["quality_rules"])
        return job_dict
    finally:
        await db.close()

@mcp_server.tool(
    name="list_jobs",
    description="List active and completed jobs in the orchestrator."
)
async def list_jobs(status: str | None = None) -> list[dict[str, Any]]:
    db = await get_db_conn()
    try:
        query = "SELECT * FROM jobs WHERE 1=1"
        params: list[Any] = []
        if status:
            query += " AND status = ?"
            params.append(status)
        query += " ORDER BY created_at DESC LIMIT 50"

        cursor = await db.execute(query, tuple(params))
        rows = await cursor.fetchall()
        result = []
        for r in rows:
            d = _row_to_dict(r)
            d["pipeline"] = json.loads(d["pipeline"]) if isinstance(d.get("pipeline"), str) else d.get("pipeline")
            d["quality_rules"] = json.loads(d["quality_rules"]) if isinstance(d.get("quality_rules"), str) else d.get("quality_rules")
            result.append(d)
        return result
    finally:
        await db.close()

@mcp_server.tool(
    name="get_job",
    description="Get detailed status of a job and its pipeline."
)
async def get_job(job_id: str) -> dict[str, Any]:
    db = await get_db_conn()
    try:
        cursor = await db.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
        row = await cursor.fetchone()
        if not row:
            return {"error": f"Job '{job_id}' not found"}
        d = _row_to_dict(row)
        d["pipeline"] = json.loads(d["pipeline"]) if isinstance(d.get("pipeline"), str) else d.get("pipeline")
        d["quality_rules"] = json.loads(d["quality_rules"]) if isinstance(d.get("quality_rules"), str) else d.get("quality_rules")
        return d
    finally:
        await db.close()

@mcp_server.tool(
    name="get_job_metrics",
    description="Retrieve aggregated throughput and task metrics for a job."
)
async def get_job_metrics(job_id: str) -> dict[str, Any]:
    db = await get_db_conn()
    try:
        cursor = await db.execute("SELECT * FROM job_metrics WHERE job_id = ?", (job_id,))
        row = await cursor.fetchone()
        if not row:
            return {"error": f"Metrics for job '{job_id}' not found"}
        return _row_to_dict(row)
    finally:
        await db.close()

# =====================================================================
# 4. WORKER REGISTRY & TELEMETRY TOOLS
# =====================================================================

@mcp_server.tool(
    name="register_worker",
    description="Register or update worker capability and quota parameters in the fleet."
)
async def register_worker(
    worker_id: str,
    nickname: str,
    provider: str = "claude_desktop",
    node_id: str = "local-pc",
    capabilities: list[str] | None = None,
    quota_limit_per_window: int = 50,
    cooldown_window_minutes: int = 300,
) -> dict[str, Any]:
    db = await get_db_conn()
    try:
        caps = capabilities or ["writing", "research", "code", "qa", "seo", "formatting"]
        now = _now_iso()
        await db.execute(
            """
            INSERT INTO workers (id, provider, node_id, nickname, status, capabilities, quota_limit_per_window, cooldown_window_minutes, last_heartbeat, registered_at)
            VALUES (?, ?, ?, ?, 'idle', ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                provider=excluded.provider,
                nickname=excluded.nickname,
                capabilities=excluded.capabilities,
                quota_limit_per_window=excluded.quota_limit_per_window,
                cooldown_window_minutes=excluded.cooldown_window_minutes,
                last_heartbeat=excluded.last_heartbeat
            """,
            (worker_id, provider, node_id, nickname, json.dumps(caps), quota_limit_per_window, cooldown_window_minutes, now, now)
        )
        await db.commit()
        cursor = await db.execute("SELECT * FROM workers WHERE id = ?", (worker_id,))
        d = _row_to_dict(await cursor.fetchone())
        d["capabilities"] = json.loads(d["capabilities"])
        return d
    finally:
        await db.close()

@mcp_server.tool(
    name="worker_heartbeat",
    description="Send worker heartbeat telemetry, update active task status, or report cooldown."
)
async def worker_heartbeat(
    worker_id: str,
    current_task_id: str | None = None,
    note: str | None = None,
    trigger_cooldown: bool = False,
) -> dict[str, Any]:
    db = await get_db_conn()
    try:
        now = datetime.now(timezone.utc)
        now_iso = now.strftime("%Y-%m-%dT%H:%M:%SZ")

        cursor = await db.execute("SELECT * FROM workers WHERE id = ?", (worker_id,))
        w = await cursor.fetchone()
        if not w:
            return {"error": f"Worker '{worker_id}' not found"}

        cooldown_until = w["cooldown_until"]
        status = w["status"]

        if trigger_cooldown:
            cd_min = w["cooldown_window_minutes"] or 300
            cd_exp = now + timedelta(minutes=cd_min)
            cooldown_until = cd_exp.strftime("%Y-%m-%dT%H:%M:%SZ")
            status = "cooldown"

        await db.execute(
            "UPDATE workers SET last_heartbeat = ?, cooldown_until = ?, status = ? WHERE id = ?",
            (now_iso, cooldown_until, status, worker_id)
        )
        await db.commit()
        return {"success": True, "worker_id": worker_id, "status": status, "last_heartbeat": now_iso}
    finally:
        await db.close()

@mcp_server.tool(
    name="list_workers",
    description="List all registered worker profiles and their live status."
)
async def list_workers(status: str | None = None) -> list[dict[str, Any]]:
    db = await get_db_conn()
    try:
        query = "SELECT * FROM workers WHERE 1=1"
        params: list[Any] = []
        if status:
            query += " AND status = ?"
            params.append(status)
        cursor = await db.execute(query, tuple(params))
        rows = await cursor.fetchall()
        res = []
        for r in rows:
            d = _row_to_dict(r)
            d["capabilities"] = json.loads(d["capabilities"]) if isinstance(d.get("capabilities"), str) else d.get("capabilities")
            res.append(d)
        return res
    finally:
        await db.close()

@mcp_server.tool(
    name="get_worker",
    description="Fetch single worker details and quota metrics."
)
async def get_worker(worker_id: str) -> dict[str, Any]:
    db = await get_db_conn()
    try:
        cursor = await db.execute("SELECT * FROM workers WHERE id = ?", (worker_id,))
        row = await cursor.fetchone()
        if not row:
            return {"error": f"Worker '{worker_id}' not found"}
        d = _row_to_dict(row)
        d["capabilities"] = json.loads(d["capabilities"]) if isinstance(d.get("capabilities"), str) else d.get("capabilities")
        return d
    finally:
        await db.close()

@mcp_server.tool(
    name="get_system_health",
    description="Return coordinator backend health and fleet overview summary."
)
async def get_system_health() -> dict[str, Any]:
    db = await get_db_conn()
    try:
        jobs_c = await db.execute("SELECT COUNT(*) FROM jobs")
        job_count = (await jobs_c.fetchone())[0]

        tasks_c = await db.execute("SELECT COUNT(*) FROM tasks")
        task_count = (await tasks_c.fetchone())[0]

        workers_c = await db.execute("SELECT COUNT(*) FROM workers")
        worker_count = (await workers_c.fetchone())[0]

        pending_c = await db.execute("SELECT COUNT(*) FROM tasks WHERE status = 'pending'")
        pending_tasks = (await pending_c.fetchone())[0]

        claimed_c = await db.execute("SELECT COUNT(*) FROM tasks WHERE status = 'claimed'")
        claimed_tasks = (await claimed_c.fetchone())[0]

        done_c = await db.execute("SELECT COUNT(*) FROM tasks WHERE status IN ('done', 'merged')")
        done_tasks = (await done_c.fetchone())[0]

        return {
            "status": "healthy",
            "version": settings.VERSION,
            "counts": {
                "jobs": job_count,
                "tasks": task_count,
                "workers": worker_count,
                "pending_tasks": pending_tasks,
                "claimed_tasks": claimed_tasks,
                "done_tasks": done_tasks,
            }
        }
    finally:
        await db.close()

# =====================================================================
# 5. SHARED MEMORY & DURABLE CONTEXT TOOLS
# =====================================================================

@mcp_server.tool(
    name="push_memory",
    description="Push a shared memory entry (decision, insight, research finding) to the team store."
)
async def push_memory(
    account: str,
    text: str,
) -> dict[str, Any]:
    db = await get_db_conn()
    try:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        cursor = await db.execute("SELECT COUNT(*) FROM memory_entries WHERE id LIKE ?", (f"mem_{today}_%",))
        count = (await cursor.fetchone())[0]
        mem_id = f"mem_{today}_{count + 1:03d}"
        now = _now_iso()

        await db.execute(
            "INSERT INTO memory_entries (id, account, text, created_at) VALUES (?, ?, ?, ?)",
            (mem_id, account, text, now)
        )
        await db.commit()
        return {"success": True, "id": mem_id, "account": account, "text": text, "created_at": now}
    finally:
        await db.close()

@mcp_server.tool(
    name="search_memory",
    description="Search the team memory database for keywords or relevant context."
)
async def search_memory(
    query: str,
    limit: int = 20,
) -> list[dict[str, Any]]:
    db = await get_db_conn()
    try:
        search_pattern = f"%{query}%"
        cursor = await db.execute(
            "SELECT * FROM memory_entries WHERE text LIKE ? OR account LIKE ? ORDER BY created_at DESC LIMIT ?",
            (search_pattern, search_pattern, max(1, min(limit, 100)))
        )
        rows = await cursor.fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        await db.close()

@mcp_server.tool(
    name="read_team_memory",
    description="Retrieve chronological team memory entries, optionally filtered by timestamp."
)
async def read_team_memory(
    since: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    db = await get_db_conn()
    try:
        query = "SELECT * FROM memory_entries WHERE 1=1"
        params: list[Any] = []
        if since:
            query += " AND created_at >= ?"
            params.append(since)
        query += " ORDER BY created_at ASC LIMIT ?"
        params.append(max(1, min(limit, 200)))

        cursor = await db.execute(query, tuple(params))
        rows = await cursor.fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        await db.close()

@mcp_server.tool(
    name="read_team_context",
    description="Retrieve durable project context or identity scaffold ('scaffold', 'identity', etc.)."
)
async def read_team_context(
    key: str = "scaffold",
) -> dict[str, Any]:
    db = await get_db_conn()
    try:
        cursor = await db.execute("SELECT * FROM team_context WHERE key = ?", (key,))
        row = await cursor.fetchone()
        if row:
            return _row_to_dict(row)

        # Fallback to team-context.md file
        if settings.TEAM_CONTEXT_PATH.exists():
            content = settings.TEAM_CONTEXT_PATH.read_text(encoding="utf-8")
            now = _now_iso()
            # Seed to DB for future queries
            await db.execute(
                "INSERT OR REPLACE INTO team_context (key, value, updated_at) VALUES (?, ?, ?)",
                (key, content, now)
            )
            await db.commit()
            return {"key": key, "value": content, "updated_at": now}

        return {"error": f"Team context '{key}' not found"}
    finally:
        await db.close()
