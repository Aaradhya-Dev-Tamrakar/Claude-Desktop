from __future__ import annotations

from datetime import datetime, timezone
import aiosqlite
from fastapi import APIRouter, Depends, HTTPException, Query
from pathlib import Path

from server.core.config import settings
from server.core.database import get_db
from server.models.schemas import (
    MemoryCreate, MemoryResponse, ContextUpsert, ContextResponse
)

router = APIRouter(tags=["Memory & Context"])

def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

# ----------------- SHARED MEMORY -----------------
@router.post("/memory", response_model=MemoryResponse, status_code=201)
async def push_memory(entry: MemoryCreate, db: aiosqlite.Connection = Depends(get_db)):
    """Push a shared team memory entry to the central database."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    cursor = await db.execute("SELECT COUNT(*) FROM memory_entries WHERE id LIKE ?", (f"mem_{today}_%",))
    count = (await cursor.fetchone())[0]
    mem_id = f"mem_{today}_{count + 1:03d}"
    now = _now_iso()

    await db.execute(
        "INSERT INTO memory_entries (id, account, text, created_at) VALUES (?, ?, ?, ?)",
        (mem_id, entry.account, entry.text, now)
    )
    await db.commit()

    return MemoryResponse(id=mem_id, account=entry.account, text=entry.text, created_at=now)

@router.get("/memory", response_model=list[MemoryResponse])
async def list_memory(
    since: str | None = Query(None, description="ISO timestamp filter (returns entries on or after this date/time)"),
    account: str | None = Query(None, description="Filter by submitting account"),
    limit: int = Query(50, ge=1, le=200),
    db: aiosqlite.Connection = Depends(get_db)
):
    """List shared memory entries, ordered chronologically."""
    query = "SELECT * FROM memory_entries WHERE 1=1"
    params: list[any] = []

    if since:
        query += " AND created_at >= ?"
        params.append(since)
    if account:
        query += " AND account = ?"
        params.append(account)

    query += " ORDER BY created_at ASC LIMIT ?"
    params.append(limit)

    cursor = await db.execute(query, tuple(params))
    rows = await cursor.fetchall()
    return [
        MemoryResponse(id=r["id"], account=r["account"], text=r["text"], created_at=r["created_at"])
        for r in rows
    ]

@router.get("/memory/search", response_model=list[MemoryResponse])
async def search_memory(
    q: str = Query(..., min_length=1, description="Search query string"),
    limit: int = Query(20, ge=1, le=100),
    db: aiosqlite.Connection = Depends(get_db)
):
    """Search memory entries by keyword substring."""
    search_pattern = f"%{q}%"
    cursor = await db.execute(
        "SELECT * FROM memory_entries WHERE text LIKE ? OR account LIKE ? ORDER BY created_at DESC LIMIT ?",
        (search_pattern, search_pattern, limit)
    )
    rows = await cursor.fetchall()
    return [
        MemoryResponse(id=r["id"], account=r["account"], text=r["text"], created_at=r["created_at"])
        for r in rows
    ]

# ----------------- TEAM CONTEXT -----------------
@router.get("/context", response_model=list[ContextResponse])
async def get_all_context(db: aiosqlite.Connection = Depends(get_db)):
    """Retrieve all team context entries. Auto-seeds default 'scaffold' from team-context.md if empty."""
    cursor = await db.execute("SELECT * FROM team_context ORDER BY key ASC")
    rows = await cursor.fetchall()

    if not rows and settings.TEAM_CONTEXT_PATH.exists():
        try:
            content = settings.TEAM_CONTEXT_PATH.read_text(encoding="utf-8")
            now = _now_iso()
            await db.execute(
                "INSERT OR REPLACE INTO team_context (key, value, updated_at) VALUES ('scaffold', ?, ?)",
                (content, now)
            )
            await db.commit()
            cursor = await db.execute("SELECT * FROM team_context ORDER BY key ASC")
            rows = await cursor.fetchall()
        except Exception as e:
            pass

    return [
        ContextResponse(key=r["key"], value=r["value"], updated_at=r["updated_at"])
        for r in rows
    ]

@router.get("/context/{key}", response_model=ContextResponse)
async def get_context_by_key(key: str, db: aiosqlite.Connection = Depends(get_db)):
    """Retrieve a single context value by key."""
    cursor = await db.execute("SELECT * FROM team_context WHERE key = ?", (key,))
    row = await cursor.fetchone()
    if not row:
        # Fallback to team-context.md if asking for scaffold
        if key in ("scaffold", "identity") and settings.TEAM_CONTEXT_PATH.exists():
            content = settings.TEAM_CONTEXT_PATH.read_text(encoding="utf-8")
            return ContextResponse(key=key, value=content, updated_at=_now_iso())
        raise HTTPException(status_code=404, detail=f"Context key '{key}' not found")

    return ContextResponse(key=row["key"], value=row["value"], updated_at=row["updated_at"])

@router.put("/context/{key}", response_model=ContextResponse)
async def upsert_context(key: str, req: ContextUpsert, db: aiosqlite.Connection = Depends(get_db)):
    """Set or update a persistent team context key-value entry."""
    now = _now_iso()
    await db.execute(
        "INSERT OR REPLACE INTO team_context (key, value, updated_at) VALUES (?, ?, ?)",
        (key, req.value, now)
    )
    await db.commit()
    return ContextResponse(key=key, value=req.value, updated_at=now)
