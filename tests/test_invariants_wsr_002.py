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
from client.adapters.claude_desktop_proxy import ClaudeDesktopProxyAdapter
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
    # 1. Groq adapter failure propagation
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

    # 2. Gemini adapter failure propagation
    gemini_adapter = GeminiFreeAdapter(worker_id="test_gemini", nickname="Test Gemini", api_key="bad_key")
    res_gemini = await gemini_adapter.execute_task(
        task_id="t2",
        spec="Test spec",
        stage="research",
        context={}
    )
    assert res_gemini["success"] is False
    assert res_gemini["error"] is not None

    # 3. ClaudeDesktopProxyAdapter: Invalid API key MUST emit error, zero silent fallthrough to mock
    claude_adapter = ClaudeDesktopProxyAdapter(
        worker_id="test_claude",
        nickname="Test Claude",
        api_key="bad_key",
        cdp_port=0,
    )
    res_claude = await claude_adapter.execute_task(
        task_id="t3",
        spec="Test spec",
        stage="writing",
        context={}
    )
    assert res_claude["success"] is False
    assert res_claude["error"] is not None
    assert "HTTP" in res_claude["error"] or "EXECUTION_FAILED" in res_claude["error"]

    # 4. ClaudeDesktopProxyAdapter: No provider available (no key, no CDP, no simulation)
    claude_no_prov = ClaudeDesktopProxyAdapter(
        worker_id="test_claude_none",
        nickname="Test Claude None",
        api_key="",
        cdp_port=0,
    )
    res_none = await claude_no_prov.execute_task(
        task_id="t4",
        spec="Test spec",
        stage="qa",
        context={}
    )
    assert res_none["success"] is False
    assert "NO_PROVIDER_AVAILABLE" in res_none["error"]

@pytest.mark.asyncio
async def test_invariant_c_truthful_telemetry():
    """Invariant C: Worker telemetry produces non-null empirical system metrics decoupled from quota."""
    telemetry = get_system_telemetry()
    assert isinstance(telemetry, dict)
    assert "cpu_percent" in telemetry
    assert "memory_percent" in telemetry
    assert "usage_percent" not in telemetry
    assert isinstance(telemetry["cpu_percent"], float)
    assert isinstance(telemetry["memory_percent"], float)

@pytest.mark.asyncio
async def test_invariant_c_no_spurious_cooldown_on_high_memory():
    """Invariant C: High OS RAM utilization MUST NEVER trigger worker quota cooldown."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Register worker
        await client.post("/api/v1/workers/register", json={
            "id": "telemetry_worker_01",
            "provider": "ollama_local",
            "node_id": "node-mem",
            "nickname": "Telemetry Worker",
            "capabilities": ["research"],
            "cooldown_window_minutes": 300,
        })

        # Send heartbeat with 98% memory utilization — must NOT trigger cooldown
        hb_resp = await client.post("/api/v1/workers/telemetry_worker_01/heartbeat", json={
            "cpu_percent": 85.0,
            "memory_percent": 98.5,
            "usage_percent": 98,
        })
        assert hb_resp.status_code == 200
        worker_state = hb_resp.json()
        assert worker_state["status"] != "cooldown", "High RAM usage must not trigger quota cooldown"
        assert worker_state["status"] == "idle"

        # Sending rate_limit_headroom <= 0 or trigger_cooldown DOES trigger cooldown
        cooldown_resp = await client.post("/api/v1/workers/telemetry_worker_01/heartbeat", json={
            "rate_limit_headroom": 0,
        })
        assert cooldown_resp.status_code == 200
        assert cooldown_resp.json()["status"] == "cooldown"

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

@pytest.mark.asyncio
async def test_invariant_d_qa_checkpoint_preservation():
    """Invariant D / Fix 5: Passing QA review preserves deliverable in checkpoints table and advances DAG."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Create Job with [research, qa, format]
        job_res = await client.post("/api/v1/jobs", json={
            "sku": "qa_pipeline_sku",
            "client": "qa_client",
            "input_uri": "test://input",
            "pipeline": ["research", "qa", "format"],
        })
        assert job_res.status_code == 201
        job_id = job_res.json()["id"]

        # Register workers
        await client.post("/api/v1/workers/register", json={
            "id": "qa_worker_01",
            "provider": "ollama_local",
            "node_id": "node-qa",
            "nickname": "QA Reviewer",
            "capabilities": ["qa", "research"],
        })

        # Create & complete stage 1
        await client.post("/api/v1/tasks", json={
            "id": "qa_test_task_1",
            "job_id": job_id,
            "stage": "research",
            "stage_order": 1,
            "kind": "text",
            "spec": "Research content",
        })
        claim1 = await client.post("/api/v1/tasks/qa_test_task_1/claim", json={
            "worker_id": "qa_worker_01",
            "lease_seconds": 300,
        })
        await client.post("/api/v1/tasks/qa_test_task_1/checkpoint", json={
            "task_id": "qa_test_task_1",
            "kind": "text",
            "summary": "Initial draft ready",
            "result_text": "Draft body text",
            "submitted_by": "qa_worker_01",
            "claim_token": claim1.json()["claim_token"],
        })

        # Stage 2 (qa) task was auto-created by pipeline engine
        async with aiosqlite.connect(str(settings.DATABASE_PATH)) as db:
            db.row_factory = aiosqlite.Row
            qa_task = await (await db.execute("SELECT id FROM tasks WHERE parent_id = 'qa_test_task_1'")).fetchone()
            assert qa_task is not None
            qa_task_id = qa_task["id"]

        # Submit QA review PASS with result_text
        qa_resp = await client.post(f"/api/v1/tasks/{qa_task_id}/qa-review", json={
            "task_id": qa_task_id,
            "reviewer_worker_id": "qa_worker_01",
            "verdict": "pass",
            "summary": "QA verified 100% compliant",
            "result_text": "QA Verified Deliverable: Draft body text approved.",
        })
        assert qa_resp.status_code == 201

        # Verify: checkpoint exists for the QA task AND format stage received the QA deliverable
        async with aiosqlite.connect(str(settings.DATABASE_PATH)) as db:
            db.row_factory = aiosqlite.Row
            qa_cp = await (await db.execute("SELECT * FROM checkpoints WHERE task_id = ?", (qa_task_id,))).fetchone()
            assert qa_cp is not None
            assert "QA Verified Deliverable" in qa_cp["result_text"]

            format_task = await (await db.execute("SELECT * FROM tasks WHERE parent_id = ?", (qa_task_id,))).fetchone()
            assert format_task is not None
            assert format_task["stage"] == "format"
            assert "QA Verified Deliverable" in format_task["spec"]

@pytest.mark.asyncio
async def test_invariant_d_atomic_rollback_on_failure(monkeypatch):
    """Invariant D / Fix 6: Failure during stage advancement rolls back checkpoint and task state atomically."""
    from server.core.pipeline_engine import pipeline_engine

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Create Job with [research, draft]
        job_res = await client.post("/api/v1/jobs", json={
            "sku": "rollback_sku",
            "client": "test_client",
            "input_uri": "test://input",
            "pipeline": ["research", "draft"],
        })
        job_id = job_res.json()["id"]

        # Register worker
        await client.post("/api/v1/workers/register", json={
            "id": "rollback_worker_01",
            "provider": "ollama_local",
            "node_id": "node-rb",
            "nickname": "Worker",
            "capabilities": ["research"],
        })

        # Create Stage 1 task & claim it
        await client.post("/api/v1/tasks", json={
            "id": "task_rollback_1",
            "job_id": job_id,
            "stage": "research",
            "stage_order": 1,
            "kind": "text",
            "spec": "Spec before simulated failure",
        })
        claim = await client.post("/api/v1/tasks/task_rollback_1/claim", json={
            "worker_id": "rollback_worker_01",
            "lease_seconds": 300,
        })
        claim_token = claim.json()["claim_token"]

        # Inject failure into advance_task_to_next_stage to simulate mid-transaction crash
        async def mock_advance_fail(*args, **kwargs):
            raise RuntimeError("SIMULATED_DATABASE_IO_ERROR_DURING_STAGE_ADVANCE")

        monkeypatch.setattr(pipeline_engine, "advance_task_to_next_stage", mock_advance_fail)

        # Attempt checkpoint submission — must fail with 500
        with pytest.raises(Exception):
            await client.post("/api/v1/tasks/task_rollback_1/checkpoint", json={
                "task_id": "task_rollback_1",
                "kind": "text",
                "summary": "Should be rolled back",
                "result_text": "Data that should not persist",
                "submitted_by": "rollback_worker_01",
                "claim_token": claim_token,
            })

        # Verify atomic rollback:
        # 1. Task remains claimed (not marked done)
        # 2. Checkpoint row does NOT exist
        # 3. No successor stage task was created
        async with aiosqlite.connect(str(settings.DATABASE_PATH)) as db:
            db.row_factory = aiosqlite.Row
            t = await (await db.execute("SELECT status FROM tasks WHERE id = 'task_rollback_1'")).fetchone()
            assert t["status"] == "claimed", f"Expected task status 'claimed', got '{t['status']}'"

            cp = await (await db.execute("SELECT * FROM checkpoints WHERE task_id = 'task_rollback_1'")).fetchone()
            assert cp is None, "Checkpoint should not persist after rollback"

            successor = await (await db.execute("SELECT * FROM tasks WHERE parent_id = 'task_rollback_1'")).fetchone()
            assert successor is None, "Successor task must not exist after rollback"
