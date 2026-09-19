"""
Copilot Headless Adapter: Pure asynchronous HTTP adapter for GitHub Copilot accounts.
Enables running multiple Copilot worker instances concurrently without opening VS Code or Electron GUI (~10-15 MB RAM per instance).
"""

from __future__ import annotations

import os
import time
from typing import Any
import httpx

from client.adapters.base_adapter import BaseWorkerAdapter


class CopilotHeadlessAdapter(BaseWorkerAdapter):
    """
    Automates GitHub Copilot via direct REST API without requiring VS Code.
    Exchanges GitHub token for internal Copilot session tokens with auto-refresh,
    supports free tier auto-model detection, and logs model telemetry.
    """

    COPILOT_TOKEN_URL = "https://api.github.com/copilot_internal/v2/token"
    COPILOT_CHAT_URL = "https://api.githubcopilot.com/chat/completions"

    def __init__(
        self,
        worker_id: str,
        nickname: str,
        github_token: str | None = None,
        env_token_var: str | None = None,
        model: str = "auto",
        capabilities: list[str] | None = None,
        timeout: float = 60.0,
    ):
        caps = capabilities or ["research", "writing", "formatting", "code", "qa", "seo"]
        super().__init__(worker_id, nickname, caps)
        self.env_token_var = env_token_var
        self._raw_github_token = github_token or (os.getenv(env_token_var, "") if env_token_var else "")
        self.model = model
        self.timeout = timeout

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

    async def execute_task(
        self,
        task_id: str,
        spec: str,
        stage: str,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Executes task prompt via Copilot Chat completions endpoint.
        Captures and returns the auto-selected model from response telemetry.
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

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        payload: dict[str, Any] = {
            "messages": messages,
            "temperature": 0.2,
            "max_tokens": 4096,
        }
        if self.model and self.model != "auto":
            payload["model"] = self.model

        headers = {
            "Authorization": f"Bearer {session_token}",
            "Content-Type": "application/json",
            "Editor-Version": "vscode/1.95.0",
            "Copilot-Integration-Id": "vscode-chat",
            "User-Agent": "GitHubCopilotChat/0.22.0",
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
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

                result_text = choices[0]["message"]["content"]
                model_used = data.get("model", "copilot-auto")
                usage = data.get("usage", {})

                return {
                    "success": True,
                    "summary": f"Completed {stage} via Copilot ({model_used})",
                    "result_text": result_text,
                    "model_used": model_used,
                    "tokens_used": usage.get("total_tokens", 0),
                    "error": None,
                }
            except (KeyError, IndexError) as e:
                return {
                    "success": False,
                    "error": f"MALFORMED_RESPONSE: {e}",
                    "summary": "",
                    "result_text": "",
                }
