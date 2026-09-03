from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from server.core.config import settings
from server.core.database import init_db
from server.main import app


@pytest_asyncio.fixture(autouse=True)
async def setup_test_db(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(settings, "DATABASE_PATH", tmp_path / "health.db")
    monkeypatch.setattr(settings, "DATA_DIR", tmp_path)
    await init_db()


@pytest.mark.asyncio
async def test_health_endpoints_and_request_correlation():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        live = await client.get("/health/live")
        ready = await client.get("/health/ready", headers={"X-Request-ID": "health-check-1"})

    assert live.status_code == 200
    assert live.json()["status"] == "ok"
    assert ready.status_code == 200
    assert ready.json()["status"] == "ready"
    assert ready.headers["X-Request-ID"] == "health-check-1"


@pytest.mark.asyncio
async def test_metrics_endpoint_exposes_request_counters():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        await client.get("/health/live")
        metrics = await client.get("/metrics")

    assert metrics.status_code == 200
    assert "orchestrator_http_requests_total" in metrics.text
    assert 'path="/health/live"' in metrics.text
