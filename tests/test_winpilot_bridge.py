"""Unit tests for WinPilotBridge in Claude-Desktop."""

import pytest
from unittest.mock import AsyncMock, patch

from client.adapters.winpilot_bridge import WinPilotBridge


@pytest.mark.asyncio
async def test_winpilot_bridge_initialization():
    bridge = WinPilotBridge()
    assert bridge.exe is not None
    assert len(bridge.history) == 0


@pytest.mark.asyncio
async def test_winpilot_bridge_focus():
    bridge = WinPilotBridge()
    with patch.object(bridge, "_run_cmd", new_callable=AsyncMock) as mock_cmd:
        mock_cmd.return_value = (0, "Window focused", "")
        ok = await bridge.focus_window("Claude")
        assert ok is True
        mock_cmd.assert_called_once_with("focus", "Claude")


@pytest.mark.asyncio
async def test_winpilot_bridge_set_model_and_effort():
    bridge = WinPilotBridge()
    with patch.object(bridge, "_run_cmd", new_callable=AsyncMock) as mock_cmd:
        mock_cmd.return_value = (0, "Success", "")
        m_ok = await bridge.set_model("Claude", "sonnet")
        e_ok = await bridge.set_effort("Claude", "high")
        t_ok = await bridge.toggle_thinking("Claude")

        assert m_ok is True
        assert e_ok is True
        assert t_ok is True


@pytest.mark.asyncio
async def test_winpilot_bridge_detect_cooldown():
    bridge = WinPilotBridge()
    with patch.object(bridge, "_run_cmd", new_callable=AsyncMock) as mock_cmd:
        mock_cmd.return_value = (0, "Cooldown active! Reset time: 3:15 PM (Banner: Try again)", "")
        cd = await bridge.detect_cooldown("Claude")

        assert cd["in_cooldown"] is True
        assert cd["reset_time"] == "3:15 PM"


@pytest.mark.asyncio
async def test_winpilot_bridge_batch_setup_and_inject():
    bridge = WinPilotBridge()
    with patch.object(bridge, "focus_window", new_callable=AsyncMock) as mock_focus, \
         patch.object(bridge, "detect_cooldown", new_callable=AsyncMock) as mock_cd, \
         patch.object(bridge, "set_model", new_callable=AsyncMock) as mock_model, \
         patch.object(bridge, "set_effort", new_callable=AsyncMock) as mock_effort, \
         patch.object(bridge, "toggle_thinking", new_callable=AsyncMock) as mock_thinking, \
         patch.object(bridge, "send_prompt", new_callable=AsyncMock) as mock_send:

        mock_focus.return_value = True
        mock_cd.return_value = {"in_cooldown": False, "reset_time": None}
        mock_model.return_value = True
        mock_effort.return_value = True
        mock_thinking.return_value = True
        mock_send.return_value = True

        res = await bridge.batch_setup_and_inject(
            worker_id="user1",
            task_id="task_001",
            target_window="Claude",
            prompt="Analyze architectural AST",
            model="sonnet",
            effort="medium",
            toggle_thinking=True,
        )

        assert res["success"] is True
        assert res["worker_id"] == "user1"
        assert res["task_id"] == "task_001"

        # Verify history was recorded
        history = bridge.get_clipboard_history("user1")
        assert len(history) == 1
        assert history[0]["task_id"] == "task_001"
        assert history[0]["model"] == "sonnet"
