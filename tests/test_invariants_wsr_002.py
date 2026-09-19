from __future__ import annotations

import json
import pytest
import pytest_asyncio
import aiosqlite
from httpx import AsyncClient, ASGITransport

from server.core.config import settings
from server.core.database import init_db
from server.main import app
from client.adapters.groq_adapter import GroqAdapter
from client.adapters.gemini_free_adapter import GeminiFreeAdapter
from client.worker_daemon import get_system_telemetry

@pytest_asyncio.fixture(autouse=True)
async def setup_test_db(tmp_path, monkeypatch):
    test_db = tmp_path / "test_inv_wsr_002.db"
    monkeypatch.setattr(settings, "DATABASE_PATH", test_db)
    monkeypatch.setattr(settings, "DATA_DIR", tmp_path)
    await init_db()
    yield

@pytest.mark.asyncio
async def test_invariant_b_strict_separation_of_real_and_simulation():
    """Invariant B: Unhandled API / network failure MUST emit typed error, NEVER synthetic success."""
    adapter = GroqAdapter(worker_id="test_groq", nickname="Test Groq", api_key="bad_key")
    res = await adapter.execute_task(
        task_id="t1",
        spec="Test spec",
        stage="draft",
        context={}
    )
    assert res["success"] is False
    assert res["error"] is not None
    assert "Invalid" in res["error"] or "HTTP" in res["error"] or "Groq" in res["error"]

    gemini_adapter = GeminiFreeAdapter(worker_id="test_gemini", nickname="Test Gemini", api_key="bad_key")
    res_gemini = await gemini_adapter.execute_task(
        task_id="t2",
        spec="Test spec",
        stage="research",
        context={}
    )
    assert res_gemini["success"] is False
    assert res_gemini["error"] is not None

@pytest.mark.asyncio
async def test_invariant_c_truthful_telemetry():
    """Invariant C: Worker telemetry produces non-null empirical system metrics."""
    telemetry = get_system_telemetry()
    assert isinstance(telemetry, dict)
    assert "cpu_percent" in telemetry
    assert "memory_percent" in telemetry
    assert "usage_percent" in telemetry
    assert isinstance(telemetry["cpu_percent"], float)
    assert isinstance(telemetry["memory_percent"], float)

@pytest.mark.asyncio
async def test_invariant_d_atomic_dag_stage_advancement():
    """Invariant D: Checkpoint submission and DAG next-stage creation commit atomically in a single transaction."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Create a Job with 2 stages: [research, draft]
        job_res = await client.post("/api/v1/jobs", json={
            "sku": "test_sku",
            "client": "test_client",
            "input_uri": "test://input",
            "pipeline": ["research", "draft"]
        })
        assert job_res.status_code == 201
        job_id = job_res.json()["id"]

        # Register worker
        await client.post("/api/v1/workers/register", json={
            "id": "researcher_01",
            "provider": "ollama_local",
            "node_id": "node-1",
            "nickname": "Researcher",
            "capabilities": ["research"]
        })

        # Create Stage 1 task
        t_res = await client.post("/api/v1/tasks", json={
            "id": "task_stage_1",
            "job_id": job_id,
            "stage": "research",
            "stage_order": 1,
            "kind": "text",
            "spec": "Perform market research"
        })
        assert t_res.status_code == 201

        # Claim task
        claim = await client.post("/api/v1/tasks/task_stage_1/claim", json={
            "worker_id": "researcher_01",
            "lease_seconds": 300
        })
        assert claim.status_code == 200
        claim_token = claim.json()["claim_token"]

        # Submit checkpoint: atomically marks stage 1 done AND creates stage 2 (draft) task
        cp_res = await client.post("/api/v1/tasks/task_stage_1/checkpoint", json={
            "task_id": "task_stage_1",
            "kind": "text",
            "summary": "Research done",
            "result_text": "Market findings: High demand for widget X",
            "submitted_by": "researcher_01",
            "claim_token": claim_token
        })
        assert cp_res.status_code == 201

        # Check in database: Stage 1 is done, checkpoint exists, Stage 2 task exists with prior output
        async with aiosqlite.connect(str(settings.DATABASE_PATH)) as db:
            db.row_factory = aiosqlite.Row
            t1 = await (await db.execute("SELECT status FROM tasks WHERE id = 'task_stage_1'")).fetchone()
            assert t1["status"] == "done"

            stage2_task = await (await db.execute("SELECT * FROM tasks WHERE parent_id = 'task_stage_1'")).fetchone()
            assert stage2_task is not None
            assert stage2_task["stage"] == "draft"
            assert stage2_task["stage_order"] == 2
            assert stage2_task["status"] == "pending"
            assert "Market findings: High demand for widget X" in stage2_task["spec"]
