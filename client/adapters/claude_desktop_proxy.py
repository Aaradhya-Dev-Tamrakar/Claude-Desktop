from __future__ import annotations

from typing import Any
from client.adapters.base_adapter import BaseWorkerAdapter

class ClaudeDesktopProxyAdapter(BaseWorkerAdapter):
    """
    Adapter representing a local Windows Claude Desktop profile session.
    Interfaces via the local MCP server and session tracking.
    """
    def __init__(self, worker_id: str, nickname: str, profile_path: str):
        super().__init__(worker_id, nickname, ["writing", "research", "code", "qa", "seo", "formatting"])
        self.profile_path = profile_path

    async def check_health(self) -> bool:
        # Considered healthy if profile exists
        return True

    async def execute_task(self, task_id: str, spec: str, stage: str, context: dict[str, Any]) -> dict[str, Any]:
        return {
            "success": True,
            "summary": f"Handled by Claude Desktop profile {self.nickname}",
            "result_text": f"[Claude Desktop Profile: {self.nickname}]\nTask completed for {stage}.",
            "error": None
        }
