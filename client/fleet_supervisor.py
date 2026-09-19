from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any
import httpx

from client.adapters.base_adapter import BaseWorkerAdapter
from client.adapters.claude_desktop_cdp import ClaudeDesktopCDPAdapter
from client.adapters.copilot_headless import CopilotHeadlessAdapter
from client.adapters.winpilot_bridge import WinPilotBridge

_SHARED_WINPILOT_BRIDGE: WinPilotBridge | None = None


def get_winpilot_bridge() -> WinPilotBridge:
    """Return shared WinPilotBridge singleton to coordinate physical desktop input."""
    global _SHARED_WINPILOT_BRIDGE
    if _SHARED_WINPILOT_BRIDGE is None:
        _SHARED_WINPILOT_BRIDGE = WinPilotBridge()
    return _SHARED_WINPILOT_BRIDGE

REPO_ROOT = Path(__file__).resolve().parent.parent
ORCHESTRATOR_URL = os.getenv("ORCHESTRATOR_URL", "http://127.0.0.1:8000/api/v1")
NODE_ID = os.getenv("NODE_ID", "local-fleet-node")
POLL_INTERVAL_SECONDS = max(1.0, float(os.getenv("WORKER_POLL_INTERVAL_SECONDS", "5")))
LEASE_SECONDS = max(30, int(os.getenv("LEASE_SECONDS", "300")))

ROLE_CAPABILITIES: dict[str, list[str]] = {
    "orchestrator": ["coordination", "review", "writing", "code"],
    "researcher": ["research", "fact_check", "web_search"],
    "writer": ["writing", "draft", "creative", "code"],
    "seo_optimizer": ["seo", "seo_optimize", "formatting", "writing"],
    "qa_reviewer": ["qa", "qa_review", "fact_check", "audit"],
    "formatter": ["formatting", "markdown", "schema"],
    "overflow_worker": ["writing", "research", "formatting"],
}

# ── Provider-based adapter factory ──────────────────────────────────
_PROVIDER_REGISTRY: dict[str, type] = {
    "claude_desktop_cdp": ClaudeDesktopCDPAdapter,
    "copilot_headless": CopilotHeadlessAdapter,
}


def create_adapter(inst: dict[str, Any]) -> BaseWorkerAdapter:
    """Instantiate the correct adapter from a fleet-entry dict.

    Supported providers:
      - claude_desktop_cdp  → ClaudeDesktopCDPAdapter (CDP/WebSocket)
      - copilot_headless    → CopilotHeadlessAdapter  (REST API, zero-GUI)
    """
    provider = inst.get("Provider", "claude_desktop_cdp")
    worker_id = inst.get("Account", "unknown")
    nickname = inst.get("Nickname", worker_id)
    model = inst.get("PreferredModel", "claude-3-5-sonnet")
    budget = int(inst.get("ThinkingBudget", 0))

    if provider == "claude_desktop_cdp":
        cdp_port = int(inst.get("CdpPort", 9222))
        use_winpilot = inst.get("UseWinPilot", True)
        window_title = inst.get("WindowTitle", f"Claude - {nickname}" if nickname != worker_id else "Claude")
        bridge = get_winpilot_bridge() if use_winpilot else None
        return ClaudeDesktopCDPAdapter(
            worker_id=worker_id,
            nickname=nickname,
            cdp_port=cdp_port,
            preferred_model=model,
            thinking_budget=budget,
            winpilot_bridge=bridge,
            window_title=window_title,
        )

    if provider == "copilot_headless":
        env_token = inst.get("EnvToken", "GITHUB_TOKEN")
        return CopilotHeadlessAdapter(
            worker_id=worker_id,
            nickname=nickname,
            github_token=os.getenv(env_token, ""),
            model=model,
        )

    raise ValueError(f"Unknown provider '{provider}' for worker '{worker_id}'")


# ── Generic worker loop ─────────────────────────────────────────────
async def run_worker_loop(
    worker_id: str,
    nickname: str,
    role: str,
    provider: str,
    adapter: BaseWorkerAdapter,
    client: httpx.AsyncClient,
    stop_event: asyncio.Event,
) -> None:
    """Worker loop that drives any BaseWorkerAdapter through the orchestrator task lifecycle."""
    capabilities = ROLE_CAPABILITIES.get(role, ["writing", "research", "code", "qa", "formatting"])

    # Provider-specific readiness probe
    if provider == "claude_desktop_cdp" and hasattr(adapter, "wait_until_ready"):
        cdp_port = getattr(adapter, "cdp_port", "?")
        print(f"[*] [{worker_id}] Probing Claude Desktop CDP readiness on port {cdp_port}...")
        is_ready = await adapter.wait_until_ready(timeout=25.0)
        if not is_ready:
            print(f"[!] [{worker_id}] Warning: CDP port {cdp_port} did not report ready. Retrying in background...")
        else:
            print(f"[+] [{worker_id}] CDP on port {cdp_port} is READY.")
    elif provider == "copilot_headless":
        health = await adapter.check_health()
        tag = "READY" if health.get("ok") else "DEGRADED"
        print(f"[+] [{worker_id}] Copilot Headless adapter {tag}.")
    else:
        print(f"[*] [{worker_id}] Provider '{provider}' — skipping readiness probe.")

    # 1. Register worker with FastAPI orchestrator
    reg_payload = {
        "id": worker_id,
        "provider": provider,
        "node_id": NODE_ID,
        "nickname": f"{nickname} ({role})",
        "capabilities": capabilities,
        "quota_limit_per_window": 50 if provider == "claude_desktop_cdp" else 10,
        "cooldown_window_minutes": 300,
    }
    try:
        r = await client.post(f"{ORCHESTRATOR_URL}/workers/register", json=reg_payload)
        if r.status_code in (200, 201):
            print(f"[+] [{worker_id}] Registered with orchestrator (capabilities: {capabilities})")
    except Exception as e:
        print(f"[!] [{worker_id}] Failed to register with orchestrator: {e}")

    reconnect_delay = 1.0
    while not stop_event.is_set():
        try:
            # Heartbeat
            await client.post(
                f"{ORCHESTRATOR_URL}/workers/{worker_id}/heartbeat",
                json={"usage_percent": 10},
            )

            # Check for claimable tasks matching worker capabilities
            task_resp = await client.get(
                f"{ORCHESTRATOR_URL}/tasks",
                params={"status": "pending", "limit": 5},
            )
            if task_resp.status_code == 200:
                tasks = task_resp.json()
                for t in tasks:
                    task_id = t["id"]
                    stage = t["stage"]
                    
                    # Verify capability match
                    if stage not in capabilities and "all" not in capabilities:
                        continue

                    # Try to claim
                    claim_r = await client.post(
                        f"{ORCHESTRATOR_URL}/tasks/{task_id}/claim",
                        json={"worker_id": worker_id, "lease_seconds": LEASE_SECONDS},
                    )
                    if claim_r.status_code == 200:
                        claim_data = claim_r.json()
                        claim_token = claim_data.get("claim_token")
                        task_info = claim_data.get("task", t)
                        print(f"[>] [{worker_id}] Claimed task {task_id} (stage: {stage}). Executing via CDP...")

                        exec_res = await adapter.execute_task(
                            task_id, task_info["spec"], stage, {}
                        )

                        if exec_res.get("success"):
                            result_text = exec_res.get("result_text", "")
                            
                            # If this is a QA stage, submit formal QA review
                            if stage in ("qa", "qa_review"):
                                verdict = "pass"
                                reason = None
                                if "fail" in result_text.lower() or "revision_needed" in result_text.lower():
                                    verdict = "revision_needed"
                                    reason = "QA checks requested revision"
                                
                                qa_payload = {
                                    "reviewer_worker_id": worker_id,
                                    "verdict": verdict,
                                    "rejection_reason": reason,
                                    "checks_passed": {"evaluated": True, "score": 90 if verdict == "pass" else 50},
                                }
                                await client.post(
                                    f"{ORCHESTRATOR_URL}/tasks/{task_id}/qa-review",
                                    json=qa_payload,
                                )
                                print(f"[+] [{worker_id}] Task {task_id} QA review submitted: {verdict.upper()}")
                            else:
                                # Normal stage: submit checkpoint
                                cp_payload = {
                                    "task_id": task_id,
                                    "kind": "text",
                                    "summary": exec_res["summary"],
                                    "result_text": result_text,
                                    "submitted_by": worker_id,
                                    "claim_token": claim_token,
                                }
                                await client.post(
                                    f"{ORCHESTRATOR_URL}/tasks/{task_id}/checkpoint",
                                    json=cp_payload,
                                )
                                print(f"[+] [{worker_id}] Task {task_id} checkpoint submitted.")

                        elif exec_res.get("error") == "RATE_LIMIT_429":
                            print(f"[!] [{worker_id}] Rate limit detected in Claude UI! Entering 5h cooldown.")
                            await client.post(
                                f"{ORCHESTRATOR_URL}/workers/{worker_id}/heartbeat",
                                json={"trigger_cooldown": True},
                            )
                            await client.post(
                                f"{ORCHESTRATOR_URL}/tasks/{task_id}/release",
                                json={"worker_id": worker_id, "claim_token": claim_token},
                            )
                            # Sleep during cooldown or until stop
                            await asyncio.sleep(300)
                        else:
                            print(f"[!] [{worker_id}] Task execution failed: {exec_res.get('error')}")
                            await client.post(
                                f"{ORCHESTRATOR_URL}/tasks/{task_id}/release",
                                json={"worker_id": worker_id, "claim_token": claim_token},
                            )
                        break

            reconnect_delay = 1.0
            await asyncio.sleep(POLL_INTERVAL_SECONDS)

        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"[!] [{worker_id}] Loop error: {e}")
            await asyncio.sleep(reconnect_delay)
            reconnect_delay = min(30.0, reconnect_delay * 2)

async def main():
    parser = argparse.ArgumentParser(description="Autonomous Multi-Provider Fleet Supervisor")
    parser.add_argument(
        "--fleet-file",
        type=str,
        default=str(REPO_ROOT / "orchestrator-state" / "live-status" / "active_fleet.json"),
        help="Path to active fleet JSON metadata",
    )
    args = parser.parse_args()

    fleet_file = Path(args.fleet_file)
    if not fleet_file.exists():
        print(f"[!] Fleet metadata file not found at: {fleet_file}")
        sys.exit(1)

    try:
        fleet_data = json.loads(fleet_file.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[!] Failed to parse fleet metadata: {e}")
        sys.exit(1)

    # Normalise: accept a single dict or a list of dicts
    if isinstance(fleet_data, dict):
        fleet_data = [fleet_data]
    if not isinstance(fleet_data, list) or len(fleet_data) == 0:
        print("[!] Fleet metadata contains no active instances.")
        sys.exit(1)

    providers_used = sorted({inst.get("Provider", "claude_desktop_cdp") for inst in fleet_data})
    print("============================================================")
    print("  AUTONOMOUS MULTI-PROVIDER FLEET SUPERVISOR")
    print(f"  Managing {len(fleet_data)} workers  |  Providers: {', '.join(providers_used)}")
    print(f"  Connecting to Orchestrator: {ORCHESTRATOR_URL}")
    print("============================================================")

    stop_event = asyncio.Event()
    async with httpx.AsyncClient(timeout=30.0) as client:
        tasks = []
        for inst in fleet_data:
            worker_id = inst.get("Account", "unknown")
            nickname = inst.get("Nickname", worker_id)
            role = inst.get("Role", "writer")
            provider = inst.get("Provider", "claude_desktop_cdp")

            try:
                adapter = create_adapter(inst)
            except ValueError as e:
                print(f"[!] Skipping worker '{worker_id}': {e}")
                continue

            t = asyncio.create_task(
                run_worker_loop(
                    worker_id=worker_id,
                    nickname=nickname,
                    role=role,
                    provider=provider,
                    adapter=adapter,
                    client=client,
                    stop_event=stop_event,
                )
            )
            tasks.append(t)

        if not tasks:
            print("[!] No workers could be initialised. Exiting.")
            sys.exit(1)

        try:
            await asyncio.gather(*tasks)
        except (KeyboardInterrupt, asyncio.CancelledError):
            print("\n[*] Stopping fleet supervisor...")
            stop_event.set()
            for t in tasks:
                t.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

if __name__ == "__main__":
    asyncio.run(main())

