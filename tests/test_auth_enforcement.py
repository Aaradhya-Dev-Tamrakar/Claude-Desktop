from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from server.core.config import settings
from server.core.database import init_db
from server.main import app

@pytest_asyncio.fixture(autouse=True)
async def setup_test_db(tmp_path, monkeypatch):
    test_db = tmp_path / "test_auth.db"
    monkeypatch.setattr(settings, "DATABASE_PATH", test_db)
    monkeypatch.setattr(settings, "DATA_DIR", tmp_path)
    await init_db()
    yield

@pytest.mark.asyncio
async def test_auth_allowed_in_dev_mode_when_no_key_configured(monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")
    monkeypatch.setattr(settings, "API_AUTH_KEY", "")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # GET /api/v1/jobs
        resp = await client.get("/api/v1/jobs")
        assert resp.status_code == 200

        # GET /api/v1/tasks
        resp = await client.get("/api/v1/tasks")
        assert resp.status_code == 200

        # GET /api/v1/workers
        resp = await client.get("/api/v1/workers")
        assert resp.status_code == 200

        # GET /api/v1/memory
        resp = await client.get("/api/v1/memory")
        assert resp.status_code == 200

@pytest.mark.asyncio
async def test_auth_enforced_when_api_key_configured(monkeypatch):
    dummy_auth_val = "x" * 32
    monkeypatch.setattr(settings, "API_AUTH_KEY", dummy_auth_val)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Unauthenticated calls MUST return 401 (including MCP SSE mount)
        for endpoint in ["/api/v1/jobs", "/api/v1/tasks", "/api/v1/workers", "/api/v1/memory", "/mcp/"]:
            unauth = await client.get(endpoint)
            assert unauth.status_code == 401, f"Expected 401 for {endpoint}, got {unauth.status_code}"

        # Invalid token MUST return 401
        invalid = await client.get("/api/v1/jobs", headers={"Authorization": "Bearer invalid-bearer-value"})
        assert invalid.status_code == 401

        invalid_mcp = await client.get("/mcp/", headers={"X-API-Key": "wrong_key"})
        assert invalid_mcp.status_code == 401

        # Valid Bearer token MUST succeed
        valid_bearer = await client.get("/api/v1/jobs", headers={"Authorization": f"Bearer {dummy_auth_val}"})
        assert valid_bearer.status_code == 200

        # Valid X-API-Key header MUST succeed
        valid_header = await client.get("/api/v1/tasks", headers={"X-API-Key": dummy_auth_val})
        assert valid_header.status_code == 200
