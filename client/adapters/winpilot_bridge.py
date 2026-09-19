"""
WinPilot Bridge: High-level Python bridge connecting Claude-Desktop orchestrator
and workers to the WinPilot desktop automation engine (windows-pilot).

Enforces batched sequential dispatch via an async lock to guarantee zero focus-stealing
and zero clipboard races across concurrent desktop workers.
"""

from __future__ import annotations

import asyncio
import collections
import datetime
import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger("winpilot_bridge")

DEFAULT_WINPILOT_EXE = Path("F:/Aaradhya-Dev-Tamrakar/windows-pilot/.venv/Scripts/winpilot.exe")

# Global lock guaranteeing only ONE worker interacts with the OS UI at any millisecond
_WINPILOT_UI_LOCK = asyncio.Lock()


class WinPilotBridge:
    """Async bridge to WinPilot CLI with an in-memory clipboard history buffer."""

    def __init__(self, winpilot_exe: Path | str | None = None):
        if winpilot_exe:
            self.exe = Path(winpilot_exe)
        elif DEFAULT_WINPILOT_EXE.exists():
            self.exe = DEFAULT_WINPILOT_EXE
        else:
            self.exe = Path("winpilot")

        # In-memory clipboard history ring buffer (last 50 payloads)
        self.history: collections.deque[dict[str, Any]] = collections.deque(maxlen=50)

    async def _run_cmd(self, *args: str) -> tuple[int, str, str]:
        """Execute a winpilot CLI command asynchronously."""
        cmd = [str(self.exe), *args]
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            return proc.returncode or 0, stdout.decode("utf-8", errors="replace"), stderr.decode("utf-8", errors="replace")
        except Exception as e:
            logger.error("Failed to execute winpilot command %s: %s", cmd, e)
            return 1, "", str(e)

    async def focus_window(self, target: str = "Claude") -> bool:
        """Brings target window to foreground, uncloaking from virtual desktops."""
        code, out, _ = await self._run_cmd("focus", target)
        return code == 0

    async def set_model(self, target: str, model: str) -> bool:
        """Sets active model in Claude Desktop via WinPilot UIA automation."""
        code, out, _ = await self._run_cmd("recipe", "claude-model", "-m", model, "-t", target)
        return code == 0

    async def set_effort(self, target: str, effort: str) -> bool:
        """Sets response effort level (low, medium, high, extra, max)."""
        code, out, _ = await self._run_cmd("recipe", "claude-effort", "-e", effort, "-t", target)
        return code == 0

    async def toggle_thinking(self, target: str = "Claude") -> bool:
        """Toggles extended thinking mode via Ctrl+Shift+E."""
        code, out, _ = await self._run_cmd("recipe", "claude-thinking", "-t", target)
        return code == 0

    async def send_prompt(self, target: str, prompt: str, submit: bool = True) -> bool:
        """Injects prompt via clipboard and optionally presses Enter."""
        args = ["recipe", "claude-prompt", prompt, "-t", target]
        if not submit:
            args.append("--no-submit")
        code, _, _ = await self._run_cmd(*args)
        return code == 0

    async def detect_cooldown(self, target: str = "Claude") -> dict[str, Any]:
        """
        Inspects Claude Desktop UI to detect 90% warning or 100% cooldown.
        Extracts exact reset timestamp if available.
        """
        code, out, _ = await self._run_cmd("recipe", "claude-cooldown", "-t", target)
        in_cooldown = "cooldown active" in out.lower()
        warning_90 = "warning: approaching limit" in out.lower()

        reset_time = None
        if "reset time:" in out.lower():
            try:
                part = out.split("Reset time:", 1)[1].split("(", 1)[0].strip()
                reset_time = part
            except Exception:
                pass

        return {
            "in_cooldown": in_cooldown,
            "warning_90_pct": warning_90,
            "reset_time": reset_time,
            "raw_output": out.strip(),
        }

    async def batch_setup_and_inject(
        self,
        worker_id: str,
        task_id: str,
        target_window: str,
        prompt: str,
        model: str | None = None,
        effort: str | None = None,
        toggle_thinking: bool = False,
    ) -> dict[str, Any]:
        """
        The Revolving Turnstile: Executes the 1-by-1 physical dispatch sequence under an async lock.
        Guarantees zero focus-stealing and zero clipboard races with other concurrent workers.
        """
        async with _WINPILOT_UI_LOCK:
            record = {
                "timestamp": datetime.datetime.now().isoformat(),
                "worker_id": worker_id,
                "task_id": task_id,
                "target_window": target_window,
                "model": model,
                "effort": effort,
                "toggle_thinking": toggle_thinking,
                "prompt_snippet": prompt[:80] + ("..." if len(prompt) > 80 else ""),
                "success": False,
            }

            try:
                # 1. Focus target window (uncloaks virtual desktop)
                await self.focus_window(target_window)
                await asyncio.sleep(0.1)

                # 2. Check for pre-existing cooldown before wasting effort
                cd = await self.detect_cooldown(target_window)
                if cd["in_cooldown"]:
                    record["error"] = f"Worker in cooldown until {cd['reset_time']}"
                    self.history.append(record)
                    return {"success": False, "cooldown": True, "reset_time": cd["reset_time"]}

                # 3. Configure Model if specified
                if model:
                    await self.set_model(target_window, model)
                    await asyncio.sleep(0.15)

                # 4. Configure Effort if specified
                if effort:
                    await self.set_effort(target_window, effort)
                    await asyncio.sleep(0.15)

                # 5. Toggle Thinking if requested
                if toggle_thinking:
                    await self.toggle_thinking(target_window)
                    await asyncio.sleep(0.1)

                # 6. Inject Prompt via Unicode Clipboard & Enter
                ok = await self.send_prompt(target_window, prompt, submit=True)
                record["success"] = ok
                self.history.append(record)

                return {
                    "success": ok,
                    "cooldown": False,
                    "worker_id": worker_id,
                    "task_id": task_id,
                }

            except Exception as e:
                logger.error("Error in batch_setup_and_inject for %s: %s", worker_id, e)
                record["error"] = str(e)
                self.history.append(record)
                return {"success": False, "error": str(e)}

    def get_clipboard_history(self, worker_id: str | None = None) -> list[dict[str, Any]]:
        """Query recent dispatch history for a worker or entire fleet."""
        if worker_id:
            return [h for h in self.history if h.get("worker_id") == worker_id]
        return list(self.history)
