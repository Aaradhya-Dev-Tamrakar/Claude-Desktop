from __future__ import annotations

import asyncio
import os
import sys
from typing import Any
import httpx

from client.adapters.gemini_free_adapter import GeminiFreeAdapter
from client.adapters.groq_adapter import GroqAdapter
from client.adapters.ollama_local_adapter import OllamaLocalAdapter
from client.adapters.claude_desktop_proxy import ClaudeDesktopProxyAdapter
from client.adapters.claude_desktop_cdp import ClaudeDesktopCDPAdapter
from client.adapters.base_adapter import BaseWorkerAdapter

ORCHESTRATOR_URL = os.getenv("ORCHESTRATOR_URL", "http://localhost:8000/api/v1")
NODE_ID = os.getenv("NODE_ID", "local-node-01")
WORKER_ID = os.getenv("WORKER_ID", "groq_worker_01")
PROVIDER = os.getenv("PROVIDER", "groq")  # 'gemini_free', 'groq', 'ollama_local', 'claude_desktop', 'claude_desktop_cdp'
CDP_PORT = int(os.getenv("CDP_PORT") or os.getenv("CLAUDE_CDP_PORT") or "9222")

def get_adapter() -> BaseWorkerAdapter:
    if PROVIDER == "gemini_free":
        return GeminiFreeAdapter(worker_id=WORKER_ID, nickname="Gemini Free Worker")
    elif PROVIDER == "groq":
        return GroqAdapter(worker_id=WORKER_ID, nickname="Groq Worker")
    elif PROVIDER == "ollama_local":
        return OllamaLocalAdapter(worker_id=WORKER_ID, nickname="Ollama Qwen Worker")
    elif PROVIDER == "claude_desktop_cdp":
        return ClaudeDesktopCDPAdapter(worker_id=WORKER_ID, nickname="Claude Desktop CDP", cdp_port=CDP_PORT)
    else:
        return ClaudeDesktopProxyAdapter(worker_id=WORKER_ID, nickname="Claude Desktop Proxy", profile_path="", cdp_port=CDP_PORT)

async def main_loop():
    adapter = get_adapter()
    print(f"[*] Starting Worker Daemon: {WORKER_ID} ({PROVIDER}) on {NODE_ID}")
    print(f"[*] Connecting to Orchestrator: {ORCHESTRATOR_URL}")

    async with httpx.AsyncClient(timeout=30.0) as client:
        # 1. Register with cloud orchestrator
        reg_payload = {
            "id": WORKER_ID,
            "provider": PROVIDER,
            "node_id": NODE_ID,
            "nickname": adapter.nickname,
            "capabilities": adapter.capabilities,
            "quota_limit_per_window": 50,
            "cooldown_window_minutes": 300
        }
        try:
            r = await client.post(f"{ORCHESTRATOR_URL}/workers/register", json=reg_payload)
            print(f"[+] Registered worker successfully: {r.json().get('id')}")
        except Exception as e:
            print(f"[!] Failed to register with orchestrator: {e}")

        # 2. Main pull & heartbeat loop
        while True:
            try:
                # Send Heartbeat
                await client.post(f"{ORCHESTRATOR_URL}/workers/{WORKER_ID}/heartbeat", json={"usage_percent": 10})

                # Check if there is an assigned or claimable task
                task_resp = await client.get(f"{ORCHESTRATOR_URL}/tasks", params={"status": "pending", "limit": 5})
                if task_resp.status_code == 200:
                    tasks = task_resp.json()
                    for t in tasks:
                        task_id = t["id"]
                        stage = t["stage"]
                        
                        # Try to claim
                        claim_r = await client.post(f"{ORCHESTRATOR_URL}/tasks/{task_id}/claim", json={"worker_id": WORKER_ID, "lease_seconds": 300})
                        if claim_r.status_code == 200:
                            claim_data = claim_r.json()
                            claim_token = claim_data.get("claim_token")
                            task_info = claim_data.get("task", t)
                            print(f"[>] Claimed task {task_id} (stage: {stage}). Executing...")
                            exec_res = await adapter.execute_task(task_id, task_info["spec"], stage, {})
                            
                            if exec_res.get("success"):
                                # Submit checkpoint
                                cp_payload = {
                                    "task_id": task_id,
                                    "kind": "text",
                                    "summary": exec_res["summary"],
                                    "result_text": exec_res["result_text"],
                                    "submitted_by": WORKER_ID,
                                    "claim_token": claim_token
                                }
                                await client.post(f"{ORCHESTRATOR_URL}/tasks/{task_id}/checkpoint", json=cp_payload)
                                print(f"[+] Task {task_id} completed and checkpoint submitted!")
                            elif exec_res.get("error") == "RATE_LIMIT_429":
                                print(f"[!] Rate limit 429 encountered! Triggering cooldown...")
                                await client.post(f"{ORCHESTRATOR_URL}/workers/{WORKER_ID}/heartbeat", json={"trigger_cooldown": True})
                                await client.post(f"{ORCHESTRATOR_URL}/tasks/{task_id}/release", json={"worker_id": WORKER_ID, "claim_token": claim_token})
                                break
                            else:
                                print(f"[!] Task execution failed: {exec_res.get('error')}")
                                await client.post(f"{ORCHESTRATOR_URL}/tasks/{task_id}/release", json={"worker_id": WORKER_ID, "claim_token": claim_token})

                        
                await asyncio.sleep(10)
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[!] Error in worker daemon loop: {e}")
                await asyncio.sleep(10)

if __name__ == "__main__":
    try:
        asyncio.run(main_loop())
    except KeyboardInterrupt:
        print("[*] Worker daemon terminated.")
