import asyncio
import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from client.adapters.claude_desktop_cdp import ClaudeDesktopCDPAdapter
from client.adapters.claude_desktop_proxy import ClaudeDesktopProxyAdapter

@pytest.mark.asyncio
async def test_cdp_adapter_init():
    adapter = ClaudeDesktopCDPAdapter(worker_id="test_cdp_01", nickname="Claude CDP Test", cdp_port=9222)
    assert adapter.worker_id == "test_cdp_01"
    assert adapter.nickname == "Claude CDP Test"
    assert adapter.cdp_port == 9222
    assert adapter.http_url == "http://127.0.0.1:9222"
    assert "writing" in adapter.capabilities

@pytest.mark.asyncio
async def test_cdp_health_check_success():
    adapter = ClaudeDesktopCDPAdapter("test_w", "Test", cdp_port=9222)
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_get.return_value = mock_resp
        
        healthy = await adapter.check_health()
        assert healthy is True

@pytest.mark.asyncio
async def test_cdp_health_check_failure():
    adapter = ClaudeDesktopCDPAdapter("test_w", "Test", cdp_port=9222)
    with patch("httpx.AsyncClient.get", side_effect=Exception("Connection refused")):
        healthy = await adapter.check_health()
        assert healthy is False

@pytest.mark.asyncio
async def test_cdp_get_page_ws_url():
    adapter = ClaudeDesktopCDPAdapter("test_w", "Test", cdp_port=9222)
    sample_targets = [
        {"type": "background_page", "webSocketDebuggerUrl": "ws://127.0.0.1:9222/devtools/page/bg"},
        {"type": "page", "title": "Claude", "webSocketDebuggerUrl": "ws://127.0.0.1:9222/devtools/page/claude_main"}
    ]
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = sample_targets
        mock_get.return_value = mock_resp
        
        ws_url = await adapter.get_page_ws_url()
        assert ws_url == "ws://127.0.0.1:9222/devtools/page/claude_main"

@pytest.mark.asyncio
async def test_cdp_execute_task_unreachable():
    adapter = ClaudeDesktopCDPAdapter("test_w", "Test", cdp_port=9999)
    with patch.object(adapter, "get_page_ws_url", return_value=None):
        res = await adapter.execute_task("task_001", "write product description", "draft", {})
        assert res["success"] is False
        assert "not reachable" in res["error"]

@pytest.mark.asyncio
async def test_cdp_cooldown_detection_returns_429():
    adapter = ClaudeDesktopCDPAdapter("test_w", "Test", cdp_port=9222)
    
    mock_ws = AsyncMock()
    # Mock WebSocket connect
    with patch.object(adapter, "get_page_ws_url", return_value="ws://127.0.0.1:9222/page/1"), \
         patch("websockets.connect") as mock_ws_connect, \
         patch.object(adapter, "_send_cdp_command", return_value={"result": {}}), \
         patch.object(adapter, "_check_cooldown_banner", return_value=True):
        
        mock_ws_connect.return_value.__aenter__.return_value = mock_ws
        
        res = await adapter.execute_task("task_002", "spec", "research", {})
        assert res["success"] is False
        assert res["error"] == "RATE_LIMIT_429"

@pytest.mark.asyncio
async def test_cdp_execute_task_flow_success():
    adapter = ClaudeDesktopCDPAdapter("test_w", "Test", cdp_port=9222)
    
    mock_ws = AsyncMock()
    with patch.object(adapter, "get_page_ws_url", return_value="ws://127.0.0.1:9222/page/1"), \
         patch("websockets.connect") as mock_ws_connect, \
         patch.object(adapter, "_send_cdp_command", return_value={"result": {}}), \
         patch.object(adapter, "_check_cooldown_banner", return_value=False), \
         patch.object(adapter, "_start_new_chat", return_value=None), \
         patch.object(adapter, "_inject_prompt_and_send", return_value=True), \
         patch.object(adapter, "_wait_for_generation_complete", return_value={"success": True, "result_text": "High quality generated product draft"}):
        
        mock_ws_connect.return_value.__aenter__.return_value = mock_ws
        
        res = await adapter.execute_task("task_003", "Create description for SKU-123", "draft", {})
        assert res["success"] is True
        assert "High quality generated product draft" in res["result_text"]
        assert "draft" in res["summary"]

@pytest.mark.asyncio
async def test_claude_proxy_delegation_to_cdp():
    proxy = ClaudeDesktopProxyAdapter("worker_claude", "Claude Worker", cdp_port=9222)
    with patch.object(proxy._cdp_adapter, "check_health", return_value=True), \
         patch.object(proxy._cdp_adapter, "execute_task", return_value={"success": True, "result_text": "CDP text", "summary": "CDP summary", "error": None}):
        
        res = await proxy.execute_task("task_004", "spec", "qa", {})
        assert res["success"] is True
        assert res["result_text"] == "CDP text"
