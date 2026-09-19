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

@pytest.mark.asyncio
async def test_cdp_eval_js_exception():
    adapter = ClaudeDesktopCDPAdapter("test_w", "Test", cdp_port=9222)
    mock_ws = AsyncMock()
    with patch.object(adapter, "_send_cdp_command", return_value={
        "result": {
            "exceptionDetails": {"text": "SyntaxError: Unexpected token"}
        }
    }):
        with pytest.raises(RuntimeError, match="CDP JavaScript evaluation failed"):
            await adapter._eval_js(mock_ws, "invalid.js.expression()")

@pytest.mark.asyncio
async def test_cdp_ui_error_banner_handling():
    adapter = ClaudeDesktopCDPAdapter("test_w", "Test", cdp_port=9222)
    mock_ws = AsyncMock()
    with patch.object(adapter, "_check_cooldown_banner", return_value=False), \
         patch.object(adapter, "_eval_js", return_value="Message failed to send"):
        
        res = await adapter._wait_for_generation_complete(mock_ws)
        assert res["success"] is False
        assert "Claude UI Error" in res["error"]

@pytest.mark.asyncio
async def test_cdp_adapter_custom_model_and_thinking_init():
    adapter = ClaudeDesktopCDPAdapter(
        worker_id="user6",
        nickname="QA Reviewer",
        cdp_port=9227,
        preferred_model="claude-3-7-sonnet",
        thinking_budget=16000
    )
    assert adapter.preferred_model == "claude-3-7-sonnet"
    assert adapter.thinking_budget == 16000
    assert adapter.cdp_port == 9227

@pytest.mark.asyncio
async def test_cdp_wait_until_ready_success():
    adapter = ClaudeDesktopCDPAdapter("test_ready", "Test", cdp_port=9222)
    mock_ws = AsyncMock()
    with patch.object(adapter, "get_page_ws_url", return_value="ws://127.0.0.1:9222/page/1"), \
         patch("websockets.connect") as mock_ws_connect, \
         patch.object(adapter, "_send_cdp_command", return_value={"result": {}}), \
         patch.object(adapter, "_dismiss_overlays", return_value=None), \
         patch.object(adapter, "_eval_js", return_value=True):
        
        mock_ws_connect.return_value.__aenter__.return_value = mock_ws
        ready = await adapter.wait_until_ready(timeout=2.0)
        assert ready is True

@pytest.mark.asyncio
async def test_cdp_wait_until_ready_timeout():
    adapter = ClaudeDesktopCDPAdapter("test_ready_to", "Test", cdp_port=9222)
    with patch.object(adapter, "get_page_ws_url", return_value=None):
        ready = await adapter.wait_until_ready(timeout=0.1)
        assert ready is False
@pytest.mark.asyncio
async def test_cdp_execute_task_via_winpilot_bridge():
    """Verify that when winpilot_bridge is present, batch_setup_and_inject is called."""
    mock_bridge = AsyncMock()
    mock_bridge.batch_setup_and_inject.return_value = {
        "success": True,
        "cooldown": False,
        "worker_id": "user1",
        "task_id": "task_wp_1",
    }

    adapter = ClaudeDesktopCDPAdapter(
        worker_id="user1",
        nickname="Claude Lead",
        cdp_port=9222,
        preferred_model="claude-3-7-sonnet",
        thinking_budget=10000,
        winpilot_bridge=mock_bridge,
        window_title="Claude - Claude Lead",
    )

    mock_ws = AsyncMock()
    with patch.object(adapter, "get_page_ws_url", return_value="ws://127.0.0.1:9222/page/1"), \
         patch("websockets.connect") as mock_ws_connect, \
         patch.object(adapter, "_send_cdp_command", return_value={"result": {}}), \
         patch.object(adapter, "_check_cooldown_banner", return_value=False), \
         patch.object(adapter, "_start_new_chat", return_value=None), \
         patch.object(adapter, "_dismiss_overlays", return_value=None), \
         patch.object(adapter, "_ensure_model_and_thinking", return_value=None), \
         patch.object(adapter, "_wait_for_generation_complete", return_value={"success": True, "result_text": "Response via WinPilot injection"}):

        mock_ws_connect.return_value.__aenter__.return_value = mock_ws

        res = await adapter.execute_task("task_wp_1", "Write outline", "draft", {})
        assert res["success"] is True
        assert res["result_text"] == "Response via WinPilot injection"

        mock_bridge.batch_setup_and_inject.assert_called_once()
        call_kwargs = mock_bridge.batch_setup_and_inject.call_args[1]
        assert call_kwargs["worker_id"] == "user1"
        assert call_kwargs["task_id"] == "task_wp_1"
        assert call_kwargs["target_window"] == "Claude - Claude Lead"
        assert call_kwargs["model"] == "sonnet"
        assert call_kwargs["effort"] == "high"
        assert call_kwargs["toggle_thinking"] is True


@pytest.mark.asyncio
async def test_cdp_execute_task_winpilot_cooldown():
    """Verify that if WinPilot detects cooldown, execute_task returns RATE_LIMIT_429."""
    mock_bridge = AsyncMock()
    mock_bridge.batch_setup_and_inject.return_value = {
        "success": False,
        "cooldown": True,
        "reset_time": "18:00",
    }

    adapter = ClaudeDesktopCDPAdapter(
        worker_id="user1",
        nickname="Claude Lead",
        cdp_port=9222,
        winpilot_bridge=mock_bridge,
    )

    mock_ws = AsyncMock()
    with patch.object(adapter, "get_page_ws_url", return_value="ws://127.0.0.1:9222/page/1"), \
         patch("websockets.connect") as mock_ws_connect, \
         patch.object(adapter, "_send_cdp_command", return_value={"result": {}}), \
         patch.object(adapter, "_check_cooldown_banner", return_value=False), \
         patch.object(adapter, "_start_new_chat", return_value=None), \
         patch.object(adapter, "_dismiss_overlays", return_value=None), \
         patch.object(adapter, "_ensure_model_and_thinking", return_value=None):

        mock_ws_connect.return_value.__aenter__.return_value = mock_ws

        res = await adapter.execute_task("task_wp_cd", "Write outline", "draft", {})
        assert res["success"] is False
        assert res["error"] == "RATE_LIMIT_429"
        assert "18:00" in res["summary"]
