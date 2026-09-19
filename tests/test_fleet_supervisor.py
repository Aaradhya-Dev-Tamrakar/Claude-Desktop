from __future__ import annotations

import asyncio
import json
import os
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from pathlib import Path

from client.fleet_supervisor import ROLE_CAPABILITIES, run_worker_loop, create_adapter

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

    mock_adapter = AsyncMock()
    mock_adapter.wait_until_ready.return_value = True
    mock_adapter.cdp_port = 9223

    # Start loop and trigger stop after 0.05s
    loop_task = asyncio.create_task(
        run_worker_loop(
            worker_id="user2",
            nickname="dev83",
            role="researcher",
            provider="claude_desktop_cdp",
            adapter=mock_adapter,
            client=mock_client,
            stop_event=stop_event,
        )
    )

    await asyncio.sleep(0.05)
    stop_event.set()
    await asyncio.wait_for(loop_task, timeout=1.0)

    # Verify registration was attempted
    assert mock_client.post.call_count >= 1

def test_create_adapter_cdp():
    """create_adapter builds a ClaudeDesktopCDPAdapter for CDP entries."""
    inst = {
        "Account": "user1",
        "Nickname": "claude-lead",
        "Provider": "claude_desktop_cdp",
        "CdpPort": 9222,
        "PreferredModel": "claude-3-7-sonnet",
        "ThinkingBudget": 10000,
    }
    adapter = create_adapter(inst)
    assert adapter.worker_id == "user1"
    assert adapter.cdp_port == 9222

def test_create_adapter_copilot_headless():
    """create_adapter builds a CopilotHeadlessAdapter for headless entries."""
    os.environ["TEST_COPILOT_TK"] = "FAKE_TEST_TOKEN_123"
    try:
        inst = {
            "Account": "copilot-1",
            "Nickname": "copilot-researcher",
            "Provider": "copilot_headless",
            "EnvToken": "TEST_COPILOT_TK",
            "PreferredModel": "auto",
        }
        adapter = create_adapter(inst)
        assert adapter.worker_id == "copilot-1"
        assert adapter._raw_github_token == "FAKE_TEST_TOKEN_123"
    finally:
        os.environ.pop("TEST_COPILOT_TK", None)

def test_create_adapter_unknown_provider():
    """create_adapter raises ValueError for unknown providers."""
    with pytest.raises(ValueError, match="Unknown provider"):
        create_adapter({"Account": "x", "Provider": "magic_unicorn"})

@pytest.mark.asyncio
async def test_fleet_lease_renewal_periodically():
    """Verify fleet supervisor issues periodic lease renewals until stopped."""
    from client.fleet_supervisor import renew_task_lease_periodically

    mock_client = AsyncMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_client.post.return_value = mock_resp

    stop_event = asyncio.Event()

    with patch("client.fleet_supervisor.LEASE_RENEWAL_SECONDS", 0.05):
        renewal_task = asyncio.create_task(
            renew_task_lease_periodically(
                client=mock_client,
                worker_id="fleet_worker_01",
                task_id="task_fleet_1",
                claim_token="tk1",
                stop_event=stop_event,
            )
        )

        await asyncio.sleep(0.12)
        stop_event.set()
        await asyncio.wait_for(renewal_task, timeout=1.0)

    assert mock_client.post.call_count >= 1
    call_args = mock_client.post.call_args[0]
    call_kwargs = mock_client.post.call_args[1]
    assert "tasks/task_fleet_1/renew-lease" in call_args[0]
    assert call_kwargs["json"]["worker_id"] == "fleet_worker_01"
    assert call_kwargs["json"]["claim_token"] == "tk1"

