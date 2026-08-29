from __future__ import annotations

import json
import pytest
import pytest_asyncio
import aiosqlite
from pathlib import Path

from server.core.database import init_db
from server.core.config import settings
from server.core.pipeline_engine import pipeline_engine

pytestmark = pytest.mark.asyncio

@pytest_asyncio.fixture(autouse=True)
async def setup_test_db(tmp_path: Path, monkeypatch):
    test_db_path = tmp_path / "test_production.db"
    monkeypatch.setattr(settings, "DATABASE_PATH", test_db_path)
    monkeypatch.setattr(settings, "DATA_DIR", tmp_path)
    await init_db()
    yield

async def test_pipeline_decomposition_and_waterfall():
    async with aiosqlite.connect(str(settings.DATABASE_PATH)) as db:
        db.row_factory = aiosqlite.Row

        # 1. Create a job
        job_id = "job_test_001"
        pipeline = ["research", "draft", "qa", "format"]
        quality_rules = ["No hallucinations", "Length <= 100 words"]
        
        await db.execute(
            """
            INSERT INTO jobs (id, sku, client, input_uri, status, pipeline, quality_rules)
            VALUES (?, '100_product_descriptions', 'Acme Corp', 'data/input.csv', 'intake', ?, ?)
            """,
            (job_id, json.dumps(pipeline), json.dumps(quality_rules))
        )
        await db.commit()

        # 2. Decompose job for 2 input items
        items = [
            {"product_name": "Ergonomic Keyboard", "specs": "Bluetooth, USB-C, 75%"},
            {"product_name": "Wireless Mouse", "specs": "2.4GHz, 4000 DPI"}
        ]
        created_task_ids = await pipeline_engine.decompose_job_into_tasks(job_id, items, db)
        assert len(created_task_ids) == 2
        
        # Verify first stage is 'research'
        cursor = await db.execute("SELECT stage, stage_order, status FROM tasks WHERE id = ?", (created_task_ids[0],))
        t1 = await cursor.fetchone()
        assert t1["stage"] == "research"
        assert t1["stage_order"] == 1
        assert t1["status"] == "pending"

        # 3. Simulate completion of Stage 1 task
        task_1_id = created_task_ids[0]
        await db.execute(
            """
            INSERT INTO checkpoints (task_id, job_id, kind, summary, result_text, submitted_by)
            VALUES (?, ?, 'text', 'Extracted attributes successfully', 'Extracted: Bluetooth, USB-C', 'worker_01')
            """,
            (task_1_id, job_id)
        )
        await db.execute("UPDATE tasks SET status = 'done' WHERE id = ?", (task_1_id,))
        await db.commit()

        # 4. Advance task to next stage (Stage 2: 'draft')
        next_task_id = await pipeline_engine.advance_task_to_next_stage(task_1_id, db)
        assert next_task_id is not None
        
        cursor = await db.execute("SELECT stage, stage_order, spec FROM tasks WHERE id = ?", (next_task_id,))
        t2 = await cursor.fetchone()
        assert t2["stage"] == "draft"
        assert t2["stage_order"] == 2
        assert "Extracted: Bluetooth, USB-C" in t2["spec"]
