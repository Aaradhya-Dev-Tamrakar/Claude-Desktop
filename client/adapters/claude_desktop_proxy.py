from __future__ import annotations

import os
import json
from typing import Any
import httpx

from client.adapters.base_adapter import BaseWorkerAdapter
from client.adapters.claude_desktop_cdp import ClaudeDesktopCDPAdapter

class ClaudeDesktopProxyAdapter(BaseWorkerAdapter):
    """
    Adapter representing a local Windows Claude Desktop profile session.
    Interfaces via Anthropic API, local CDP session (free tier), or simulated profile engine fallback.
    """
    def __init__(
        self,
        worker_id: str,
        nickname: str,
        profile_path: str = "",
        api_key: str | None = None,
        model: str = "claude-3-5-sonnet-20241022",
        cdp_port: int | None = None,
        execution_mode: str | None = None,
    ):
        super().__init__(worker_id, nickname, ["writing", "research", "code", "qa", "seo", "formatting"])
        self.profile_path = profile_path
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY", "")
        self.model = model
        self.cdp_port = cdp_port if cdp_port is not None else int(os.getenv("CLAUDE_CDP_PORT") or "0")
        self._cdp_adapter = ClaudeDesktopCDPAdapter(worker_id, nickname, cdp_port=self.cdp_port) if self.cdp_port > 0 else None
        self.execution_mode = execution_mode if execution_mode is not None else os.getenv("EXECUTION_MODE", "")

    async def check_health(self) -> bool:
        if self._cdp_adapter:
            return await self._cdp_adapter.check_health()
        return True

    async def execute_task(self, task_id: str, spec: str, stage: str, context: dict[str, Any]) -> dict[str, Any]:
        """Execute task using Anthropic Claude API, CDP bridge, or explicit simulation mode.

        Error propagation follows INV-WSR-002 Invariant B: unhandled provider
        failures MUST emit typed errors, NEVER synthetic success.
        """
        # 1. If CDP port is active, use Chrome DevTools Protocol to automate free Claude Desktop
        if self._cdp_adapter and await self._cdp_adapter.check_health():
            return await self._cdp_adapter.execute_task(task_id, spec, stage, context)

        # 2. If real Anthropic API key is available, call Claude API
        if self.api_key:
            try:
                headers = {
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json"
                }
                system_prompt = f"You are a specialized production assistant in profile '{self.nickname}' working on stage: {stage}."
                payload = {
                    "model": self.model,
                    "max_tokens": 4096,
                    "system": system_prompt,
                    "messages": [{"role": "user", "content": spec}]
                }
                async with httpx.AsyncClient(timeout=60.0) as client:
                    resp = await client.post("https://api.anthropic.com/v1/messages", headers=headers, json=payload)
                    if resp.status_code == 429:
                        return {"success": False, "error": "RATE_LIMIT_429", "summary": "", "result_text": ""}
                    if resp.status_code != 200:
                        return {"success": False, "error": f"HTTP_{resp.status_code}: {resp.text[:200]}", "summary": "", "result_text": ""}
                    data = resp.json()
                    result_text = data["content"][0]["text"]
                    return {
                        "success": True,
                        "summary": f"Completed {stage} via Claude ({self.model})",
                        "result_text": result_text,
                        "error": None
                    }
            except httpx.TimeoutException:
                return {"success": False, "error": "TIMEOUT", "summary": "", "result_text": ""}
            except Exception as e:
                return {"success": False, "error": f"EXECUTION_FAILED: {e}", "summary": "", "result_text": ""}

        # 3. Explicit simulation mode — only when EXECUTION_MODE=SIMULATION (INV-WSR-002 §1.2)
        if self.execution_mode.upper() == "SIMULATION":
            transformed_result = self._execute_local_profile_stage(stage, spec)
            return {
                "success": True,
                "summary": f"[SIMULATION] Processed {stage} by Claude Desktop profile '{self.nickname}'",
                "result_text": transformed_result,
                "error": None
            }

        # No provider available and not in simulation mode
        return {
            "success": False,
            "error": "NO_PROVIDER_AVAILABLE: No API key, no CDP port, and EXECUTION_MODE != SIMULATION",
            "summary": "",
            "result_text": ""
        }

    def _execute_local_profile_stage(self, stage: str, spec: str) -> str:
        """Stage-aware local processing engine producing structured deliverables."""
        if stage == "research":
            return (
                f"### Research Insights ({self.nickname})\n"
                f"- Input Spec Analyzed: {spec[:200]}...\n"
                f"- Key Features Extracted: Ergonomic design, high durability, standard interfaces.\n"
                f"- Target Audience: Professional & retail consumers looking for quality."
            )
        elif stage == "draft":
            return (
                f"### Product Draft Copy\n"
                f"Experience superior quality and peak performance engineered for modern everyday use. "
                f"Crafted with precision, this product delivers seamless connectivity, long-lasting reliability, "
                f"and ergonomic comfort for all-day productivity.\n\n"
                f"**Highlights:**\n"
                f"- Premium grade materials\n"
                f"- Intuitive setup and universal compatibility\n"
                f"- Optimized for efficiency"
            )
        elif stage in ("seo", "seo_optimize"):
            return (
                f"### SEO Optimized Content\n"
                f"**Meta Title:** Premium Ergonomic Solution - High Performance & Comfort\n"
                f"**Meta Description:** Discover peak performance and durability with our ergonomic device. Designed for seamless productivity.\n"
                f"**Keywords:** ergonomic, high performance, productivity, premium hardware, seamless connectivity\n\n"
                f"Experience superior quality and peak performance engineered for modern everyday use. "
                f"Crafted with precision, this product delivers seamless connectivity, long-lasting reliability, "
                f"and ergonomic comfort for all-day productivity."
            )
        elif stage == "qa":
            return (
                f"### QA Verification Summary\n"
                f"- Adherence to Quality Rules: PASS\n"
                f"- Grammar & Style Check: PASS\n"
                f"- Accuracy against source specs: VERIFIED (100% match)\n"
                f"- Word count within limits: PASS"
            )
        elif stage in ("format", "formatting"):
            return (
                f"| Field | Content |\n"
                f"| --- | --- |\n"
                f"| Title | Premium High Performance Product |\n"
                f"| Description | Experience superior quality and peak performance engineered for modern everyday use. |\n"
                f"| SEO Keywords | ergonomic, high performance, productivity |\n"
                f"| Verified By | Claude Profile {self.nickname} |"
            )
        else:
            return f"Processed task spec for stage '{stage}' via profile '{self.nickname}'.\n{spec[:300]}"

