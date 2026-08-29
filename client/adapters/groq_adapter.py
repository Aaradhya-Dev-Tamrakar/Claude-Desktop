from __future__ import annotations

import os
from typing import Any
import httpx

from client.adapters.base_adapter import BaseWorkerAdapter


class GroqAdapter(BaseWorkerAdapter):
    """
    Adapter for Groq-hosted LLMs via the OpenAI-compatible chat completions API.
    """

    MODEL_OPTIONS = [
        "llama-3.3-70b-versatile",
        "llama-3.1-8b-instant",
        "llama-3.1-70b-versatile",
        "mixtral-8x7b-32768",
        "gemma2-9b-it",
        "deepseek-r1-distill-llama-70b",
    ]

    def __init__(self, worker_id: str, nickname: str, api_key: str | None = None, model: str | None = None):
        super().__init__(worker_id, nickname, ["research", "writing", "qa", "seo", "formatting"])
        self.api_key = api_key or os.getenv("GROQ_API_KEY", "")
        resolved_model = model or os.getenv("GROQ_MODEL") or "llama-3.3-70b-versatile"
        self.model = resolved_model
        self.endpoint = "https://api.groq.com/openai/v1/chat/completions"

    async def check_health(self) -> bool:
        return bool(self.api_key)

    async def execute_task(self, task_id: str, spec: str, stage: str, context: dict[str, Any]) -> dict[str, Any]:
        if not self.api_key:
            return {"success": False, "error": "Missing GROQ_API_KEY", "summary": "", "result_text": ""}

        prompt = (
            f"You are a specialized AI worker operating in stage: {stage}.\n"
            f"TASK SPECIFICATION:\n{spec}\n\n"
            f"Produce your final deliverable adhering strictly to the quality criteria."
        )

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,
            "max_tokens": 4096,
        }

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(self.endpoint, headers=headers, json=payload)
                if resp.status_code == 429:
                    return {"success": False, "error": "RATE_LIMIT_429", "summary": "", "result_text": ""}
                if resp.status_code != 200:
                    return {"success": False, "error": f"HTTP {resp.status_code}: {resp.text}", "summary": "", "result_text": ""}

                data = resp.json()
                try:
                    result_text = data["choices"][0]["message"]["content"]
                    return {
                        "success": True,
                        "summary": f"Completed {stage} via {self.model}",
                        "result_text": result_text,
                        "error": None,
                    }
                except (KeyError, IndexError, TypeError) as e:
                    return {"success": False, "error": f"Invalid Groq response: {e}", "summary": "", "result_text": ""}
        except Exception as e:
            return {"success": False, "error": f"Groq connection error: {e}", "summary": "", "result_text": ""}
