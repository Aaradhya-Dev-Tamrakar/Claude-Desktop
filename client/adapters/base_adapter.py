from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

class BaseWorkerAdapter(ABC):
    """Abstract interface for worker execution endpoints."""
    
    def __init__(self, worker_id: str, nickname: str, capabilities: list[str]):
        self.worker_id = worker_id
        self.nickname = nickname
        self.capabilities = capabilities

    @abstractmethod
    async def execute_task(self, task_id: str, spec: str, stage: str, context: dict[str, Any]) -> dict[str, Any]:
        """
        Executes work specified in `spec`.
        Returns dictionary:
        {
            "summary": "...",
            "result_text": "...",
            "success": True/False,
            "error": "..."
        }
        """
        pass

    @abstractmethod
    async def check_health(self) -> bool:
        """Returns True if the backend AI model / profile is online and usable."""
        pass
