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
LEASE_SECONDS = max(30, int(os.getenv("LEASE_SECONDS", "300")))
LEASE_RENEWAL_SECONDS = max(10, int(os.getenv("LEASE_RENEWAL_SECONDS", str(LEASE_SECONDS // 3))))
POLL_INTERVAL_SECONDS = max(1.0, float(os.getenv("WORKER_POLL_INTERVAL_SECONDS", "10")))
HTTP_MAX_CONNECTIONS = max(2, int(os.getenv("WORKER_HTTP_MAX_CONNECTIONS", "10")))
HTTP_MAX_KEEPALIVE_CONNECTIONS = max(1, min(
    HTTP_MAX_CONNECTIONS,
    int(os.getenv("WORKER_HTTP_MAX_KEEPALIVE_CONNECTIONS", "5")),
))
MAX_RECONNECT_DELAY_SECONDS = 60

API_KEY = os.getenv("API_AUTH_KEY") or os.getenv("ORCHESTRATOR_API_KEY", "")

def get_system_telemetry() -> dict[str, Any]:
    """Measure empirical OS metrics (Invariant C). Does NOT include quota/usage fields."""
    try:
        import psutil
        cpu = psutil.cpu_percent(interval=None)
        mem = psutil.virtual_memory().percent
        return {"cpu_percent": float(cpu), "memory_percent": float(mem)}
    except Exception:
        pass

    try:
        import ctypes
        import time
        if sys.platform == "win32":
            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]
            stat = MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
            mem = float(stat.dwMemoryLoad)

            class FILETIME(ctypes.Structure):
                _fields_ = [("dwLowDateTime", ctypes.c_ulong), ("dwHighDateTime", ctypes.c_ulong)]

            idle, kernel, user = FILETIME(), FILETIME(), FILETIME()
            if ctypes.windll.kernel32.GetSystemTimes(ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user)):
                to_int = lambda ft: (ft.dwHighDateTime << 32) + ft.dwLowDateTime
                i1, k1, u1 = to_int(idle), to_int(kernel), to_int(user)
                time.sleep(0.01)
                ctypes.windll.kernel32.GetSystemTimes(ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user))
                i2, k2, u2 = to_int(idle), to_int(kernel), to_int(user)
                sys_time = (k2 - k1) + (u2 - u1)
                idle_time = (i2 - i1)
                cpu = float(round(100.0 * (sys_time - idle_time) / sys_time, 1)) if sys_time > 0 else 0.0
                return {"cpu_percent": cpu, "memory_percent": mem}
    except Exception:
        pass

    return {"cpu_percent": None, "memory_percent": None}

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

async def renew_task_lease_periodically(
    client: httpx.AsyncClient,
    task_id: str,
    claim_token: str,
    stop_event: asyncio.Event,
) -> None:
    while not stop_event.is_set():
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=LEASE_RENEWAL_SECONDS)
            break
        except asyncio.TimeoutError:
            response = await client.post(
                f"{ORCHESTRATOR_URL}/tasks/{task_id}/renew-lease",
                json={
                    "worker_id": WORKER_ID,
                    "claim_token": claim_token,
                    "lease_seconds": LEASE_SECONDS,
                },
            )
            if response.status_code != 200:
                print(f"[!] Lease renewal failed for {task_id}: HTTP {response.status_code}")
                break

async def main_loop():
    adapter = get_adapter()
    print(f"[*] Starting Worker Daemon: {WORKER_ID} ({PROVIDER}) on {NODE_ID}")
    print(f"[*] Connecting to Orchestrator: {ORCHESTRATOR_URL}")

    limits = httpx.Limits(
        max_connections=HTTP_MAX_CONNECTIONS,
        max_keepalive_connections=HTTP_MAX_KEEPALIVE_CONNECTIONS,
    )
    headers = {"X-API-Key": API_KEY} if API_KEY else {}
    async with httpx.AsyncClient(timeout=30.0, limits=limits, headers=headers) as client:
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
            r.raise_for_status()
            print(f"[+] Registered worker successfully: {r.json().get('id')}")
        except Exception as e:
            raise RuntimeError(f"Failed to register with orchestrator: {e}") from e

        # 2. Main pull & heartbeat loop
        reconnect_delay = 1
        active_task_id: str | None = None
        while True:
            try:
                # Send Heartbeat with empirical telemetry (Invariant C)
                telemetry = get_system_telemetry()
                hb_payload = {
                    "cpu_percent": telemetry["cpu_percent"],
                    "memory_percent": telemetry["memory_percent"],
                    "active_leases": 1 if active_task_id else 0,
                    "current_task_id": active_task_id,
                }
                await client.post(f"{ORCHESTRATOR_URL}/workers/{WORKER_ID}/heartbeat", json=hb_payload)

                # Acquire task via Closed-Loop Protocol (Invariant A)
                acq_payload = {
                    "worker_id": WORKER_ID,
                    "capabilities": adapter.capabilities,
                    "lease_seconds": LEASE_SECONDS,
                }
                acq_r = await client.post(f"{ORCHESTRATOR_URL}/tasks/acquire", json=acq_payload)
                if acq_r.status_code == 200 and acq_r.json():
                    claim_data = acq_r.json()
                    claim_token = claim_data.get("claim_token")
                    task_info = claim_data.get("task", {})
                    task_id = task_info.get("id")
                    stage = task_info.get("stage")

                    if task_id and claim_token:
                        print(f"[>] Acquired task {task_id} (stage: {stage}). Executing...")
                        active_task_id = task_id
                        # Report busy state & active lease immediately in heartbeat
                        await client.post(
                            f"{ORCHESTRATOR_URL}/workers/{WORKER_ID}/heartbeat",
                            json={
                                "cpu_percent": telemetry["cpu_percent"],
                                "memory_percent": telemetry["memory_percent"],
                                "active_leases": 1,
                                "current_task_id": task_id,
                            },
                        )
                        lease_stop = asyncio.Event()
                        lease_task = asyncio.create_task(
                            renew_task_lease_periodically(client, task_id, claim_token, lease_stop)
                        )
                        try:
                            exec_res = await adapter.execute_task(task_id, task_info.get("spec", ""), stage, {})

                            if exec_res.get("success"):
                                # Submit checkpoint
                                cp_payload = {
                                    "task_id": task_id,
                                    "kind": "text",
                                    "summary": exec_res.get("summary", ""),
                                    "result_text": exec_res.get("result_text", ""),
                                    "submitted_by": WORKER_ID,
                                    "claim_token": claim_token,
                                }
                                checkpoint_r = await client.post(f"{ORCHESTRATOR_URL}/tasks/{task_id}/checkpoint", json=cp_payload)
                                checkpoint_r.raise_for_status()
                                print(f"[+] Task {task_id} completed and checkpoint submitted!")
                            elif exec_res.get("error") == "RATE_LIMIT_429":
                                print(f"[!] Rate limit 429 encountered! Triggering cooldown...")
                                await client.post(f"{ORCHESTRATOR_URL}/workers/{WORKER_ID}/heartbeat", json={"trigger_cooldown": True})
                                await client.post(f"{ORCHESTRATOR_URL}/tasks/{task_id}/release", json={"worker_id": WORKER_ID, "claim_token": claim_token})
                            else:
                                print(f"[!] Task execution failed: {exec_res.get('error')}")
                                await client.post(f"{ORCHESTRATOR_URL}/tasks/{task_id}/release", json={"worker_id": WORKER_ID, "claim_token": claim_token})
                        finally:
                            lease_stop.set()
                            await lease_task
                            active_task_id = None

                reconnect_delay = 1
                await asyncio.sleep(POLL_INTERVAL_SECONDS)
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[!] Error in worker daemon loop: {e}")
                await asyncio.sleep(reconnect_delay)
                reconnect_delay = min(MAX_RECONNECT_DELAY_SECONDS, reconnect_delay * 2)

if __name__ == "__main__":
    try:
        asyncio.run(main_loop())
    except KeyboardInterrupt:
        print("[*] Worker daemon terminated.")
