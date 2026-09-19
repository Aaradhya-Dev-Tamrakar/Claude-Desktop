from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from server.core.config import settings
from server.core.database import init_db
from server.main import app

@pytest_asyncio.fixture(autouse=True)
async def setup_test_db(tmp_path, monkeypatch):
    test_db = tmp_path / "test_acq.db"
    monkeypatch.setattr(settings, "DATABASE_PATH", test_db)
    monkeypatch.setattr(settings, "DATA_DIR", tmp_path)
    await init_db()
    yield

@pytest.mark.asyncio
async def test_acquire_returns_204_when_no_tasks():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Register idle worker
        reg = await client.post("/api/v1/workers/register", json={
            "id": "worker_acq_1",
            "provider": "ollama_local",
            "node_id": "node-1",
            "nickname": "Worker 1",
            "capabilities": ["writing"]
        })
        assert reg.status_code == 201

        # Acquire when queue is empty -> 204 No Content
        acq = await client.post("/api/v1/tasks/acquire", json={
            "worker_id": "worker_acq_1",
            "capabilities": ["writing"],
            "lease_seconds": 120
        })
        assert acq.status_code == 204

@pytest.mark.asyncio
async def test_acquire_matches_capabilities_and_leases_atomically():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Register workers
        await client.post("/api/v1/workers/register", json={
            "id": "writer_worker",
            "provider": "groq",
            "node_id": "node-1",
            "nickname": "Writer",
            "capabilities": ["writing", "draft"]
        })
        await client.post("/api/v1/workers/register", json={
            "id": "qa_worker",
            "provider": "claude_desktop_cdp",
            "node_id": "node-1",
            "nickname": "QA Bot",
            "capabilities": ["qa", "qa_review"]
        })

        # Create QA task and Draft task
        t_draft = await client.post("/api/v1/tasks", json={
            "id": "task_draft_01",
            "stage": "draft",
            "kind": "text",
            "spec": "Draft blog post",
            "priority": 2
        })
        assert t_draft.status_code == 201

        t_qa = await client.post("/api/v1/tasks", json={
            "id": "task_qa_01",
            "stage": "qa",
            "kind": "text",
            "spec": "Verify blog post",
            "priority": 1
        })
        assert t_qa.status_code == 201

        # Writer acquires: should skip QA task (capability mismatch) and acquire Draft task
        acq_writer = await client.post("/api/v1/tasks/acquire", json={
            "worker_id": "writer_worker",
            "lease_seconds": 180
        })
        assert acq_writer.status_code == 200
        writer_data = acq_writer.json()
        assert writer_data["task"]["id"] == "task_draft_01"
        assert writer_data["task"]["owner_worker_id"] == "writer_worker"
        assert writer_data["claim_token"] is not None

        # QA worker acquires: acquires QA task
        acq_qa = await client.post("/api/v1/tasks/acquire", json={
            "worker_id": "qa_worker",
            "lease_seconds": 180
        })
        assert acq_qa.status_code == 200
        qa_data = acq_qa.json()
        assert qa_data["task"]["id"] == "task_qa_01"
        assert qa_data["task"]["owner_worker_id"] == "qa_worker"
        assert qa_data["claim_token"] is not None

        # Subsequent acquire -> 204
        acq_empty = await client.post("/api/v1/tasks/acquire", json={
            "worker_id": "writer_worker"
        })
        assert acq_empty.status_code == 204
