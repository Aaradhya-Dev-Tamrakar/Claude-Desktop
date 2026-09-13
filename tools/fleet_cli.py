from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any
import httpx

from client.adapters.claude_desktop_cdp import ClaudeDesktopCDPAdapter, ClaudeDesktopUIAAdapter

REPO_ROOT = Path(__file__).resolve().parent.parent
FLEET_JSON = REPO_ROOT / "orchestrator-state" / "live-status" / "active_fleet.json"
ORCHESTRATOR_URL = os.getenv("ORCHESTRATOR_URL", "http://127.0.0.1:8000/api/v1")

if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

def _attach_default_desktop():
    try:
        import ctypes
        user32 = ctypes.windll.user32
        h_def = user32.OpenDesktopW("Default", 0, False, 0x01FF)
        if h_def:
            user32.SetThreadDesktop(h_def)
    except Exception:
        pass

def load_fleet_data() -> list[dict[str, Any]]:
    if FLEET_JSON.exists():
        try:
            return json.loads(FLEET_JSON.read_text(encoding="utf-8"))
        except Exception:
            pass
    # Fallback to scanning ports 9222-9229
    return [
        {"Account": f"user{i}", "Nickname": f"Instance {i}", "CdpPort": 9220 + i, "PreferredModel": "claude-3-5-sonnet", "Role": "worker"}
        for i in range(2, 7)
    ]

async def cmd_status():
    _attach_default_desktop()
    fleet = load_fleet_data()
    print("\n+----------------------------------------------------------------------------------------------------+")
    print("|                                   CLAUDE DESKTOP FLEET STATUS                                      |")
    print("+----------+--------------+--------------+----------------------+------------------+-----------------+")
    print("| Account  | Role         | Window HWND  | Preferred Model      | Window State     | CDP Status      |")
    print("+----------+--------------+--------------+----------------------+------------------+-----------------+")

    async with httpx.AsyncClient(timeout=1.5) as client:
        for inst in fleet:
            acc = inst.get("Account", "unknown")
            role = inst.get("Role", "worker")
            port = int(inst.get("CdpPort", 9222))
            hwnd = inst.get("Hwnd")
            model = inst.get("PreferredModel", "claude-3-5-sonnet")

            win_str = "NOT ATTACHED"
            if hwnd:
                try:
                    import win32gui
                    if win32gui.IsWindow(hwnd):
                        win_str = f"VISIBLE ({hwnd})" if win32gui.IsWindowVisible(hwnd) else f"HIDDEN ({hwnd})"
                except Exception:
                    win_str = f"HWND: {hwnd}"

            cdp_str = "OFFLINE"
            try:
                r = await client.get(f"http://127.0.0.1:{port}/json/version")
                if r.status_code == 200:
                    cdp_str = "ONLINE / READY"
            except Exception:
                cdp_str = "GUARDED"

            hwnd_col = str(hwnd) if hwnd else "-"
            print(f"| {acc:<8} | {role:<12} | {hwnd_col:<12} | {model:<20} | {win_str:<16} | {cdp_str:<15} |")

    print("+----------+--------------+--------------+----------------------+------------------+-----------------+\n")

async def cmd_broadcast(prompt: str):
    _attach_default_desktop()
    fleet = load_fleet_data()
    print(f"\n[*] Broadcasting prompt to {len(fleet)} instances:")
    print(f"    Prompt: {prompt[:100]}...\n")

    async def _send_one(inst: dict[str, Any]):
        acc = inst.get("Account", "unknown")
        hwnd = inst.get("Hwnd")
        if hwnd:
            adapter = ClaudeDesktopUIAAdapter(worker_id=acc, nickname=acc, hwnd=hwnd)
            res = await adapter.send_text(prompt)
            return acc, res.get("success", False), res.get("summary", "")
        else:
            port = int(inst.get("CdpPort", 9222))
            model = inst.get("PreferredModel", "claude-3-5-sonnet")
            adapter = ClaudeDesktopCDPAdapter(worker_id=acc, nickname=acc, cdp_port=port, preferred_model=model)
            res = await adapter.execute_task(task_id="broadcast", spec=prompt, stage="interactive", context={})
            return acc, res.get("success", False), res.get("result_text", res.get("error", ""))

    tasks = [_send_one(inst) for inst in fleet]
    results = await asyncio.gather(*tasks)

    for acc, success, out in results:
        status_tag = "[SUCCESS]" if success else "[FAILED]"
        print(f"┌───────────────────────────────────────────────────────────┐")
        print(f"│ Profile: {acc:<15} {status_tag:>35} │")
        print(f"├───────────────────────────────────────────────────────────┤")
        lines = out.strip().split("\n")
        for line in lines[:10]:
            print(f"  {line}")
        print(f"└───────────────────────────────────────────────────────────┘\n")

async def cmd_send(target: str, prompt: str):
    _attach_default_desktop()
    fleet = load_fleet_data()
    target_inst = None
    for inst in fleet:
        if inst.get("Account") == target or str(inst.get("CdpPort")) == target:
            target_inst = inst
            break

    if not target_inst:
        port = int(target) if target.isdigit() else 9222
        target_inst = {"Account": target, "CdpPort": port, "PreferredModel": "claude-3-5-sonnet"}

    acc = target_inst.get("Account", target)
    hwnd = target_inst.get("Hwnd")
    port = int(target_inst.get("CdpPort", 9222))
    model = target_inst.get("PreferredModel", "claude-3-5-sonnet")

    if hwnd:
        print(f"[*] Sending prompt to {acc} via Windows UI Automation (HWND={hwnd})...")
        adapter = ClaudeDesktopUIAAdapter(worker_id=acc, nickname=acc, hwnd=hwnd, preferred_model=model)
        res = await adapter.send_text(prompt)
    else:
        print(f"[*] Sending prompt to {acc} via CDP (Port {port}, Model: {model})...")
        adapter = ClaudeDesktopCDPAdapter(worker_id=acc, nickname=acc, cdp_port=port, preferred_model=model)
        res = await adapter.execute_task(task_id="cli_direct", spec=prompt, stage="interactive", context={})

    if res.get("success"):
        print(f"\n[+] Successfully dispatched prompt to {acc} on desktop.")
    else:
        print(f"\n[!] Execution failed: {res.get('error')}")

async def cmd_submit(spec: str):
    print(f"[*] Submitting end-to-end task DAG to Orchestrator: {ORCHESTRATOR_URL}")
    pipeline = ["research", "draft", "qa"]
    payload = {
        "title": "Autonomous Fleet Task",
        "sku_id": "custom_adhoc",
        "pipeline": json.dumps(pipeline),
        "quality_rules": "No hallucinations, professional structure, clean formatting",
        "raw_input_data": json.dumps([{"spec": spec}]),
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            r = await client.post(f"{ORCHESTRATOR_URL}/jobs", json=payload)
            if r.status_code in (200, 201):
                job = r.json()
                print(f"[+] Job submitted successfully: {job.get('id')}")
                print(f"    Pipeline: {' -> '.join(pipeline)}")
                print(f"    Tasks queued in SQLite WAL. Background daemons will claim and execute.")
                print(f"    Run 'python -m client.output_harvester' or check outputs/runs/ for deliverable.")
            else:
                print(f"[!] Submission failed with HTTP {r.status_code}: {r.text}")
        except Exception as e:
            print(f"[!] Failed to connect to Orchestrator at {ORCHESTRATOR_URL}: {e}")

def main():
    parser = argparse.ArgumentParser(description="Claude Desktop Multi-Instance Fleet CLI")
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    # status
    subparsers.add_parser("status", help="Show active Claude Desktop instances and CDP health")

    # broadcast
    bc_parser = subparsers.add_parser("broadcast", help="Broadcast a prompt to all active instances")
    bc_parser.add_argument("prompt", type=str, help="Prompt text to broadcast")

    # send
    send_parser = subparsers.add_parser("send", help="Send a prompt to a specific instance")
    send_parser.add_argument("target", type=str, help="Target account name (e.g. user2) or CDP port")
    send_parser.add_argument("prompt", type=str, help="Prompt text")

    # submit
    submit_parser = subparsers.add_parser("submit", help="Submit an autonomous multi-stage job to the orchestrator")
    submit_parser.add_argument("spec", type=str, help="Task specification")

    args = parser.parse_args()

    if args.subcommand == "status":
        asyncio.run(cmd_status())
    elif args.subcommand == "broadcast":
        asyncio.run(cmd_broadcast(args.prompt))
    elif args.subcommand == "send":
        asyncio.run(cmd_send(args.target, args.prompt))
    elif args.subcommand == "submit":
        asyncio.run(cmd_submit(args.spec))

if __name__ == "__main__":
    main()
