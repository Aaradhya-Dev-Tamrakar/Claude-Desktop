"""Unit tests for CopilotHeadlessAdapter in Claude-Desktop."""

import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from pathlib import Path
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
    assert adapter.enable_tools is True


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


@pytest.mark.asyncio
async def test_copilot_headless_sandboxed_tools(tmp_path):
    adapter = CopilotHeadlessAdapter(
        "copilot-1",
        "Worker",
        "tok",
        workspace_root=tmp_path,
    )

    # Test write_file
    res_write = await adapter._execute_tool("write_file", {"path": "hello.txt", "content": "Hello World!\nSecond line"})
    assert res_write["success"] is True
    assert (tmp_path / "hello.txt").exists()

    # Test read_file
    res_read = await adapter._execute_tool("read_file", {"path": "hello.txt", "offset": 1, "limit": 2})
    assert res_read["success"] is True
    assert "Hello World!" in res_read["content"]
    assert res_read["total_lines"] == 2


@pytest.mark.asyncio
async def test_copilot_headless_tool_calling_loop(tmp_path):
    adapter = CopilotHeadlessAdapter(
        "copilot-1",
        "Agent",
        "tok",
        workspace_root=tmp_path,
        enable_tools=True,
    )

    token_resp = MagicMock(spec=httpx.Response)
    token_resp.status_code = 200
    token_resp.json.return_value = {
        "token": "tid=session",
        "expires_at": 9999999999,
        "endpoints": {"api": "https://api.githubcopilot.com"},
    }

    # Turn 1: model returns tool call to write a file
    turn1_resp = MagicMock(spec=httpx.Response)
    turn1_resp.status_code = 200
    turn1_resp.json.return_value = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call_123",
                            "type": "function",
                            "function": {
                                "name": "write_file",
                                "arguments": json.dumps({"path": "output.txt", "content": "Agent created this file"}),
                            },
                        }
                    ],
                }
            }
        ],
        "model": "gpt-4o",
        "usage": {"total_tokens": 100},
    }

    # Turn 2: model returns final text summary after tool execution
    turn2_resp = MagicMock(spec=httpx.Response)
    turn2_resp.status_code = 200
    turn2_resp.json.return_value = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "File output.txt has been written successfully.",
                }
            }
        ],
        "model": "gpt-4o",
        "usage": {"total_tokens": 80},
    }

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get, \
         patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_get.return_value = token_resp
        mock_post.side_effect = [turn1_resp, turn2_resp]

        res = await adapter.execute_task(
            task_id="task_tool_loop_01",
            spec="Create output.txt with agent content",
            stage="code",
            context={},
        )

        assert res["success"] is True
        assert (tmp_path / "output.txt").exists()
        assert (tmp_path / "output.txt").read_text(encoding="utf-8") == "Agent created this file"
        assert "File output.txt has been written" in res["result_text"]
        assert res["tokens_used"] == 180
