from __future__ import annotations

from datetime import datetime, timezone, timedelta
import json
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query
import aiosqlite

from server.core.database import get_db
from server.core.pipeline_engine import pipeline_engine
from server.models.schemas import (
    TaskCreate, TaskResponse, TaskClaimRequest, TaskClaimResponse, TaskLeaseRenewRequest,
    TaskReleaseRequest, TaskBlockRequest, CheckpointSubmit, CheckpointResponse,
    QAReviewSubmit, QAReviewResponse
)

router = APIRouter(prefix="/tasks", tags=["Tasks"])

def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

@router.post("", response_model=TaskResponse, status_code=201)
async def create_task(task: TaskCreate, db: aiosqlite.Connection = Depends(get_db)):
    """Create a new task in the queue."""
    task_id = task.id
    if not task_id:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        cursor = await db.execute("SELECT COUNT(*) FROM tasks WHERE id LIKE ?", (f"task_{today}_%",))
        count = (await cursor.fetchone())[0]
        task_id = f"task_{today}_{count + 1:03d}"

    now = _now_iso()
    try:
        await db.execute(
            """
            INSERT INTO tasks (id, job_id, parent_id, stage, stage_order, kind, spec, status, priority, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?)
            """,
            (task_id, task.job_id, task.parent_id, task.stage, task.stage_order, task.kind, task.spec, task.priority, now, now)
        )
        await db.commit()
    except aiosqlite.IntegrityError as e:
        raise HTTPException(status_code=400, detail=f"Database integrity error: {str(e)}")

    return TaskResponse(
        id=task_id,
        job_id=task.job_id,
        parent_id=task.parent_id,
        stage=task.stage,
        stage_order=task.stage_order,
        kind=task.kind,
        spec=task.spec,
        status="pending",
        priority=task.priority,
        owner_worker_id=None,
        claimed_at=None,
        lease_expires_at=None,
        claim_token=None,
        completed_at=None,
        blocked_reason=None,
        created_at=now,
        updated_at=now
    )

@router.get("", response_model=list[TaskResponse])
async def list_tasks(
    status: str | None = Query(None, description="Filter by status ('pending', 'claimed', 'done', etc.)"),
    stage: str | None = Query(None, description="Filter by pipeline stage ('research', 'draft', 'qa')"),
    job_id: str | None = Query(None, description="Filter by job ID"),
    parent_id: str | None = Query(None, description="Filter by parent task ID"),
    limit: int = Query(50, ge=1, le=200),
    db: aiosqlite.Connection = Depends(get_db)
):
    """List tasks with flexible filtering."""
    query = "SELECT * FROM tasks WHERE 1=1"
    params: list[any] = []
    
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
    params.append(limit)
    
    cursor = await db.execute(query, tuple(params))
    rows = await cursor.fetchall()
    
    return [
        TaskResponse(
            id=r["id"],
            job_id=r["job_id"],
            parent_id=r["parent_id"],
            stage=r["stage"],
            stage_order=r["stage_order"],
            kind=r["kind"],
            spec=r["spec"],
            status=r["status"],
            priority=r["priority"],
            owner_worker_id=r["owner_worker_id"],
            claimed_at=r["claimed_at"],
            lease_expires_at=r["lease_expires_at"] if "lease_expires_at" in r.keys() else None,
            claim_token=r["claim_token"] if "claim_token" in r.keys() else None,
            completed_at=r["completed_at"],
            blocked_reason=r["blocked_reason"],
            created_at=r["created_at"],
            updated_at=r["updated_at"]
        )
        for r in rows
    ]

@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(task_id: str, db: aiosqlite.Connection = Depends(get_db)):
    """Get single task details."""
    cursor = await db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
    r = await cursor.fetchone()
    if not r:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")
    
    return TaskResponse(
        id=r["id"],
        job_id=r["job_id"],
        parent_id=r["parent_id"],
        stage=r["stage"],
        stage_order=r["stage_order"],
        kind=r["kind"],
        spec=r["spec"],
        status=r["status"],
        priority=r["priority"],
        owner_worker_id=r["owner_worker_id"],
        claimed_at=r["claimed_at"],
        lease_expires_at=r["lease_expires_at"] if "lease_expires_at" in r.keys() else None,
        claim_token=r["claim_token"] if "claim_token" in r.keys() else None,
        completed_at=r["completed_at"],
        blocked_reason=r["blocked_reason"],
        created_at=r["created_at"],
        updated_at=r["updated_at"]
    )

@router.post("/{task_id}/claim", response_model=TaskClaimResponse)
async def claim_task(task_id: str, req: TaskClaimRequest, db: aiosqlite.Connection = Depends(get_db)):
    """Claim a pending or expired task atomically with a lease duration."""
    now = datetime.now(timezone.utc)
    now_iso = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    lease_sec = max(1, min(req.lease_seconds, 3600))
    lease_exp_iso = (now + timedelta(seconds=lease_sec)).strftime("%Y-%m-%dT%H:%M:%SZ")
    claim_token = str(uuid.uuid4())

    # Atomic compare-and-swap update
    cursor = await db.execute(
        """
        UPDATE tasks 
        SET status = 'claimed', owner_worker_id = ?, claimed_at = ?, lease_expires_at = ?, claim_token = ?, updated_at = ?
        WHERE id = ? AND (status = 'pending' OR (status = 'claimed' AND lease_expires_at IS NOT NULL AND lease_expires_at <= ?))
        """,
        (req.worker_id, now_iso, lease_exp_iso, claim_token, now_iso, task_id, now_iso)
    )
    
    if cursor.rowcount == 0:
        # Check if task exists to return appropriate error
        check_cursor = await db.execute("SELECT status, owner_worker_id, lease_expires_at FROM tasks WHERE id = ?", (task_id,))
        task_check = await check_cursor.fetchone()
        if not task_check:
            raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")
        raise HTTPException(
            status_code=409,
            detail=f"Task '{task_id}' could not be claimed (status: {task_check['status']}, owner: {task_check['owner_worker_id']})"
        )

    # Record attempt
    attempt_cursor = await db.execute("SELECT COUNT(*) FROM task_attempts WHERE task_id = ?", (task_id,))
    attempt_num = (await attempt_cursor.fetchone())[0] + 1
    await db.execute(
        "INSERT INTO task_attempts (task_id, worker_id, attempt_number, status, started_at) VALUES (?, ?, ?, 'running', ?)",
        (task_id, req.worker_id, attempt_num, now_iso)
    )
    
    # Update worker state to busy
    await db.execute("UPDATE workers SET status = 'busy', last_heartbeat = ? WHERE id = ?", (now_iso, req.worker_id))
    await db.commit()
    
    task_resp = await get_task(task_id, db)
    return TaskClaimResponse(
        task=task_resp,
        claim_token=claim_token,
        lease_expires_at=lease_exp_iso
    )

@router.post("/{task_id}/renew-lease", response_model=TaskClaimResponse)
async def renew_task_lease(task_id: str, req: TaskLeaseRenewRequest, db: aiosqlite.Connection = Depends(get_db)):
    """Renew the lease on an actively claimed task."""
    now = datetime.now(timezone.utc)
    now_iso = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    lease_sec = max(10, min(req.lease_seconds, 3600))
    lease_exp_iso = (now + timedelta(seconds=lease_sec)).strftime("%Y-%m-%dT%H:%M:%SZ")

    query = """
        UPDATE tasks 
        SET lease_expires_at = ?, updated_at = ?
        WHERE id = ? AND status = 'claimed' AND owner_worker_id = ?
    """
    params = [lease_exp_iso, now_iso, task_id, req.worker_id]
    if req.claim_token:
        query += " AND claim_token = ?"
        params.append(req.claim_token)

    cursor = await db.execute(query, tuple(params))
    if cursor.rowcount == 0:
        raise HTTPException(status_code=403, detail=f"Cannot renew lease for task '{task_id}': invalid owner or claim token")

    await db.execute("UPDATE workers SET last_heartbeat = ? WHERE id = ?", (now_iso, req.worker_id))
    await db.commit()

    task_resp = await get_task(task_id, db)
    return TaskClaimResponse(
        task=task_resp,
        claim_token=task_resp.claim_token or "",
        lease_expires_at=lease_exp_iso
    )

@router.post("/{task_id}/release", response_model=TaskResponse)
async def release_task(task_id: str, req: TaskReleaseRequest, db: aiosqlite.Connection = Depends(get_db)):
    """Release a claimed task back to pending."""
    now = _now_iso()
    cursor = await db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
    task = await cursor.fetchone()
    if not task:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")
    
    if task["owner_worker_id"] != req.worker_id:
        raise HTTPException(status_code=403, detail=f"Task is owned by '{task['owner_worker_id']}', not '{req.worker_id}'")

    await db.execute(
        """
        UPDATE tasks 
        SET status = 'pending', owner_worker_id = NULL, claimed_at = NULL, lease_expires_at = NULL, claim_token = NULL, updated_at = ?
        WHERE id = ?
        """,
        (now, task_id)
    )
    await db.execute("UPDATE workers SET status = 'idle', last_heartbeat = ? WHERE id = ?", (now, req.worker_id))
    await db.commit()
    return await get_task(task_id, db)

@router.post("/{task_id}/block", response_model=TaskResponse)
async def block_task(task_id: str, req: TaskBlockRequest, db: aiosqlite.Connection = Depends(get_db)):
    """Mark a claimed task as blocked."""
    now = _now_iso()
    cursor = await db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
    task = await cursor.fetchone()
    if not task:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")
    if task["owner_worker_id"] != req.worker_id:
        raise HTTPException(status_code=403, detail=f"Task is owned by '{task['owner_worker_id']}', not '{req.worker_id}'")

    await db.execute(
        "UPDATE tasks SET status = 'blocked', blocked_reason = ?, updated_at = ? WHERE id = ?",
        (req.reason, now, task_id)
    )
    await db.commit()
    return await get_task(task_id, db)

# ----------------- CHECKPOINT SUBMISSION -----------------
@router.post("/{task_id}/checkpoint", response_model=CheckpointResponse, status_code=201)
async def submit_checkpoint(task_id: str, cp: CheckpointSubmit, db: aiosqlite.Connection = Depends(get_db)):
    """Submit finished task deliverable, mark task 'done', and advance pipeline stage."""
    now = _now_iso()
    cursor = await db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
    task = await cursor.fetchone()
    if not task:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")
    if task["owner_worker_id"] != cp.submitted_by:
        raise HTTPException(status_code=403, detail=f"Task is owned by '{task['owner_worker_id']}', not '{cp.submitted_by}'")

    # Insert or replace checkpoint
    await db.execute(
        """
        INSERT OR REPLACE INTO checkpoints (task_id, job_id, kind, summary, result_text, branch_name, commit_sha, submitted_by, submitted_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (task_id, task["job_id"], cp.kind, cp.summary, cp.result_text, cp.branch_name, cp.commit_sha, cp.submitted_by, now)
    )

    # Mark task done
    await db.execute(
        "UPDATE tasks SET status = 'done', completed_at = ?, updated_at = ? WHERE id = ?",
        (now, now, task_id)
    )

    # Update attempt status
    await db.execute(
        "UPDATE task_attempts SET status = 'succeeded', finished_at = ? WHERE task_id = ? AND worker_id = ? AND status = 'running'",
        (now, task_id, cp.submitted_by)
    )

    # Update worker quota used & set idle
    await db.execute(
        "UPDATE workers SET status = 'idle', quota_used_current = quota_used_current + 1, last_heartbeat = ? WHERE id = ?",
        (now, cp.submitted_by)
    )

    await db.commit()

    # Automatically advance task to next stage in pipeline
    if task["job_id"]:
        next_task_id = await pipeline_engine.advance_task_to_next_stage(task_id, db)
        if not next_task_id:
            # If final stage or waiting on siblings, check if entire job can be finalized
            await pipeline_engine.check_and_finalize_job(task["job_id"], db)

    return CheckpointResponse(
        task_id=task_id,
        job_id=task["job_id"],
        kind=cp.kind,
        summary=cp.summary,
        result_text=cp.result_text,
        branch_name=cp.branch_name,
        commit_sha=cp.commit_sha,
        submitted_by=cp.submitted_by,
        submitted_at=now
    )

@router.get("/{task_id}/checkpoint", response_model=CheckpointResponse)
async def get_checkpoint(task_id: str, db: aiosqlite.Connection = Depends(get_db)):
    """Retrieve checkpoint deliverable for a task."""
    cursor = await db.execute("SELECT * FROM checkpoints WHERE task_id = ?", (task_id,))
    cp = await cursor.fetchone()
    if not cp:
        raise HTTPException(status_code=404, detail=f"No checkpoint found for task '{task_id}'")
    
    return CheckpointResponse(
        task_id=cp["task_id"],
        job_id=cp["job_id"],
        kind=cp["kind"],
        summary=cp["summary"],
        result_text=cp["result_text"],
        branch_name=cp["branch_name"],
        commit_sha=cp["commit_sha"],
        submitted_by=cp["submitted_by"],
        submitted_at=cp["submitted_at"]
    )

# ----------------- QA REVIEWS -----------------
@router.post("/{task_id}/qa-review", response_model=QAReviewResponse, status_code=201)
async def submit_qa_review(task_id: str, qa: QAReviewSubmit, db: aiosqlite.Connection = Depends(get_db)):
    """Submit a QA verification pass/fail/revision review."""
    now = _now_iso()
    cursor = await db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
    task = await cursor.fetchone()
    if not task:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")

    checks_json = json.dumps(qa.checks_passed)

    cursor = await db.execute(
        """
        INSERT INTO qa_reviews (task_id, job_id, reviewer_worker_id, verdict, rejection_reason, checks_passed, reviewed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (task_id, task["job_id"], qa.reviewer_worker_id, qa.verdict, qa.rejection_reason, checks_json, now)
    )
    review_id = cursor.lastrowid

    # Handle verdict impact on task and metrics
    if qa.verdict in ("fail", "revision_needed"):
        # Requeue or mark revision
        await db.execute(
            "UPDATE tasks SET status = 'pending', owner_worker_id = NULL, claimed_at = NULL, lease_expires_at = NULL, claim_token = NULL, updated_at = ? WHERE id = ?",
            (now, task_id)
        )
        if task["job_id"]:
            await db.execute(
                "UPDATE job_metrics SET rejected_tasks = rejected_tasks + 1, total_revisions = total_revisions + 1 WHERE job_id = ?",
                (task["job_id"],)
            )
    elif qa.verdict == "pass":
        await db.execute("UPDATE tasks SET status = 'merged', updated_at = ? WHERE id = ?", (now, task_id))
        if task["job_id"]:
            await db.execute(
                "UPDATE job_metrics SET completed_tasks = completed_tasks + 1 WHERE job_id = ?",
                (task["job_id"],)
            )
            # Advance to next stage or finalize job
            next_task = await pipeline_engine.advance_task_to_next_stage(task_id, db)
            if not next_task:
                await pipeline_engine.check_and_finalize_job(task["job_id"], db)

    await db.commit()

    return QAReviewResponse(
        id=review_id,
        task_id=task_id,
        job_id=task["job_id"],
        reviewer_worker_id=qa.reviewer_worker_id,
        verdict=qa.verdict,
        rejection_reason=qa.rejection_reason,
        checks_passed=qa.checks_passed,
        reviewed_at=now
    )

