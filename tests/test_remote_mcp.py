from __future__ import annotations

import os
import pytest
import pytest_asyncio
import aiosqlite
from httpx import AsyncClient, ASGITransport

from server.core.config import settings
from server.core.database import init_db, get_db_conn
from server.main import app
from server.mcp_remote import (
    create_task, list_tasks, get_task, claim_task, renew_task_lease, release_task,
    block_task, unblock_task, submit_checkpoint, submit_qa_review,
    submit_job_from_template, list_jobs, get_job, get_job_metrics,
    register_worker, worker_heartbeat, list_workers, get_worker, get_system_health,
    push_memory, search_memory, read_team_memory, read_team_context
)

@pytest_asyncio.fixture(autouse=True)
async def setup_test_db(tmp_path, monkeypatch):
    test_db = tmp_path / "test_production.db"
    monkeypatch.setattr(settings, "DATABASE_PATH", test_db)
    monkeypatch.setattr(settings, "DATA_DIR", tmp_path)
    await init_db()
    yield

@pytest.mark.asyncio
async def test_mcp_task_lifecycle():
    # 1. Create task
    t = await create_task(spec="Audit API latency", stage="research", kind="text", priority=2)
    assert t["id"].startswith("task_")
    task_id = t["id"]
    assert t["status"] == "pending"

    # 2. Register worker
    w = await register_worker(worker_id="worker_alpha", nickname="Alpha", capabilities=["research", "writing"])
    assert w["id"] == "worker_alpha"
    assert w["status"] == "idle"

    # 3. Claim task
    claim = await claim_task(task_id=task_id, worker_id="worker_alpha", lease_seconds=120)
    assert claim["success"] is True
    assert claim["claim_token"] is not None
    assert claim["task"]["status"] == "claimed"
    assert claim["task"]["owner_worker_id"] == "worker_alpha"

    # 4. Renew lease
    renew = await renew_task_lease(task_id=task_id, worker_id="worker_alpha", claim_token=claim["claim_token"], lease_seconds=240)
    assert renew["success"] is True

    # 5. Block & Unblock
    b = await block_task(task_id=task_id, worker_id="worker_alpha", reason="Waiting for API access")
    assert b["success"] is True
    assert b["task"]["status"] == "blocked"

    ub = await unblock_task(task_id=task_id, worker_id="worker_alpha")
    assert ub["success"] is True
    assert ub["task"]["status"] == "pending"

    # Re-claim and submit checkpoint
    await claim_task(task_id=task_id, worker_id="worker_alpha", lease_seconds=120)
    cp = await submit_checkpoint(task_id=task_id, submitted_by="worker_alpha", summary="Completed research", result_text="Latency is 12ms")
    assert cp["success"] is True
    assert cp["checkpoint"]["summary"] == "Completed research"

    # Verify task state
    fetched = await get_task(task_id=task_id)
    assert fetched["status"] == "done"

@pytest.mark.asyncio
async def test_mcp_memory_and_context():
    # Push memories
    m1 = await push_memory(account="profile_shreejan", text="Decided to use SQLite WAL mode for fast concurrency")
    m2 = await push_memory(account="profile_tisha", text="Implemented remote SSE MCP transport on port 8000")
    assert m1["id"].startswith("mem_")
    assert m2["id"].startswith("mem_")

    # Read memory list
    all_mem = await read_team_memory()
    assert len(all_mem) >= 2

    # Search memory
    results = await search_memory(query="SQLite")
    assert len(results) >= 1
    assert "SQLite WAL mode" in results[0]["text"]

    # Read context scaffold
    ctx = await read_team_context(key="scaffold")
    assert ctx["key"] == "scaffold"
    assert len(ctx["value"]) > 0

@pytest.mark.asyncio
async def test_mcp_jobs_and_qa_review():
    # Submit job from template
    job = await submit_job_from_template(template_name="100_product_descriptions", client="test_client")
    assert job["id"].startswith("job_")
    assert job["sku"] == "100_product_descriptions"
    assert "draft" in job["pipeline"]

    # List jobs
    jobs = await list_jobs()
    assert len(jobs) >= 1

    # Metrics
    metrics = await get_job_metrics(job_id=job["id"])
    assert metrics["job_id"] == job["id"]

    # Create task attached to job and submit QA review
    t = await create_task(spec="Draft copy for Product 1", stage="draft", job_id=job["id"])
    qa = await submit_qa_review(task_id=t["id"], reviewer_worker_id="qa_bot", verdict="pass", checks_passed={"grammar": True})
    assert qa["success"] is True
    assert qa["verdict"] == "pass"

@pytest.mark.asyncio
async def test_mcp_system_health_and_fleet():
    await register_worker(worker_id="worker_beta", nickname="Beta", capabilities=["qa"])
    await worker_heartbeat(worker_id="worker_beta", note="Working on test")
    
    workers = await list_workers()
    assert any(w["id"] == "worker_beta" for w in workers)

    health = await get_system_health()
    assert health["status"] == "healthy"
    assert health["counts"]["workers"] >= 1

@pytest.mark.asyncio
async def test_fastapi_rest_routes():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Health check
        resp = await client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
        assert resp.json()["mcp_endpoint"] == "/mcp"

        # Memory REST routes
        post_mem = await client.post("/api/v1/memory", json={"account": "rest_user", "text": "Testing REST API"})
        assert post_mem.status_code == 201
        mem_id = post_mem.json()["id"]

        get_mem = await client.get("/api/v1/memory")
        assert get_mem.status_code == 200
        assert any(m["id"] == mem_id for m in get_mem.json())

        search_mem = await client.get("/api/v1/memory/search", params={"q": "REST"})
        assert search_mem.status_code == 200
        assert len(search_mem.json()) >= 1

@pytest.mark.asyncio
async def test_checkpoint_retry_is_idempotent():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post("/api/v1/workers/register", json={
            "id": "idempotent_worker", "provider": "ollama_local", "node_id": "node-1",
            "nickname": "Idempotent Worker", "capabilities": ["writing"]
        })
        await client.post("/api/v1/tasks", json={
            "id": "task_idempotent", "stage": "draft", "kind": "text", "spec": "retry test"
        })
        claim = await client.post("/api/v1/tasks/task_idempotent/claim", json={
            "worker_id": "idempotent_worker"
        })
        checkpoint = {
            "task_id": "task_idempotent", "kind": "text", "summary": "done",
            "result_text": "result", "submitted_by": "idempotent_worker",
            "claim_token": claim.json()["claim_token"]
        }
        first = await client.post("/api/v1/tasks/task_idempotent/checkpoint", json=checkpoint)
        second = await client.post("/api/v1/tasks/task_idempotent/checkpoint", json=checkpoint)

    assert first.status_code == 201
    assert second.status_code == 201
    assert second.json()["submitted_at"] == first.json()["submitted_at"]

@pytest.mark.asyncio
async def test_released_attempts_are_closed_and_limit_is_enforced(monkeypatch):
    monkeypatch.setattr(settings, "MAX_TASK_ATTEMPTS", 1)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post("/api/v1/workers/register", json={
            "id": "limited_worker", "provider": "ollama_local", "node_id": "node-1",
            "nickname": "Limited Worker", "capabilities": ["writing"]
        })
        await client.post("/api/v1/tasks", json={
            "id": "task_attempt_limit", "stage": "draft", "kind": "text", "spec": "attempt test"
        })
        claim = await client.post("/api/v1/tasks/task_attempt_limit/claim", json={
            "worker_id": "limited_worker"
        })
        release = await client.post("/api/v1/tasks/task_attempt_limit/release", json={
            "worker_id": "limited_worker", "claim_token": claim.json()["claim_token"]
        })
        blocked_claim = await client.post("/api/v1/tasks/task_attempt_limit/claim", json={
            "worker_id": "limited_worker"
        })

    assert release.status_code == 200
    assert blocked_claim.status_code == 409
    async with aiosqlite.connect(str(settings.DATABASE_PATH)) as db:
        db.row_factory = aiosqlite.Row
        attempt = await (await db.execute(
            "SELECT status FROM task_attempts WHERE task_id = 'task_attempt_limit'"
        )).fetchone()
        task = await (await db.execute(
            "SELECT status FROM tasks WHERE id = 'task_attempt_limit'"
        )).fetchone()
    assert attempt["status"] == "failed"
    assert task["status"] == "failed"
