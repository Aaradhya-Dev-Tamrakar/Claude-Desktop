from __future__ import annotations

import pytest
import pytest_asyncio
import aiosqlite
from pathlib import Path

from server.core.database import init_db
from server.core.config import settings
from server.core.scheduler import scheduler
from server.core.supervisor import run_supervisor_cycle

pytestmark = pytest.mark.asyncio

@pytest_asyncio.fixture(autouse=True)
async def setup_test_db(tmp_path: Path, monkeypatch):
    test_db_path = tmp_path / "test_production.db"
    monkeypatch.setattr(settings, "DATABASE_PATH", test_db_path)
    monkeypatch.setattr(settings, "DATA_DIR", tmp_path)
    await init_db()
    yield

async def test_quota_scheduler_capability_matching():
    async with aiosqlite.connect(str(settings.DATABASE_PATH)) as db:
        db.row_factory = aiosqlite.Row

        # Register workers: one writer, one researcher
        await db.execute(
            """
            INSERT INTO workers (id, provider, node_id, nickname, status, capabilities, quota_limit_per_window, quota_used_current)
            VALUES ('worker_writer', 'claude_desktop', 'win-node', 'Writer Bot', 'idle', '["writing"]', 50, 0),
                   ('worker_researcher', 'gemini_free', 'cloud-node', 'Research Bot', 'idle', '["research"]', 50, 0)
            """
        )

        # Create a drafting task
        await db.execute(
            """
            INSERT INTO tasks (id, stage, stage_order, kind, spec, status, priority)
            VALUES ('task_draft_01', 'draft', 2, 'text', 'Draft copy for product', 'pending', 5)
            """
        )
        await db.commit()

        # Scheduler should select worker_writer for 'draft' stage
        best_worker = await scheduler.select_best_worker_for_task('task_draft_01', db)
        assert best_worker == "worker_writer"

async def test_scheduler_cooldown_filtering():
    async with aiosqlite.connect(str(settings.DATABASE_PATH)) as db:
        db.row_factory = aiosqlite.Row

        # Register a worker in cooldown and a fallback worker
        await db.execute(
            """
            INSERT INTO workers (id, provider, node_id, nickname, status, capabilities, quota_limit_per_window, quota_used_current, cooldown_until)
            VALUES ('worker_claude_exhausted', 'claude_desktop', 'win-node', 'Claude 1', 'cooldown', '["writing"]', 50, 50, '2099-01-01T00:00:00Z'),
                   ('worker_gemini_fallback', 'gemini_free', 'cloud-node', 'Gemini Free', 'idle', '["writing"]', 50, 5, NULL)
            """
        )

        await db.execute(
            """
            INSERT INTO tasks (id, stage, stage_order, kind, spec, status, priority)
            VALUES ('task_draft_02', 'draft', 2, 'text', 'Draft product description', 'pending', 5)
            """
        )
        await db.commit()

        # Should bypass exhausted Claude and select Gemini fallback
        best_worker = await scheduler.select_best_worker_for_task('task_draft_02', db)
        assert best_worker == "worker_gemini_fallback"

async def test_supervisor_dead_worker_recovery():
    async with aiosqlite.connect(str(settings.DATABASE_PATH)) as db:
        db.row_factory = aiosqlite.Row

        # Worker dead for 10 minutes (last heartbeat in past)
        stale_time = "2020-01-01T00:00:00Z"
        await db.execute(
            """
            INSERT INTO workers (id, provider, node_id, nickname, status, capabilities, quota_limit_per_window, last_heartbeat)
            VALUES ('dead_worker_01', 'claude_desktop', 'crashed-node', 'Dead Node', 'busy', '["writing"]', 50, ?)
            """,
            (stale_time,)
        )

        # Task held by dead worker
        await db.execute(
            """
            INSERT INTO tasks (id, stage, stage_order, kind, spec, status, owner_worker_id, claimed_at)
            VALUES ('task_abandoned_01', 'draft', 2, 'text', 'Important spec', 'claimed', 'dead_worker_01', ?)
            """,
            (stale_time,)
        )
        await db.commit()

    # Run supervisor cycle
    stats = await run_supervisor_cycle()
    assert stats["reclaimed_tasks"] >= 1
    assert stats["offline_workers"] >= 1

    # Verify task is back in pending state and worker is marked offline
    async with aiosqlite.connect(str(settings.DATABASE_PATH)) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT status, owner_worker_id FROM tasks WHERE id = 'task_abandoned_01'")
        t = await cursor.fetchone()
        assert t["status"] == "pending"
        assert t["owner_worker_id"] is None

        w_cursor = await db.execute("SELECT status FROM workers WHERE id = 'dead_worker_01'")
        w = await w_cursor.fetchone()
        assert w["status"] == "offline"
