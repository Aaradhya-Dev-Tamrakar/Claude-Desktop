"""
Copilot CLI Adapter: Autonomous Subprocess Adapter for GitHub Copilot CLI (copilot.exe).
Executes non-interactive agent workflows in autopilot mode with local sandbox tools,
workspace isolation, and JSON usage metrics telemetry.
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

from client.adapters.base_adapter import BaseWorkerAdapter


class CopilotCLIAdapter(BaseWorkerAdapter):
    """
    Drives local GitHub Copilot CLI (v1.0+) via headless non-interactive execution:
    `copilot -p "<prompt>" --autopilot --allow-all --no-ask-user --usage-output-file <json>`
    """

    DEFAULT_CAPABILITIES = ["code", "refactor", "unit_test", "research", "draft", "writing"]

    def __init__(
        self,
        worker_id: str,
        nickname: str,
        copilot_path: str | None = None,
        worktree: str | None = None,
        capabilities: list[str] | None = None,
        timeout: float = 180.0,
        max_autopilot_continues: int = 5,
        model: str | None = None,
        github_token: str | None = None,
        copilot_home: str | Path | None = None,
        max_ai_credits: int | None = None,
    ):
        caps = capabilities or self.DEFAULT_CAPABILITIES
        super().__init__(worker_id, nickname, caps)
        self.copilot_path = copilot_path or self._resolve_copilot_binary()
        self.worktree = Path(worktree).resolve() if worktree else None
        self.timeout = timeout
        self.max_autopilot_continues = max_autopilot_continues
        self.model = model
        self.github_token = github_token
        self.copilot_home = Path(copilot_home).resolve() if copilot_home else None
        self.max_ai_credits = max_ai_credits

    @staticmethod
    def _resolve_copilot_binary() -> str:
        """Finds copilot CLI binary on system PATH or standard WinGet installation path."""
        found = shutil.which("copilot")
        if found:
            return found

        # Fallback to standard Windows WinGet install location
        local_app_data = os.getenv("LOCALAPPDATA", "")
        if local_app_data:
            winget_pattern = Path(local_app_data) / "Microsoft" / "WinGet" / "Packages"
            if winget_pattern.exists():
                for p in winget_pattern.glob("*GitHub.Copilot*"):
                    candidate = p / "copilot.exe"
                    if candidate.is_file():
                        return str(candidate)

        return "copilot"

    async def check_health(self) -> bool:
        """Health check returns True if copilot executable is present and returns version code 0."""
        try:
            proc = await asyncio.create_subprocess_exec(
                self.copilot_path,
                "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=10.0)
            return proc.returncode == 0 and b"Copilot CLI" in stdout
        except Exception:
            return False

    def build_cli_command(self, prompt: str, usage_file: str | None = None) -> list[str]:
        """Constructs non-interactive CLI argument vector."""
        cmd = [
            self.copilot_path,
            "-p",
            prompt,
            "--autopilot",
            "--allow-all",
            "--no-ask-user",
            "--no-color",
            "--no-custom-instructions",
            "--max-autopilot-continues",
            str(self.max_autopilot_continues),
        ]

        if self.max_ai_credits is not None:
            cmd.extend(["--max-ai-credits", str(self.max_ai_credits)])

        if self.model:
            cmd.extend(["--model", self.model])

        if self.worktree:
            cmd.extend(["--worktree", str(self.worktree)])

        if usage_file:
            cmd.extend(["--usage-output-file", usage_file])

        return cmd

    async def execute_task(
        self,
        task_id: str,
        spec: str,
        stage: str,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Executes a task specification non-interactively using copilot CLI autopilot mode.
        Captures exit codes, stdout/stderr, and parses usage JSON statistics.
        """
        prompt = (
            f"TASK ID: {task_id}\n"
            f"STAGE: {stage}\n\n"
            f"SPECIFICATION:\n{spec}"
        )
        if context:
            prompt += f"\n\nCONTEXT:\n{json.dumps(context, indent=2)}"

        usage_tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
        usage_tmp_path = Path(usage_tmp.name)
        usage_tmp.close()

        cmd = self.build_cli_command(prompt, usage_file=str(usage_tmp_path))

        cwd = str(self.worktree) if self.worktree and self.worktree.exists() else None

        # Build isolated environment for child process
        child_env = os.environ.copy()
        if self.github_token:
            child_env["COPILOT_GITHUB_TOKEN"] = self.github_token
        if self.copilot_home:
            self.copilot_home.mkdir(parents=True, exist_ok=True)
            child_env["COPILOT_HOME"] = str(self.copilot_home)

        proc = None
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=cwd,
                env=child_env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(),
                timeout=self.timeout,
            )

            stdout_str = stdout_bytes.decode("utf-8", errors="replace").strip()
            stderr_str = stderr_bytes.decode("utf-8", errors="replace").strip()

            # Parse usage statistics if file generated
            usage_data: dict[str, Any] = {}
            if usage_tmp_path.exists() and usage_tmp_path.stat().st_size > 0:
                try:
                    usage_data = json.loads(usage_tmp_path.read_text(encoding="utf-8"))
                except Exception:
                    usage_data = {}

            tokens_used = usage_data.get("total_tokens", usage_data.get("tokens", 0))
            model_used = usage_data.get("model", self.model or "copilot-cli-autopilot")

            if proc.returncode == 0:
                return {
                    "success": True,
                    "summary": f"Completed {stage} via Copilot CLI (autopilot)",
                    "result_text": stdout_str if stdout_str else f"Task {task_id} completed successfully.",
                    "model_used": model_used,
                    "tokens_used": tokens_used,
                    "error": None,
                }
            else:
                return {
                    "success": False,
                    "summary": f"Copilot CLI exited with code {proc.returncode}",
                    "result_text": stdout_str,
                    "model_used": model_used,
                    "tokens_used": tokens_used,
                    "error": f"CLI_EXIT_{proc.returncode}: {stderr_str[:300] if stderr_str else 'Command failed'}",
                }

        except asyncio.TimeoutError:
            if proc:
                try:
                    proc.kill()
                    await proc.wait()
                except Exception:
                    pass
            return {
                "success": False,
                "summary": f"Copilot CLI timed out after {self.timeout}s",
                "result_text": "",
                "model_used": self.model or "copilot-cli",
                "tokens_used": 0,
                "error": f"TIMEOUT: Exceeded {self.timeout}s execution window",
            }
        except Exception as e:
            if proc:
                try:
                    proc.kill()
                    await proc.wait()
                except Exception:
                    pass
            return {
                "success": False,
                "summary": "Copilot CLI execution encountered an exception",
                "result_text": "",
                "model_used": self.model or "copilot-cli",
                "tokens_used": 0,
                "error": f"SUBPROCESS_ERROR: {e}",
            }
        finally:
            if usage_tmp_path.exists():
                try:
                    usage_tmp_path.unlink()
                except Exception:
                    pass
