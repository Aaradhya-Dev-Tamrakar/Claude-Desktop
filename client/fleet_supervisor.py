from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any
import httpx

from client.adapters.claude_desktop_cdp import ClaudeDesktopCDPAdapter

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

async def run_worker_loop(
    worker_id: str,
    nickname: str,
    role: str,
    cdp_port: int,
    preferred_model: str,
    thinking_budget: int,
    client: httpx.AsyncClient,
    stop_event: asyncio.Event,
) -> None:
    """Individual worker loop attached to a specific Claude Desktop CDP instance."""
    capabilities = ROLE_CAPABILITIES.get(role, ["writing", "research", "code", "qa", "formatting"])
    adapter = ClaudeDesktopCDPAdapter(
        worker_id=worker_id,
        nickname=nickname,
        cdp_port=cdp_port,
        preferred_model=preferred_model,
        thinking_budget=thinking_budget,
    )

    print(f"[*] [{worker_id}] Probing Claude Desktop CDP readiness on port {cdp_port}...")
    is_ready = await adapter.wait_until_ready(timeout=25.0)
    if not is_ready:
        print(f"[!] [{worker_id}] Warning: CDP port {cdp_port} did not report ready. Retrying in background...")
    else:
        print(f"[+] [{worker_id}] CDP on port {cdp_port} is READY (Model: {preferred_model}).")

    # 1. Register worker with FastAPI orchestrator
    reg_payload = {
        "id": worker_id,
        "provider": "claude_desktop_cdp",
        "node_id": NODE_ID,
        "nickname": f"{nickname} ({role})",
        "capabilities": capabilities,
        "quota_limit_per_window": 50,
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
    parser = argparse.ArgumentParser(description="Autonomous Claude Desktop Fleet Supervisor")
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

    if not isinstance(fleet_data, list) or len(fleet_data) == 0:
        print("[!] Fleet metadata contains no active instances.")
        sys.exit(1)

    print(f"============================================================")
    print(f"  CLAUDE DESKTOP AUTONOMOUS FLEET SUPERVISOR")
    print(f"  Managing {len(fleet_data)} instances across isolated CDP ports")
    print(f"  Connecting to Orchestrator: {ORCHESTRATOR_URL}")
    print(f"============================================================")

    stop_event = asyncio.Event()
    async with httpx.AsyncClient(timeout=30.0) as client:
        tasks = []
        for inst in fleet_data:
            worker_id = inst.get("Account", "unknown")
            nickname = inst.get("Nickname", worker_id)
            role = inst.get("Role", "writer")
            cdp_port = int(inst.get("CdpPort", 9222))
            model = inst.get("PreferredModel", "claude-3-5-sonnet")
            budget = int(inst.get("ThinkingBudget", 0))

            t = asyncio.create_task(
                run_worker_loop(
                    worker_id=worker_id,
                    nickname=nickname,
                    role=role,
                    cdp_port=cdp_port,
                    preferred_model=model,
                    thinking_budget=budget,
                    client=client,
                    stop_event=stop_event,
                )
            )
            tasks.append(t)

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
