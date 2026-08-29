from __future__ import annotations

import os
from typing import Any
import httpx

from client.adapters.base_adapter import BaseWorkerAdapter

class GeminiFreeAdapter(BaseWorkerAdapter):
    """
    Adapter for Google AI Studio Free Tier (Gemini 2.5 / 3.0).
    Provides free tokens with rate limits handled gracefully.
    """
    def __init__(self, worker_id: str, nickname: str, api_key: str | None = None, model: str = "gemini-2.5-flash"):
        super().__init__(worker_id, nickname, ["research", "writing", "qa", "seo", "formatting"])
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "")
        self.model = model
        self.endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"

    async def check_health(self) -> bool:
        return bool(self.api_key)

    async def execute_task(self, task_id: str, spec: str, stage: str, context: dict[str, Any]) -> dict[str, Any]:
        if not self.api_key:
            return {"success": False, "error": "Missing GEMINI_API_KEY", "summary": "", "result_text": ""}

        prompt = (
            f"You are a specialized AI worker operating in stage: {stage}.\n"
            f"TASK SPECIFICATION:\n{spec}\n\n"
            f"Produce your final deliverable adhering strictly to the quality criteria."
        )

        headers = {"Content-Type": "application/json"}
        params = {"key": self.api_key}
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.2, "maxOutputTokens": 4096}
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(self.endpoint, headers=headers, params=params, json=payload)
            if resp.status_code == 429:
                return {"success": False, "error": "RATE_LIMIT_429", "summary": "", "result_text": ""}
            if resp.status_code != 200:
                return {"success": False, "error": f"HTTP {resp.status_code}: {resp.text}", "summary": "", "result_text": ""}
            
            data = resp.json()
            try:
                result_text = data["candidates"][0]["content"]["parts"][0]["text"]
                return {
                    "success": True,
                    "summary": f"Completed {stage} via {self.model}",
                    "result_text": result_text,
                    "error": None
                }
            except (KeyError, IndexError) as e:
                return {"success": False, "error": f"Invalid Gemini response: {e}", "summary": "", "result_text": ""}
