"""Unit tests for CopilotHeadlessAdapter in Claude-Desktop."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx

from client.adapters.copilot_headless import CopilotHeadlessAdapter


@pytest.mark.asyncio
async def test_copilot_headless_init():
    adapter = CopilotHeadlessAdapter(
        "copilot-1",
        "Researcher 1",
        "test",
        model="auto",
    )
    assert adapter.worker_id == "copilot-1"
    assert adapter.token == "test"
    assert adapter.model == "auto"


@pytest.mark.asyncio
async def test_copilot_headless_token_from_env(monkeypatch):
    monkeypatch.setenv("COPILOT_TOKEN_2", "envval")
    adapter = CopilotHeadlessAdapter(
        worker_id="copilot-2",
        nickname="Formatter",
        env_token_var="COPILOT_TOKEN_2",
    )
    assert adapter.token == "envval"


@pytest.mark.asyncio
async def test_copilot_headless_token_exchange():
    adapter = CopilotHeadlessAdapter(
        "copilot-1",
        "Researcher",
        "tok",
    )

    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "token": "tid=copilot_session_abc",
        "expires_at": 9999999999,
        "endpoints": {"api": "https://api.githubcopilot.com"},
    }

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_resp
        token = await adapter._get_session_token()

        assert token == "tid=copilot_session_abc"
        assert adapter._api_endpoint == "https://api.githubcopilot.com/chat/completions"


@pytest.mark.asyncio
async def test_copilot_headless_execute_task_success():
    adapter = CopilotHeadlessAdapter(
        "copilot-1",
        "Researcher",
        "tok",
    )

    token_resp = MagicMock(spec=httpx.Response)
    token_resp.status_code = 200
    token_resp.json.return_value = {
        "token": "tid=session",
        "expires_at": 9999999999,
        "endpoints": {"api": "https://api.githubcopilot.com"},
    }

    chat_resp = MagicMock(spec=httpx.Response)
    chat_resp.status_code = 200
    chat_resp.json.return_value = {
        "choices": [
            {"message": {"role": "assistant", "content": "Extracted API endpoints and schemas."}}
        ],
        "model": "gpt-4o-mini-2024-07-18",
        "usage": {"total_tokens": 342},
    }

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get, \
         patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_get.return_value = token_resp
        mock_post.return_value = chat_resp

        res = await adapter.execute_task(
            task_id="task_research_01",
            spec="Scrape endpoints from docs",
            stage="research",
            context={},
        )

        assert res["success"] is True
        assert "Extracted API endpoints" in res["result_text"]
        assert res["model_used"] == "gpt-4o-mini-2024-07-18"
        assert res["tokens_used"] == 342


@pytest.mark.asyncio
async def test_copilot_headless_rate_limit_429():
    adapter = CopilotHeadlessAdapter(
        "copilot-1",
        "Researcher",
        "tok",
    )

    token_resp = MagicMock(spec=httpx.Response)
    token_resp.status_code = 200
    token_resp.json.return_value = {
        "token": "tid=session",
        "expires_at": 9999999999,
        "endpoints": {"api": "https://api.githubcopilot.com"},
    }

    chat_resp = MagicMock(spec=httpx.Response)
    chat_resp.status_code = 429
    chat_resp.text = "Rate limit exceeded"

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get, \
         patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_get.return_value = token_resp
        mock_post.return_value = chat_resp

        res = await adapter.execute_task(
            task_id="task_429",
            spec="Big work",
            stage="research",
            context={},
        )

        assert res["success"] is False
        assert res["error"] == "RATE_LIMIT_429"
