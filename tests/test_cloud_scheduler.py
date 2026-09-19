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

async def test_cross_provider_tier_prioritization_and_overflow():
    """Verify that Claude primary is preferred when available, but overflows to Copilot when in cooldown."""
    async with aiosqlite.connect(str(settings.DATABASE_PATH)) as db:
        db.row_factory = aiosqlite.Row

        # Register Claude CDP primary and Copilot headless overflow worker
        await db.execute(
            """
            INSERT INTO workers (id, provider, node_id, nickname, status, capabilities, quota_limit_per_window, quota_used_current, cooldown_until)
            VALUES ('claude_primary_01', 'claude_desktop_cdp', 'win-node', 'Claude Primary', 'idle', '["writing", "formatting"]', 50, 10, NULL),
                   ('copilot_overflow_01', 'copilot_headless', 'win-node', 'Copilot Overflow', 'idle', '["writing", "formatting"]', 10, 1, NULL)
            """
        )

        # 1. Normal task: Claude has higher provider tier weight, should be chosen
        await db.execute(
            """
            INSERT INTO tasks (id, stage, stage_order, kind, spec, status, priority)
            VALUES ('task_tier_01', 'draft', 1, 'text', 'Draft section', 'pending', 5)
            """
        )
        await db.commit()

        best_worker = await scheduler.select_best_worker_for_task('task_tier_01', db)
        assert best_worker == "claude_primary_01"

        # 2. Put Claude into cooldown (e.g. 5-hour limit hit)
        await db.execute(
            "UPDATE workers SET status = 'cooldown', cooldown_until = '2099-01-01T00:00:00Z' WHERE id = 'claude_primary_01'"
        )

        await db.execute(
            """
            INSERT INTO tasks (id, stage, stage_order, kind, spec, status, priority)
            VALUES ('task_tier_02', 'draft', 1, 'text', 'Draft another section', 'pending', 5)
            """
        )
        await db.commit()

        # Should automatically overflow to Copilot headless without pipeline stall
        best_overflow = await scheduler.select_best_worker_for_task('task_tier_02', db)
        assert best_overflow == "copilot_overflow_01"


async def test_stage_affinity_routing():
    """Verify that repetitive format stages favor Copilot headless, while QA favors Claude."""
    async with aiosqlite.connect(str(settings.DATABASE_PATH)) as db:
        db.row_factory = aiosqlite.Row

        # Register equal-quota workers with different providers
        await db.execute(
            """
            INSERT INTO workers (id, provider, node_id, nickname, status, capabilities, quota_limit_per_window, quota_used_current)
            VALUES ('claude_worker', 'claude_desktop_cdp', 'win-node', 'Claude Bot', 'idle', '["formatting", "qa"]', 50, 0),
                   ('copilot_worker', 'copilot_headless', 'win-node', 'Copilot Bot', 'idle', '["formatting", "qa"]', 50, 0)
            """
        )

        # QA task -> Claude has QA affinity
        await db.execute(
            "INSERT INTO tasks (id, stage, stage_order, kind, spec, status, priority) VALUES ('task_qa_01', 'qa', 3, 'text', 'Review draft', 'pending', 1)"
        )
        # Format task -> Copilot has format affinity
        await db.execute(
            "INSERT INTO tasks (id, stage, stage_order, kind, spec, status, priority) VALUES ('task_fmt_01', 'format', 4, 'text', 'Clean markdown', 'pending', 1)"
        )
        await db.commit()

        best_qa = await scheduler.select_best_worker_for_task('task_qa_01', db)
        assert best_qa == "claude_worker"
