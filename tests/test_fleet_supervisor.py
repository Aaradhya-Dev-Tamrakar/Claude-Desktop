from __future__ import annotations

import asyncio
import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from pathlib import Path

from client.fleet_supervisor import ROLE_CAPABILITIES, run_worker_loop

@pytest.mark.asyncio
async def test_role_capabilities_mapping():
    assert "research" in ROLE_CAPABILITIES["researcher"]
    assert "writing" in ROLE_CAPABILITIES["writer"]
    assert "qa" in ROLE_CAPABILITIES["qa_reviewer"]
    assert "coordination" in ROLE_CAPABILITIES["orchestrator"]

@pytest.mark.asyncio
async def test_worker_loop_registration_and_exit_on_stop():
    mock_client = AsyncMock()
    # Mock registration response
    mock_reg_resp = MagicMock()
    mock_reg_resp.status_code = 201
    mock_client.post.return_value = mock_reg_resp

    # Mock tasks response
    mock_task_resp = MagicMock()
    mock_task_resp.status_code = 200
    mock_task_resp.json.return_value = []
    mock_client.get.return_value = mock_task_resp

    stop_event = asyncio.Event()

    with patch("client.fleet_supervisor.ClaudeDesktopCDPAdapter") as mock_adapter_cls:
        mock_adapter = AsyncMock()
        mock_adapter.wait_until_ready.return_value = True
        mock_adapter_cls.return_value = mock_adapter

        # Start loop and trigger stop after 0.1s
        loop_task = asyncio.create_task(
            run_worker_loop(
                worker_id="user2",
                nickname="dev83",
                role="researcher",
                cdp_port=9223,
                preferred_model="claude-3-5-haiku",
                thinking_budget=0,
                client=mock_client,
                stop_event=stop_event,
            )
        )

        await asyncio.sleep(0.05)
        stop_event.set()
        await asyncio.wait_for(loop_task, timeout=1.0)

        # Verify adapter was initialized with correct port and model
        mock_adapter_cls.assert_called_once_with(
            worker_id="user2",
            nickname="dev83",
            cdp_port=9223,
            preferred_model="claude-3-5-haiku",
            thinking_budget=0,
        )
        assert mock_client.post.call_count >= 1
