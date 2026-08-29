from __future__ import annotations

import os
from typing import Any
import httpx

from client.adapters.base_adapter import BaseWorkerAdapter

class OllamaLocalAdapter(BaseWorkerAdapter):
    """
    Adapter for local Ollama / LM Studio models (e.g. Qwen 2.5, Llama 3.3).
    $0 inference for deterministic preprocessing, fact extraction, and regex checks.
    """
    def __init__(
        self,
        worker_id: str,
        nickname: str,
        base_url: str = "http://localhost:11434",
        model: str = "qwen2.5:7b"
    ):
        super().__init__(worker_id, nickname, ["research", "qa", "formatting", "writing"])
        self.base_url = base_url.rstrip("/")
        self.model = model

    async def check_health(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                r = await client.get(f"{self.base_url}/api/tags")
                return r.status_code == 200
        except Exception:
            return False

    async def execute_task(self, task_id: str, spec: str, stage: str, context: dict[str, Any]) -> dict[str, Any]:
        prompt = (
            f"SYSTEM: You are a local high-speed AI specialist in {stage}.\n"
            f"TASK SPEC:\n{spec}\n\n"
            f"OUTPUT DELIVERABLE:"
        )

        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.1}
        }

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                r = await client.post(f"{self.base_url}/api/generate", json=payload)
                if r.status_code != 200:
                    return {"success": False, "error": f"Ollama HTTP {r.status_code}: {r.text}", "summary": "", "result_text": ""}
                
                data = r.json()
                result_text = data.get("response", "")
                return {
                    "success": True,
                    "summary": f"Processed {stage} via local {self.model}",
                    "result_text": result_text,
                    "error": None
                }
        except Exception as e:
            return {"success": False, "error": f"Ollama connection error: {e}", "summary": "", "result_text": ""}
