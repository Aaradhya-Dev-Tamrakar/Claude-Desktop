from __future__ import annotations

import asyncio
import json
import pytest
import pytest_asyncio
import aiosqlite
from datetime import datetime, timezone, timedelta
from pathlib import Path
from httpx import AsyncClient, ASGITransport

from server.main import app
from server.core.database import init_db
from server.core.config import settings
from server.core.pipeline_engine import pipeline_engine
from server.core.supervisor import run_supervisor_cycle
from client.adapters.claude_desktop_proxy import ClaudeDesktopProxyAdapter

pytestmark = pytest.mark.asyncio

@pytest_asyncio.fixture(autouse=True)
async def setup_test_db(tmp_path: Path, monkeypatch):
    test_db_path = tmp_path / "test_production.db"
    monkeypatch.setattr(settings, "DATABASE_PATH", test_db_path)
    monkeypatch.setattr(settings, "DATA_DIR", tmp_path)
    await init_db()
    yield

async def test_e2e_sku_pipeline_execution():
    """
    End-to-End Test:
    Intake a 3-item '100_product_descriptions' job through all 5 stages:
    research -> draft -> seo_optimize -> qa -> format -> final job completion.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver/api/v1") as client:
        # 1. Register workers
        await client.post("/workers/register", json={
            "id": "worker_claude_01",
            "provider": "claude_desktop",
            "node_id": "win-node-01",
            "nickname": "Claude Lead",
            "capabilities": ["research", "writing", "seo", "qa", "formatting"],
            "quota_limit_per_window": 100
        })

        # 2. Create Job
        pipeline = ["research", "draft", "seo_optimize", "qa", "format"]
        quality_rules = ["Highlight ergonomic benefits", "Include specs", "No fluff"]
        
        job_resp = await client.post("/jobs", json={
            "id": "job_e2e_prod_001",
            "sku": "100_product_descriptions",
            "client": "Nova Retail",
            "input_uri": "s3://production-jobs/products.csv",
            "pipeline": pipeline,
            "quality_rules": quality_rules
        })
        assert job_resp.status_code == 201
        job_data = job_resp.json()
        assert job_data["status"] == "intake"

        # 3. Decompose job into initial Stage 1 (research) tasks
        items = [
            {"sku": "KB-01", "name": "Ergonomic Mechanical Keyboard", "specs": "75% layout, wireless 2.4G/BT, Hot-swap"},
            {"sku": "MS-02", "name": "Vertical Precision Mouse", "specs": "4000 DPI, rechargeable, thumb rest"},
            {"sku": "HS-03", "name": "Active Noise Canceling Headset", "specs": "40mm drivers, USB-C, 30hr battery"}
        ]

        async with aiosqlite.connect(str(settings.DATABASE_PATH)) as db:
            db.row_factory = aiosqlite.Row
            created_task_ids = await pipeline_engine.decompose_job_into_tasks("job_e2e_prod_001", items, db)
        
        assert len(created_task_ids) == 3

        # 4. Simulate worker executing each stage through to completion
        adapter = ClaudeDesktopProxyAdapter(worker_id="worker_claude_01", nickname="Claude Lead")

        for stage_idx, stage_name in enumerate(pipeline, start=1):
            # Fetch pending tasks for this stage
            tasks_resp = await client.get("/tasks", params={"job_id": "job_e2e_prod_001", "status": "pending", "stage": stage_name})
            stage_tasks = tasks_resp.json()
            assert len(stage_tasks) == 3, f"Expected 3 tasks in stage {stage_name}, got {len(stage_tasks)}"

            for t in stage_tasks:
                task_id = t["id"]
                assert t["stage_order"] == stage_idx

                # Claim task
                claim_resp = await client.post(f"/tasks/{task_id}/claim", json={"worker_id": "worker_claude_01", "lease_seconds": 300})
                assert claim_resp.status_code == 200
                claim_data = claim_resp.json()
                claim_token = claim_data["claim_token"]
                assert claim_token is not None

                # Execute task via adapter
                exec_res = await adapter.execute_task(task_id, t["spec"], stage_name, {})
                assert exec_res["success"] is True

                # Submit checkpoint
                cp_resp = await client.post(f"/tasks/{task_id}/checkpoint", json={
                    "task_id": task_id,
                    "kind": "text",
                    "summary": exec_res["summary"],
                    "result_text": exec_res["result_text"],
                    "submitted_by": "worker_claude_01",
                    "claim_token": claim_token
                })
                assert cp_resp.status_code == 201

                # If stage is 'qa', submit QA review
                if stage_name == "qa":
                    qa_resp = await client.post(f"/tasks/{task_id}/qa-review", json={
                        "task_id": task_id,
                        "job_id": "job_e2e_prod_001",
                        "reviewer_worker_id": "worker_claude_01",
                        "verdict": "pass",
                        "checks_passed": {"specs_accuracy": True, "grammar": True, "rules": True}
                    })
                    assert qa_resp.status_code == 201

        # 5. Verify final job status is completed
        final_job_resp = await client.get("/jobs/job_e2e_prod_001")
        assert final_job_resp.status_code == 200
        assert final_job_resp.json()["status"] == "completed"

        # 6. Verify job metrics
        metrics_resp = await client.get("/jobs/job_e2e_prod_001/metrics")
        assert metrics_resp.status_code == 200
        metrics = metrics_resp.json()
        assert metrics["total_tasks"] == 15  # 3 items * 5 stages
        assert metrics["completed_tasks"] == 15
        assert metrics["finished_at"] is not None

async def test_concurrent_task_leasing_race_safety():
    """
    Test that when multiple workers race to claim the same task simultaneously,
    exactly ONE worker succeeds (200 OK) and all others receive 409 Conflict.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver/api/v1") as client:
        # Register 5 workers
        for i in range(1, 6):
            await client.post("/workers/register", json={
                "id": f"race_worker_{i:02d}",
                "provider": "gemini_free",
                "node_id": f"node_{i}",
                "nickname": f"Worker {i}",
                "capabilities": ["writing", "research"]
            })

        # Create a single task
        task_resp = await client.post("/tasks", json={
            "id": "task_race_001",
            "stage": "draft",
            "stage_order": 1,
            "kind": "text",
            "spec": "High contention test task"
        })
        assert task_resp.status_code == 201

        # Fire 5 concurrent claim requests
        async def try_claim(worker_id: str):
            return await client.post("/tasks/task_race_001/claim", json={"worker_id": worker_id, "lease_seconds": 120})

        results = await asyncio.gather(*[try_claim(f"race_worker_{i:02d}") for i in range(1, 6)])

        status_codes = [r.status_code for r in results]
        assert status_codes.count(200) == 1, f"Expected exactly 1 claim success, got {status_codes.count(200)}"
        assert status_codes.count(409) == 4, f"Expected 4 conflict responses, got {status_codes.count(409)}"

async def test_expired_lease_reclamation_and_recovery():
    """
    Test that tasks with expired leases can be claimed by a new worker
    or automatically recovered back to 'pending' by the supervisor cycle.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver/api/v1") as client:
        # Register workers
        await client.post("/workers/register", json={
            "id": "crashed_worker",
            "provider": "ollama_local",
            "node_id": "crashed-box",
            "nickname": "Crashed Worker",
            "capabilities": ["research"]
        })
        await client.post("/workers/register", json={
            "id": "recovery_worker",
            "provider": "claude_desktop",
            "node_id": "healthy-box",
            "nickname": "Recovery Worker",
            "capabilities": ["research"]
        })

        # Create task
        await client.post("/tasks", json={
            "id": "task_expire_test_01",
            "stage": "research",
            "stage_order": 1,
            "kind": "text",
            "spec": "Task to test lease timeout"
        })

        # Crashed worker claims with 1 second lease
        claim1 = await client.post("/tasks/task_expire_test_01/claim", json={"worker_id": "crashed_worker", "lease_seconds": 1})
        assert claim1.status_code == 200

        # Wait for lease to expire
        await asyncio.sleep(1.5)

        # 1. Recovery worker should be able to claim expired task directly
        claim2 = await client.post("/tasks/task_expire_test_01/claim", json={"worker_id": "recovery_worker", "lease_seconds": 60})
        assert claim2.status_code == 200
        assert claim2.json()["task"]["owner_worker_id"] == "recovery_worker"

        # 2. Test supervisor cycle lease reclamation
        # Set lease in past manually in db
        async with aiosqlite.connect(str(settings.DATABASE_PATH)) as db:
            past_iso = "2020-01-01T00:00:00Z"
            await db.execute("UPDATE tasks SET lease_expires_at = ? WHERE id = 'task_expire_test_01'", (past_iso,))
            await db.commit()

        stats = await run_supervisor_cycle()
        assert stats["reclaimed_tasks"] >= 1

        # Verify task is back to pending
        task_check = await client.get("/tasks/task_expire_test_01")
        assert task_check.json()["status"] == "pending"
        assert task_check.json()["owner_worker_id"] is None

async def test_lease_renewal_heartbeat():
    """
    Test that an active worker can extend its task lease before expiration.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver/api/v1") as client:
        await client.post("/workers/register", json={
            "id": "active_worker",
            "provider": "gemini_free",
            "node_id": "node-01",
            "nickname": "Active Worker",
            "capabilities": ["writing"]
        })

        await client.post("/tasks", json={
            "id": "task_renew_01",
            "stage": "draft",
            "stage_order": 1,
            "kind": "text",
            "spec": "Long running draft task"
        })

        claim = await client.post("/tasks/task_renew_01/claim", json={"worker_id": "active_worker", "lease_seconds": 10})
        assert claim.status_code == 200
        claim_token = claim.json()["claim_token"]
        orig_exp = claim.json()["lease_expires_at"]

        # Renew lease
        renew = await client.post("/tasks/task_renew_01/renew-lease", json={
            "worker_id": "active_worker",
            "claim_token": claim_token,
            "lease_seconds": 600
        })
        assert renew.status_code == 200
        new_exp = renew.json()["lease_expires_at"]
        assert new_exp > orig_exp
