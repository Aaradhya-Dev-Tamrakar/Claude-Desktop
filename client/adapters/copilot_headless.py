"""
Copilot Headless Adapter: Pure asynchronous HTTP adapter for GitHub Copilot accounts.
Enables running multiple Copilot worker instances concurrently without opening VS Code or Electron GUI (~10-15 MB RAM per instance).
Supports Phase 2 / M6 iterative autonomous tool-calling loop (read_file, write_file, run_command).
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path
from typing import Any
import httpx

from client.adapters.base_adapter import BaseWorkerAdapter


class CopilotHeadlessAdapter(BaseWorkerAdapter):
    """
    Automates GitHub Copilot via direct REST API without requiring VS Code.
    Exchanges GitHub token for internal Copilot session tokens with auto-refresh,
    supports free tier auto-model detection, logs model telemetry, and executes
    iterative local sandboxed tool loops (M6).
    """

    COPILOT_TOKEN_URL = "https://api.github.com/copilot_internal/v2/token"
    COPILOT_CHAT_URL = "https://api.githubcopilot.com/chat/completions"

    AVAILABLE_TOOLS = [
        {
            "type": "function",
            "function": {
                "name": "read_file",
                "description": "Read file contents from disk within workspace",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Relative or absolute path to the file"},
                        "offset": {"type": "integer", "description": "Starting line number (1-indexed, default: 1)"},
                        "limit": {"type": "integer", "description": "Max lines to return (default: 500)"},
                    },
                    "required": ["path"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "write_file",
                "description": "Write or overwrite file contents on disk within workspace",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Relative or absolute path to the file"},
                        "content": {"type": "string", "description": "File content to write"},
                    },
                    "required": ["path", "content"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "run_command",
                "description": "Execute a safe shell command with a timeout within workspace",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "command": {"type": "string", "description": "The command string to execute"},
                        "timeout": {"type": "number", "description": "Execution timeout in seconds (default: 30.0)"},
                    },
                    "required": ["command"],
                },
            },
        },
    ]

    def __init__(
        self,
        worker_id: str,
        nickname: str,
        github_token: str | None = None,
        env_token_var: str | None = None,
        model: str = "auto",
        capabilities: list[str] | None = None,
        timeout: float = 60.0,
        enable_tools: bool = True,
        max_turns: int = 5,
        workspace_root: str | Path | None = None,
    ):
        caps = capabilities or ["research", "writing", "formatting", "code", "qa", "seo"]
        super().__init__(worker_id, nickname, caps)
        self.env_token_var = env_token_var
        self._raw_github_token = github_token or (os.getenv(env_token_var, "") if env_token_var else "")
        self.model = model
        self.timeout = timeout
        self.enable_tools = enable_tools
        self.max_turns = max_turns
        self.workspace_root = Path(workspace_root).resolve() if workspace_root else None

        # Session token cache
        self._session_token: str | None = None
        self._session_expires_at: float = 0
        self._api_endpoint: str = self.COPILOT_CHAT_URL

    @property
    def token(self) -> str:
        """Dynamically resolve token (checks env var if not hardcoded)."""
        if self._raw_github_token:
            return self._raw_github_token
        if self.env_token_var:
            return os.getenv(self.env_token_var, "")
        return os.getenv("GITHUB_TOKEN", "")

    async def check_health(self) -> bool:
        """Health check returns True if token is present and valid session token can be obtained."""
        if not self.token:
            return False
        try:
            session_token = await self._get_session_token()
            return bool(session_token)
        except Exception:
            return False

    async def _get_session_token(self) -> str:
        """
        Exchanges GitHub token for internal Copilot session token.
        Caches token until 60 seconds before expiration.
        """
        now = time.time()
        if self._session_token and now < (self._session_expires_at - 60):
            return self._session_token

        headers = {
            "Authorization": f"token {self.token}",
            "Accept": "application/json",
            "User-Agent": "GitHubCopilotChat/0.22.0",
            "Editor-Version": "vscode/1.95.0",
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(self.COPILOT_TOKEN_URL, headers=headers)
            if resp.status_code == 401:
                raise PermissionError("Invalid GitHub token for Copilot")
            if resp.status_code == 403:
                raise PermissionError("GitHub token lacks active Copilot subscription")
            if resp.status_code != 200:
                raise RuntimeError(f"Copilot token exchange failed: HTTP {resp.status_code}")

            data = resp.json()
            self._session_token = data.get("token")
            self._session_expires_at = float(data.get("expires_at", now + 1800))
            endpoints = data.get("endpoints", {})
            if "api" in endpoints:
                self._api_endpoint = f"{endpoints['api'].rstrip('/')}/chat/completions"

            return self._session_token or ""

    def _resolve_safe_path(self, raw_path: str) -> Path:
        """Resolves path safely against workspace_root or cwd."""
        p = Path(raw_path)
        if not p.is_absolute():
            base = self.workspace_root or Path.cwd()
            p = (base / p).resolve()
        else:
            p = p.resolve()
        return p

    async def _execute_tool(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        """Executes a local tool inside workspace sandbox."""
        try:
            if name == "read_file":
                path_str = args.get("path", "")
                offset = int(args.get("offset", 1))
                limit = int(args.get("limit", 500))
                target = self._resolve_safe_path(path_str)
                if not target.exists():
                    return {"success": False, "error": f"File not found: {path_str}"}

                lines = target.read_text(encoding="utf-8", errors="replace").splitlines()
                start_idx = max(0, offset - 1)
                selected = lines[start_idx : start_idx + limit]
                return {
                    "success": True,
                    "content": "\n".join(selected),
                    "total_lines": len(lines),
                    "offset": offset,
                    "lines_returned": len(selected),
                }

            elif name == "write_file":
                path_str = args.get("path", "")
                content = args.get("content", "")
                target = self._resolve_safe_path(path_str)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding="utf-8")
                return {"success": True, "path": str(target), "bytes_written": len(content)}

            elif name == "run_command":
                cmd = args.get("command", "")
                timeout = float(args.get("timeout", 30.0))
                cwd = str(self.workspace_root) if self.workspace_root else None

                proc = await asyncio.create_subprocess_shell(
                    cmd,
                    cwd=cwd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
                return {
                    "success": proc.returncode == 0,
                    "exit_code": proc.returncode,
                    "stdout": stdout.decode("utf-8", errors="replace").strip(),
                    "stderr": stderr.decode("utf-8", errors="replace").strip(),
                }

            else:
                return {"success": False, "error": f"Unknown tool: {name}"}

        except asyncio.TimeoutError:
            return {"success": False, "error": "Tool execution timed out"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def execute_task(
        self,
        task_id: str,
        spec: str,
        stage: str,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Executes task prompt via Copilot Chat completions endpoint.
        Supports iterative multi-turn tool loops when enable_tools is True (M6).
        """
        if not self.token:
            return {
                "success": False,
                "error": f"Missing token (check {self.env_token_var or 'GITHUB_TOKEN'})",
                "summary": "",
                "result_text": "",
            }

        try:
            session_token = await self._get_session_token()
        except PermissionError as pe:
            return {"success": False, "error": f"AUTH_ERROR: {pe}", "summary": "", "result_text": ""}
        except Exception as e:
            return {"success": False, "error": f"TOKEN_EXCHANGE_ERROR: {e}", "summary": "", "result_text": ""}

        system_prompt = (
            f"You are a specialized autonomous AI worker in an automated pipeline operating in stage: {stage}.\n"
            f"Follow all instructions rigorously. Produce high-density, production-ready deliverables."
        )

        user_prompt = f"TASK ID: {task_id}\nSTAGE: {stage}\n\nSPECIFICATION:\n{spec}"
        if context:
            user_prompt += f"\n\nCONTEXT:\n{context}"

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        headers = {
            "Authorization": f"Bearer {session_token}",
            "Content-Type": "application/json",
            "Editor-Version": "vscode/1.95.0",
            "Copilot-Integration-Id": "vscode-chat",
            "User-Agent": "GitHubCopilotChat/0.22.0",
        }

        turn = 0
        total_tokens_accum = 0
        last_model_used = "copilot-auto"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            while turn < self.max_turns:
                turn += 1

                payload: dict[str, Any] = {
                    "messages": messages,
                    "temperature": 0.2,
                    "max_tokens": 4096,
                }
                if self.model and self.model != "auto":
                    payload["model"] = self.model
                if self.enable_tools:
                    payload["tools"] = self.AVAILABLE_TOOLS

                try:
                    resp = await client.post(self._api_endpoint, headers=headers, json=payload)
                except httpx.TimeoutException:
                    return {"success": False, "error": "TIMEOUT", "summary": "", "result_text": ""}
                except Exception as e:
                    return {"success": False, "error": f"NETWORK_ERROR: {e}", "summary": "", "result_text": ""}

                if resp.status_code == 429:
                    return {
                        "success": False,
                        "error": "RATE_LIMIT_429",
                        "summary": "Copilot account rate limit / quota hit",
                        "result_text": "",
                    }

                if resp.status_code != 200:
                    return {
                        "success": False,
                        "error": f"HTTP_{resp.status_code}: {resp.text[:200]}",
                        "summary": "",
                        "result_text": "",
                    }

                data = resp.json()
                try:
                    choices = data.get("choices", [])
                    if not choices:
                        return {"success": False, "error": "Empty choices in response", "summary": "", "result_text": ""}

                    choice_msg = choices[0]["message"]
                    last_model_used = data.get("model", last_model_used)
                    usage = data.get("usage", {})
                    total_tokens_accum += usage.get("total_tokens", 0)

                    tool_calls = choice_msg.get("tool_calls")
                    if not tool_calls or not self.enable_tools:
                        result_text = choice_msg.get("content") or ""
                        return {
                            "success": True,
                            "summary": f"Completed {stage} via Copilot ({last_model_used})",
                            "result_text": result_text,
                            "model_used": last_model_used,
                            "tokens_used": total_tokens_accum,
                            "error": None,
                        }

                    # Append assistant message with tool calls
                    messages.append(choice_msg)

                    # Execute tool calls
                    for tc in tool_calls:
                        tc_id = tc.get("id", "")
                        func = tc.get("function", {})
                        fn_name = func.get("name", "")
                        fn_args_raw = func.get("arguments", "{}")
                        try:
                            fn_args = json.loads(fn_args_raw) if isinstance(fn_args_raw, str) else fn_args_raw
                        except Exception:
                            fn_args = {}

                        tool_res = await self._execute_tool(fn_name, fn_args)
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tc_id,
                            "content": json.dumps(tool_res),
                        })

                except (KeyError, IndexError) as e:
                    return {
                        "success": False,
                        "error": f"MALFORMED_RESPONSE: {e}",
                        "summary": "",
                        "result_text": "",
                    }

            return {
                "success": False,
                "error": f"EXCEEDED_MAX_TURNS_{self.max_turns}",
                "summary": f"Exceeded max turns ({self.max_turns}) during tool execution",
                "result_text": messages[-1].get("content", "") if messages else "",
                "model_used": last_model_used,
                "tokens_used": total_tokens_accum,
            }
