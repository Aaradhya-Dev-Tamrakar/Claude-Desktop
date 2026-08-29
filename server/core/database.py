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
    """Initialize database tables and indexes from schema.sql."""
    settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
    schema_sql = settings.SCHEMA_PATH.read_text(encoding="utf-8")
    
    async with aiosqlite.connect(str(settings.DATABASE_PATH)) as db:
        await db.executescript(schema_sql)
        await db.commit()
