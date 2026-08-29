from __future__ import annotations

import json
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
import aiosqlite

from server.core.database import get_db
from server.models.schemas import JobCreate, JobResponse, JobUpdate, JobMetricsResponse

router = APIRouter(prefix="/jobs", tags=["Jobs"])

def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

@router.post("", response_model=JobResponse, status_code=201)
async def create_job(job: JobCreate, db: aiosqlite.Connection = Depends(get_db)):
    """Create a new client job / production batch."""
    job_id = job.id
    if not job_id:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        cursor = await db.execute("SELECT COUNT(*) FROM jobs WHERE id LIKE ?", (f"job_{today}_%",))
        count = (await cursor.fetchone())[0]
        job_id = f"job_{today}_{count + 1:03d}"

    now = _now_iso()
    pipeline_json = json.dumps(job.pipeline)
    quality_rules_json = json.dumps(job.quality_rules)
    deadline_iso = job.deadline.isoformat() if job.deadline else None

    try:
        await db.execute(
            """
            INSERT INTO jobs (id, sku, client, input_uri, status, pipeline, quality_rules, deadline, created_at, updated_at)
            VALUES (?, ?, ?, ?, 'intake', ?, ?, ?, ?, ?)
            """,
            (job_id, job.sku, job.client, job.input_uri, pipeline_json, quality_rules_json, deadline_iso, now, now)
        )
        # Initialize metrics entry
        await db.execute("INSERT INTO job_metrics (job_id, started_at) VALUES (?, ?)", (job_id, now))
        await db.commit()
    except aiosqlite.IntegrityError:
        raise HTTPException(status_code=409, detail=f"Job with ID '{job_id}' already exists")

    return JobResponse(
        id=job_id,
        sku=job.sku,
        client=job.client,
        input_uri=job.input_uri,
        status="intake",
        pipeline=job.pipeline,
        quality_rules=job.quality_rules,
        deadline=job.deadline,
        created_at=now,
        updated_at=now
    )

@router.get("", response_model=list[JobResponse])
async def list_jobs(
    status: str | None = Query(None, description="Filter by status"),
    db: aiosqlite.Connection = Depends(get_db)
):
    """List all jobs with optional status filter."""
    if status:
        cursor = await db.execute("SELECT * FROM jobs WHERE status = ? ORDER BY created_at DESC", (status,))
    else:
        cursor = await db.execute("SELECT * FROM jobs ORDER BY created_at DESC")
    rows = await cursor.fetchall()
    
    return [
        JobResponse(
            id=r["id"],
            sku=r["sku"],
            client=r["client"],
            input_uri=r["input_uri"],
            status=r["status"],
            pipeline=json.loads(r["pipeline"]),
            quality_rules=json.loads(r["quality_rules"]),
            deadline=datetime.fromisoformat(r["deadline"]) if r["deadline"] else None,
            created_at=r["created_at"],
            updated_at=r["updated_at"]
        )
        for r in rows
    ]

@router.get("/{job_id}", response_model=JobResponse)
async def get_job(job_id: str, db: aiosqlite.Connection = Depends(get_db)):
    """Retrieve details of a single job."""
    cursor = await db.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
    r = await cursor.fetchone()
    if not r:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")
    
    return JobResponse(
        id=r["id"],
        sku=r["sku"],
        client=r["client"],
        input_uri=r["input_uri"],
        status=r["status"],
        pipeline=json.loads(r["pipeline"]),
        quality_rules=json.loads(r["quality_rules"]),
        deadline=datetime.fromisoformat(r["deadline"]) if r["deadline"] else None,
        created_at=r["created_at"],
        updated_at=r["updated_at"]
    )

@router.patch("/{job_id}", response_model=JobResponse)
async def update_job(job_id: str, patch: JobUpdate, db: aiosqlite.Connection = Depends(get_db)):
    """Update job status or deadline."""
    cursor = await db.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
    r = await cursor.fetchone()
    if not r:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")
    
    now = _now_iso()
    new_status = patch.status if patch.status is not None else r["status"]
    new_deadline = patch.deadline.isoformat() if patch.deadline is not None else r["deadline"]
    
    await db.execute(
        "UPDATE jobs SET status = ?, deadline = ?, updated_at = ? WHERE id = ?",
        (new_status, new_deadline, now, job_id)
    )
    if new_status == "completed":
        await db.execute("UPDATE job_metrics SET finished_at = ? WHERE job_id = ?", (now, job_id))
    await db.commit()
    
    return await get_job(job_id, db)

@router.get("/{job_id}/metrics", response_model=JobMetricsResponse)
async def get_job_metrics(job_id: str, db: aiosqlite.Connection = Depends(get_db)):
    """Retrieve throughput, rejection rate, and task statistics for a job."""
    cursor = await db.execute("SELECT * FROM job_metrics WHERE job_id = ?", (job_id,))
    m = await cursor.fetchone()
    if not m:
        raise HTTPException(status_code=404, detail=f"Metrics for job '{job_id}' not found")
    
    # Compute live counts from tasks table
    task_cursor = await db.execute(
        """
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN status = 'done' OR status = 'merged' THEN 1 ELSE 0 END) as completed,
            SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed
        FROM tasks WHERE job_id = ?
        """,
        (job_id,)
    )
    t_stats = await task_cursor.fetchone()

    total = t_stats["total"] or 0
    completed = t_stats["completed"] or 0

    return JobMetricsResponse(
        job_id=job_id,
        total_tasks=total,
        completed_tasks=completed,
        rejected_tasks=m["rejected_tasks"] or 0,
        total_revisions=m["total_revisions"] or 0,
        ai_calls_count=m["ai_calls_count"] or 0,
        human_intervention_minutes=m["human_intervention_minutes"] or 0.0,
        throughput_tasks_per_hour=m["throughput_tasks_per_hour"] or 0.0,
        started_at=m["started_at"],
        finished_at=m["finished_at"]
    )
