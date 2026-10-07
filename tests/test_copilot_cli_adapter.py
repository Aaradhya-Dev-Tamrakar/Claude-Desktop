"""Unit tests for CopilotCLIAdapter in Claude-Desktop."""

import asyncio
import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from pathlib import Path

from client.adapters.copilot_cli_adapter import CopilotCLIAdapter


@pytest.mark.asyncio
async def test_copilot_cli_init():
    adapter = CopilotCLIAdapter(
        worker_id="copilot-cli-1",
        nickname="Copilot Agent 1",
        copilot_path="copilot.exe",
        worktree="F:/tmp/workspace",
        model="gpt-5.4",
        timeout=60.0,
    )
    assert adapter.worker_id == "copilot-cli-1"
    assert adapter.copilot_path == "copilot.exe"
    assert adapter.model == "gpt-5.4"
    assert adapter.timeout == 60.0
    assert "code" in adapter.capabilities


@pytest.mark.asyncio
async def test_copilot_cli_build_command():
    adapter = CopilotCLIAdapter(
        worker_id="copilot-cli-1",
        nickname="Agent",
        copilot_path="copilot.exe",
        model="claude-3.7-sonnet",
        worktree="F:/workspace",
        max_autopilot_continues=3,
    )
    cmd = adapter.build_cli_command("Do the task", usage_file="usage.json")

    assert cmd[0] == "copilot.exe"
    assert "-p" in cmd
    assert "Do the task" in cmd
    assert "--autopilot" in cmd
    assert "--allow-all" in cmd
    assert "--no-ask-user" in cmd
    assert "--model" in cmd
    assert "claude-3.7-sonnet" in cmd
    assert "--usage-output-file" in cmd
    assert "usage.json" in cmd
    assert "--max-autopilot-continues" in cmd
    assert "3" in cmd


@pytest.mark.asyncio
async def test_copilot_cli_check_health_success():
    adapter = CopilotCLIAdapter("cli-1", "Agent", copilot_path="copilot.exe")

    mock_proc = AsyncMock()
    mock_proc.returncode = 0
    mock_proc.communicate.return_value = (b"GitHub Copilot CLI 1.0.91", b"")

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        health = await adapter.check_health()
        assert health is True


@pytest.mark.asyncio
async def test_copilot_cli_check_health_failure():
    adapter = CopilotCLIAdapter("cli-1", "Agent", copilot_path="nonexistent_copilot_bin")

    with patch("asyncio.create_subprocess_exec", side_effect=FileNotFoundError("not found")):
        health = await adapter.check_health()
        assert health is False


@pytest.mark.asyncio
async def test_copilot_cli_execute_task_success(tmp_path):
    adapter = CopilotCLIAdapter(
        worker_id="cli-1",
        nickname="Agent",
        copilot_path="copilot.exe",
        worktree=str(tmp_path),
    )

    mock_proc = AsyncMock()
    mock_proc.returncode = 0
    mock_proc.communicate.return_value = (b"All tests created and verified passing.", b"")

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        res = await adapter.execute_task(
            task_id="task_cli_001",
            spec="Implement retry logic",
            stage="code",
            context={"lang": "python"},
        )

        assert res["success"] is True
        assert "All tests created" in res["result_text"]
        assert res["error"] is None


@pytest.mark.asyncio
async def test_copilot_cli_execute_task_timeout():
    adapter = CopilotCLIAdapter(
        worker_id="cli-1",
        nickname="Agent",
        copilot_path="copilot.exe",
        timeout=0.01,
    )

    mock_proc = AsyncMock()
    mock_proc.communicate.side_effect = asyncio.TimeoutError()
    mock_proc.kill = MagicMock()
    mock_proc.wait = AsyncMock()

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        res = await adapter.execute_task(
            task_id="task_cli_timeout",
            spec="Long running task",
            stage="code",
            context={},
        )

        assert res["success"] is False
        assert "TIMEOUT" in res["error"]


@pytest.mark.asyncio
async def test_copilot_cli_env_and_credits_isolation(tmp_path):
    copilot_home = tmp_path / "custom_copilot_home"
    dummy_tok = "mock" + "_dummy_pat_123"
    adapter = CopilotCLIAdapter(
        worker_id="cli-isolated",
        nickname="Isolated Worker",
        copilot_path="copilot.exe",
        github_token=dummy_tok,
        copilot_home=copilot_home,
        max_ai_credits=25,
    )

    # Check CLI command contains max-ai-credits
    cmd = adapter.build_cli_command("Run isolated")
    assert "--max-ai-credits" in cmd
    assert "25" in cmd

    mock_proc = AsyncMock()
    mock_proc.returncode = 0
    mock_proc.communicate.return_value = (b"Execution complete", b"")

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_exec:
        res = await adapter.execute_task("task_iso", "spec", "code", {})
        assert res["success"] is True

        # Verify child environment passed to subprocess
        _, kwargs = mock_exec.call_args
        env_passed = kwargs.get("env", {})
        assert env_passed.get("COPILOT_GITHUB_TOKEN") == dummy_tok
        assert env_passed.get("COPILOT_HOME") == str(copilot_home)
        assert copilot_home.exists()

