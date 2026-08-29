from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
import aiosqlite

from server.core.database import get_db
from server.models.schemas import WorkerRegister, WorkerResponse, WorkerHeartbeat

router = APIRouter(prefix="/workers", tags=["Workers"])

def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

@router.post("/register", response_model=WorkerResponse, status_code=201)
async def register_worker(w: WorkerRegister, db: aiosqlite.Connection = Depends(get_db)):
    """Register or update an AI worker node / profile."""
    now = _now_iso()
    caps_json = json.dumps(w.capabilities)
    
    await db.execute(
        """
        INSERT INTO workers (id, provider, node_id, nickname, status, capabilities, quota_limit_per_window, cooldown_window_minutes, last_heartbeat, registered_at)
        VALUES (?, ?, ?, ?, 'idle', ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            provider = excluded.provider,
            node_id = excluded.node_id,
            nickname = excluded.nickname,
            capabilities = excluded.capabilities,
            quota_limit_per_window = excluded.quota_limit_per_window,
            cooldown_window_minutes = excluded.cooldown_window_minutes,
            last_heartbeat = excluded.last_heartbeat
        """,
        (w.id, w.provider, w.node_id, w.nickname, caps_json, w.quota_limit_per_window, w.cooldown_window_minutes, now, now)
    )
    await db.commit()
    return await get_worker(w.id, db)

@router.get("", response_model=list[WorkerResponse])
async def list_workers(
    status: str | None = Query(None, description="Filter by status ('idle', 'busy', 'cooldown', 'offline')"),
    db: aiosqlite.Connection = Depends(get_db)
):
    """List all registered worker nodes."""
    if status:
        cursor = await db.execute("SELECT * FROM workers WHERE status = ? ORDER BY id ASC", (status,))
    else:
        cursor = await db.execute("SELECT * FROM workers ORDER BY id ASC")
    rows = await cursor.fetchall()
    
    return [
        WorkerResponse(
            id=r["id"],
            provider=r["provider"],
            node_id=r["node_id"],
            nickname=r["nickname"],
            status=r["status"],
            capabilities=json.loads(r["capabilities"]),
            quota_limit_per_window=r["quota_limit_per_window"],
            quota_used_current=r["quota_used_current"],
            cooldown_window_minutes=r["cooldown_window_minutes"],
            cooldown_until=r["cooldown_until"],
            last_heartbeat=r["last_heartbeat"],
            registered_at=r["registered_at"]
        )
        for r in rows
    ]

@router.get("/{worker_id}", response_model=WorkerResponse)
async def get_worker(worker_id: str, db: aiosqlite.Connection = Depends(get_db)):
    """Retrieve details for a specific worker."""
    cursor = await db.execute("SELECT * FROM workers WHERE id = ?", (worker_id,))
    r = await cursor.fetchone()
    if not r:
        raise HTTPException(status_code=404, detail=f"Worker '{worker_id}' not found")
    
    return WorkerResponse(
        id=r["id"],
        provider=r["provider"],
        node_id=r["node_id"],
        nickname=r["nickname"],
        status=r["status"],
        capabilities=json.loads(r["capabilities"]),
        quota_limit_per_window=r["quota_limit_per_window"],
        quota_used_current=r["quota_used_current"],
        cooldown_window_minutes=r["cooldown_window_minutes"],
        cooldown_until=r["cooldown_until"],
        last_heartbeat=r["last_heartbeat"],
        registered_at=r["registered_at"]
    )

@router.post("/{worker_id}/heartbeat", response_model=WorkerResponse)
async def worker_heartbeat(worker_id: str, hb: WorkerHeartbeat, db: aiosqlite.Connection = Depends(get_db)):
    """Process heartbeat from a worker, updating usage, cooldown, and status."""
    cursor = await db.execute("SELECT * FROM workers WHERE id = ?", (worker_id,))
    worker = await cursor.fetchone()
    if not worker:
        raise HTTPException(status_code=404, detail=f"Worker '{worker_id}' not found")
    
    now = datetime.now(timezone.utc)
    now_iso = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    
    status = worker["status"]
    cooldown_until = worker["cooldown_until"]

    # Check if cooldown has expired
    if cooldown_until:
        cooldown_dt = datetime.fromisoformat(cooldown_until.replace("Z", "+00:00"))
        if now >= cooldown_dt:
            status = "idle"
            cooldown_until = None
            await db.execute("UPDATE workers SET quota_used_current = 0 WHERE id = ?", (worker_id,))

    # Trigger cooldown if requested or usage >= 95%
    if hb.trigger_cooldown or (hb.usage_percent and hb.usage_percent >= 95):
        status = "cooldown"
        cooldown_until_dt = now + timedelta(minutes=worker["cooldown_window_minutes"])
        cooldown_until = cooldown_until_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    if status == "offline":
        status = "idle"

    await db.execute(
        """
        UPDATE workers 
        SET status = ?, cooldown_until = ?, last_heartbeat = ?
        WHERE id = ?
        """,
        (status, cooldown_until, now_iso, worker_id)
    )
    await db.commit()
    
    return await get_worker(worker_id, db)
