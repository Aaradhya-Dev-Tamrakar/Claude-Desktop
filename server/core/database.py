from __future__ import annotations

import aiosqlite
from typing import AsyncGenerator
from server.core.config import settings

async def get_db() -> AsyncGenerator[aiosqlite.Connection, None]:
    """Dependency for obtaining an async sqlite database connection."""
    db = await aiosqlite.connect(str(settings.DATABASE_PATH))
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA foreign_keys = ON;")
    await db.execute("PRAGMA journal_mode = WAL;")
    try:
        yield db
    finally:
        await db.close()

async def init_db() -> None:
    """Initialize database tables and indexes from schema.sql with automatic migration support."""
    settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
    schema_sql = settings.SCHEMA_PATH.read_text(encoding="utf-8")
    
    async with aiosqlite.connect(str(settings.DATABASE_PATH)) as db:
        await db.executescript(schema_sql)
        
        # Check and migrate columns on tasks table if already existing
        cursor = await db.execute("PRAGMA table_info(tasks)")
        columns = [row[1] for row in await cursor.fetchall()]
        if "lease_expires_at" not in columns:
            await db.execute("ALTER TABLE tasks ADD COLUMN lease_expires_at DATETIME")
        if "claim_token" not in columns:
            await db.execute("ALTER TABLE tasks ADD COLUMN claim_token TEXT")

        await db.commit()

