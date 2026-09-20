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

        # Acquire QA task via Closed-Loop Protocol
        qa_claim = await client.post("/api/v1/tasks/acquire", json={
            "worker_id": "qa_worker_01",
            "capabilities": ["qa", "writing", "code"],
            "lease_seconds": 300
        })
        assert qa_claim.status_code == 200
        qa_claim_data = qa_claim.json()
        assert qa_claim_data["task"]["id"] == qa_task_id
        qa_token = qa_claim_data["claim_token"]

        # Submit QA review PASS with result_text and claim_token
        qa_resp = await client.post(f"/api/v1/tasks/{qa_task_id}/qa-review", json={
            "task_id": qa_task_id,
            "reviewer_worker_id": "qa_worker_01",
            "claim_token": qa_token,
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

@pytest.mark.asyncio
async def test_claim_token_masked_on_read_endpoints():
    """Security hardening (G-4): claim_token must be None on read-only endpoints, exposed only to claiming worker."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Register worker
        await client.post("/api/v1/workers/register", json={
            "id": "mask_worker_01",
            "provider": "ollama_local",
            "node_id": "node-mask",
            "nickname": "Masking Worker",
            "capabilities": ["research"],
        })

        # 2. Create task
        await client.post("/api/v1/tasks", json={
            "id": "task_masked_token_1",
            "stage": "research",
            "stage_order": 1,
            "kind": "text",
            "spec": "Test token masking",
        })

        # Read before claim
        get_before = await client.get("/api/v1/tasks/task_masked_token_1")
        assert get_before.status_code == 200
        assert get_before.json()["claim_token"] is None

        # Claim task: must return claim_token to claiming worker
        claim_resp = await client.post("/api/v1/tasks/task_masked_token_1/claim", json={
            "worker_id": "mask_worker_01",
            "lease_seconds": 300,
        })
        assert claim_resp.status_code == 200
        claim_token = claim_resp.json()["claim_token"]
        assert claim_token is not None and len(claim_token) > 0

        # Read after claim via GET /tasks/{id}: MUST be masked
        get_after = await client.get("/api/v1/tasks/task_masked_token_1")
        assert get_after.status_code == 200
        assert get_after.json()["claim_token"] is None, "claim_token must be masked on GET /tasks/{id}"

        # Read after claim via GET /tasks: MUST be masked
        list_after = await client.get("/api/v1/tasks")
        assert list_after.status_code == 200
        matching = [t for t in list_after.json() if t["id"] == "task_masked_token_1"]
        assert len(matching) == 1
        assert matching[0]["claim_token"] is None, "claim_token must be masked on GET /tasks"


@pytest.mark.asyncio
async def test_cross_worker_session_migration_and_resumption():
    """The Cross-Worker Session Continuity Money Test (INV-WSR-002 Invariants A, B, C, D):
    1. Worker A (claude_worker) acquires stage 1 ('research'), executes, submits durable checkpoint.
    2. DAG automatically generates stage 2 ('draft') containing Worker A's findings in spec.
    3. Worker A acquires stage 2, encounters rate limit (429), triggers cooldown, and releases task.
    4. Worker B (copilot_worker) calls /tasks/acquire, atomically pulls stage 2 task with durable state.
    5. Worker B executes stage 2, submits checkpoint, advances to stage 3 ('format').
    6. Stage 3 completes with unbroken provenance across workers and providers.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Create Job with 3 stages: [research, draft, format]
        job_res = await client.post("/api/v1/jobs", json={
            "sku": "cross_migration_sku",
            "client": "enterprise_client",
            "input_uri": "s3://corp/project_alpha",
            "pipeline": ["research", "draft", "format"],
        })
        assert job_res.status_code == 201
        job_id = job_res.json()["id"]

        # Register Worker A (Claude Desktop CDP)
        await client.post("/api/v1/workers/register", json={
            "id": "worker_claude_primary",
            "provider": "claude_desktop_cdp",
            "node_id": "node-cdp-01",
            "nickname": "Claude Primary",
            "capabilities": ["research", "draft", "qa"],
            "quota_limit_per_window": 50,
            "cooldown_window_minutes": 300,
        })

        # Register Worker B (Copilot Headless)
        await client.post("/api/v1/workers/register", json={
            "id": "worker_copilot_overflow",
            "provider": "copilot_headless",
            "node_id": "node-copilot-02",
            "nickname": "Copilot Overflow",
            "capabilities": ["draft", "format", "writing"],
            "quota_limit_per_window": 50,
            "cooldown_window_minutes": 300,
        })

        # Create Stage 1 task
        t1_res = await client.post("/api/v1/tasks", json={
            "id": "task_cm_stage_1",
            "job_id": job_id,
            "stage": "research",
            "stage_order": 1,
            "kind": "text",
            "spec": "Conduct deep analysis on distributed agent consensus protocols.",
        })
        assert t1_res.status_code == 201

        # Step 1: Worker A acquires stage 1 task
        acq1 = await client.post("/api/v1/tasks/acquire", json={
            "worker_id": "worker_claude_primary",
            "capabilities": ["research", "draft"],
            "lease_seconds": 300,
        })
        assert acq1.status_code == 200
        claim_data_1 = acq1.json()
        assert claim_data_1["task"]["id"] == "task_cm_stage_1"
        token_1 = claim_data_1["claim_token"]

        # Step 2: Worker A completes stage 1 and submits checkpoint
        w1_findings = "RESEARCH OUTPUT: Consensus achieves sub-second finality with raft quorum."
        cp1_res = await client.post("/api/v1/tasks/task_cm_stage_1/checkpoint", json={
            "task_id": "task_cm_stage_1",
            "kind": "text",
            "summary": "Consensus research completed",
            "result_text": w1_findings,
            "submitted_by": "worker_claude_primary",
            "claim_token": token_1,
        })
        assert cp1_res.status_code == 201

        # Step 3: Find generated stage 2 task
        async with aiosqlite.connect(str(settings.DATABASE_PATH)) as db:
            db.row_factory = aiosqlite.Row
            s2_task = await (await db.execute("SELECT * FROM tasks WHERE parent_id = 'task_cm_stage_1'")).fetchone()
            assert s2_task is not None
            assert s2_task["stage"] == "draft"
            stage_2_id = s2_task["id"]
            # Spec must contain Worker A's research findings
            assert w1_findings in s2_task["spec"]

        # Step 4: Worker A acquires stage 2 task
        acq2 = await client.post("/api/v1/tasks/acquire", json={
            "worker_id": "worker_claude_primary",
            "capabilities": ["research", "draft"],
            "lease_seconds": 300,
        })
        assert acq2.status_code == 200
        token_2_claude = acq2.json()["claim_token"]

        # Step 5: Worker A encounters RATE LIMIT 429 during execution!
        # Worker A triggers cooldown and releases task back to pending
        hb_cooldown = await client.post("/api/v1/workers/worker_claude_primary/heartbeat", json={
            "rate_limit_headroom": 0,
            "trigger_cooldown": True,
        })
        assert hb_cooldown.status_code == 200
        assert hb_cooldown.json()["status"] == "cooldown"

        release_resp = await client.post(f"/api/v1/tasks/{stage_2_id}/release", json={
            "worker_id": "worker_claude_primary",
            "claim_token": token_2_claude,
        })
        assert release_resp.status_code == 200
        assert release_resp.json()["status"] == "pending"

        # Step 6: Worker A can NO LONGER acquire tasks because it is in cooldown
        acq_blocked = await client.post("/api/v1/tasks/acquire", json={
            "worker_id": "worker_claude_primary",
            "capabilities": ["research", "draft"],
        })
        assert acq_blocked.status_code == 204

        # Step 7: Worker B (Copilot overflow) acquires the stage 2 task seamlessly
        acq_copilot = await client.post("/api/v1/tasks/acquire", json={
            "worker_id": "worker_copilot_overflow",
            "capabilities": ["draft", "format"],
            "lease_seconds": 300,
        })
        assert acq_copilot.status_code == 200
        claim_data_copilot = acq_copilot.json()
        assert claim_data_copilot["task"]["id"] == stage_2_id
        token_copilot = claim_data_copilot["claim_token"]
        assert token_copilot != token_2_claude, "Reclaimed task must issue a fresh, unique claim_token"

        # Verify Worker B has the uncorrupted spec containing Worker A's research output
        assert w1_findings in claim_data_copilot["task"]["spec"]

        # Step 8: Worker B executes stage 2 and submits checkpoint
        w2_draft = "DRAFT OUTPUT: Architecture draft incorporating raft consensus findings."
        cp2_res = await client.post(f"/api/v1/tasks/{stage_2_id}/checkpoint", json={
            "task_id": stage_2_id,
            "kind": "text",
            "summary": "Draft created from Worker A research",
            "result_text": w2_draft,
            "submitted_by": "worker_copilot_overflow",
            "claim_token": token_copilot,
        })
        assert cp2_res.status_code == 201

        # Step 9: Worker B acquires and completes final stage ('format')
        async with aiosqlite.connect(str(settings.DATABASE_PATH)) as db:
            db.row_factory = aiosqlite.Row
            s3_task = await (await db.execute("SELECT * FROM tasks WHERE parent_id = ?", (stage_2_id,))).fetchone()
            assert s3_task is not None
            assert s3_task["stage"] == "format"
            stage_3_id = s3_task["id"]

        acq3 = await client.post("/api/v1/tasks/acquire", json={
            "worker_id": "worker_copilot_overflow",
            "capabilities": ["draft", "format"],
            "lease_seconds": 300,
        })
        assert acq3.status_code == 200
        assert acq3.json()["task"]["id"] == stage_3_id

        cp3_res = await client.post(f"/api/v1/tasks/{stage_3_id}/checkpoint", json={
            "task_id": stage_3_id,
            "kind": "text",
            "summary": "Final document formatted",
            "result_text": "FINAL DELIVERABLE: Beautifully formatted specification document.",
            "submitted_by": "worker_copilot_overflow",
            "claim_token": acq3.json()["claim_token"],
        })
        assert cp3_res.status_code == 201

        # Step 10: Verify complete job status & lineage across checkpoints
        async with aiosqlite.connect(str(settings.DATABASE_PATH)) as db:
            db.row_factory = aiosqlite.Row
            job_row = await (await db.execute("SELECT status FROM jobs WHERE id = ?", (job_id,))).fetchone()
            assert job_row["status"] == "completed"

            checkpoints = await (await db.execute("SELECT * FROM checkpoints WHERE job_id = ? ORDER BY submitted_at ASC", (job_id,))).fetchall()
            assert len(checkpoints) == 3
            # Checkpoint 1 submitted by Worker A
            assert checkpoints[0]["submitted_by"] == "worker_claude_primary"
            # Checkpoint 2 and 3 submitted by Worker B
            assert checkpoints[1]["submitted_by"] == "worker_copilot_overflow"
            assert checkpoints[2]["submitted_by"] == "worker_copilot_overflow"


@pytest.mark.asyncio
async def test_qa_review_enforces_lease_and_claim_token(setup_test_db):
    """
    Invariant E Verification:
    QA review submission requires lease ownership and valid claim token.
    Rejects unowned tasks, wrong workers, and invalid claim tokens with HTTP 403.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Register workers
        await client.post("/api/v1/workers/register", json={
            "id": "qa_legit_worker",
            "provider": "claude_desktop_cdp",
            "node_id": "test-node",
            "nickname": "Legit QA Worker",
            "capabilities": ["qa", "review"],
            "quota_limit_per_window": 50,
            "cooldown_window_minutes": 300,
        })
        await client.post("/api/v1/workers/register", json={
            "id": "qa_intruder_worker",
            "provider": "groq",
            "node_id": "test-node",
            "nickname": "Intruder Worker",
            "capabilities": ["qa"],
            "quota_limit_per_window": 50,
            "cooldown_window_minutes": 300,
        })

        # Create task
        task_res = await client.post("/api/v1/tasks", json={
            "id": "task_qa_lease_test_001",
            "stage": "qa",
            "stage_order": 1,
            "kind": "text",
            "spec": "Review code for architectural invariants",
            "priority": 1,
        })
        assert task_res.status_code == 201

        # Case 1: Unclaimed task rejects QA review
        unclaimed_res = await client.post("/api/v1/tasks/task_qa_lease_test_001/qa-review", json={
            "task_id": "task_qa_lease_test_001",
            "reviewer_worker_id": "qa_legit_worker",
            "claim_token": "fake-token",
            "verdict": "pass",
        })
        assert unclaimed_res.status_code == 403
        assert "not 'qa_legit_worker'" in unclaimed_res.json()["detail"]

        # Acquire task with legit worker
        acq_res = await client.post("/api/v1/tasks/acquire", json={
            "worker_id": "qa_legit_worker",
            "capabilities": ["qa", "review"],
            "lease_seconds": 300,
        })
        assert acq_res.status_code == 200
        legit_token = acq_res.json()["claim_token"]

        # Case 2: Wrong worker ID with valid token rejects QA review
        intruder_res = await client.post("/api/v1/tasks/task_qa_lease_test_001/qa-review", json={
            "task_id": "task_qa_lease_test_001",
            "reviewer_worker_id": "qa_intruder_worker",
            "claim_token": legit_token,
            "verdict": "pass",
        })
        assert intruder_res.status_code == 403
        assert "owned by 'qa_legit_worker'" in intruder_res.json()["detail"]

        # Case 3: Legit worker with wrong claim token rejects QA review
        bad_token_res = await client.post("/api/v1/tasks/task_qa_lease_test_001/qa-review", json={
            "task_id": "task_qa_lease_test_001",
            "reviewer_worker_id": "qa_legit_worker",
            "claim_token": "wrong-token-abc",
            "verdict": "pass",
        })
        assert bad_token_res.status_code == 403
        assert "Invalid or expired claim token" in bad_token_res.json()["detail"]

        # Case 4: Legit worker with legit claim token succeeds
        valid_res = await client.post("/api/v1/tasks/task_qa_lease_test_001/qa-review", json={
            "task_id": "task_qa_lease_test_001",
            "reviewer_worker_id": "qa_legit_worker",
            "claim_token": legit_token,
            "verdict": "pass",
            "summary": "QA approved with valid lease token",
        })
        assert valid_res.status_code == 201


def test_telemetry_truthfulness_on_exception(monkeypatch):
    """
    Invariant C Verification:
    When system telemetry probes fail or raise an exception,
    the telemetry function must return None rather than synthetic 0.0% placeholders.
    """
    import sys
    from client.fleet_supervisor import get_system_telemetry as fleet_telemetry
    from client.worker_daemon import get_system_telemetry as daemon_telemetry

    # Force platform where probes are unavailable to simulate telemetry failure
    monkeypatch.setattr(sys, "platform", "unsupported_os_failure_simulation")

    fleet_res = fleet_telemetry()
    assert fleet_res["cpu_percent"] is None
    assert fleet_res["memory_percent"] is None

    daemon_res = daemon_telemetry()
    assert daemon_res["cpu_percent"] is None
    assert daemon_res["memory_percent"] is None

