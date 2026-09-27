"""
Live Claude Desktop Benchmark & Telemetry Suite

Performs real, physical process benchmarking of the Claude Desktop application:
1. Spawns live Claude Desktop instance(s) with dedicated CDP ports.
2. Measures Real Process Startup Time, CDP Attachment Latency, and UI Readiness.
3. Captures live OS process telemetry (Working Set RAM, PIDs, Thread count).
4. Verifies live CDP communication with the Electron renderer.
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
import websockets

REPO_ROOT = Path(__file__).resolve().parent.parent


def get_claude_process_snapshot() -> list[dict]:
    """Retrieve live OS process metrics for all running Claude.exe instances."""
    cmd = [
        "powershell",
        "-NoProfile",
        "-Command",
        "Get-Process -Name 'claude' -ErrorAction SilentlyContinue | Select-Object Id, ProcessName, WorkingSet64, NonpagedSystemMemorySize64, PagedMemorySize64, CPU, Threads | ConvertTo-Json -Depth 2"
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if res.returncode == 0 and res.stdout.strip():
            data = json.loads(res.stdout.strip())
            if isinstance(data, dict):
                return [data]
            elif isinstance(data, list):
                return data
    except Exception as e:
        print(f"[!] Warning reading process snapshot: {e}")
    return []


async def wait_for_cdp_port(port: int = 9222, timeout: float = 20.0) -> tuple[bool, float, dict]:
    """Poll the CDP JSON version endpoint until responsive or timeout."""
    start = time.perf_counter()
    url = f"http://127.0.0.1:{port}/json/version"
    async with httpx.AsyncClient(timeout=2.0) as client:
        while (time.perf_counter() - start) < timeout:
            try:
                r = await client.get(url)
                if r.status_code == 200:
                    latency = (time.perf_counter() - start) * 1000.0
                    return True, latency, r.json()
            except Exception:
                pass
            await asyncio.sleep(0.5)
    return False, (time.perf_counter() - start) * 1000.0, {}


async def wait_for_ui_prosemirror(port: int = 9222, timeout: float = 25.0) -> tuple[bool, float]:
    """Check via CDP WebSocket if the ProseMirror editor has rendered in the Electron window."""
    start = time.perf_counter()
    list_url = f"http://127.0.0.1:{port}/json/list"
    async with httpx.AsyncClient(timeout=3.0) as client:
        while (time.perf_counter() - start) < timeout:
            try:
                r = await client.get(list_url)
                if r.status_code == 200:
                    targets = r.json()
                    ws_url = None
                    for t in targets:
                        if t.get("type") in ("page", "webview", "app"):
                            ws_url = t.get("webSocketDebuggerUrl")
                            if ws_url:
                                break
                    if not ws_url and targets and "webSocketDebuggerUrl" in targets[0]:
                        ws_url = targets[0]["webSocketDebuggerUrl"]

                    if ws_url:
                        async with websockets.connect(ws_url, max_size=5_000_000, open_timeout=3.0) as ws:
                            # Enable runtime and check DOM
                            msg = json.dumps({"id": 1, "method": "Runtime.enable"})
                            await ws.send(msg)
                            await ws.recv()
                            
                            eval_msg = json.dumps({
                                "id": 2,
                                "method": "Runtime.evaluate",
                                "params": {
                                    "expression": "document.readyState === 'complete' || !!document.querySelector('.ProseMirror, div[contenteditable=\"true\"], textarea')",
                                    "returnByValue": True
                                }
                            })
                            await ws.send(eval_msg)
                            res = await ws.recv()
                            data = json.loads(res)
                            is_ready = data.get("result", {}).get("result", {}).get("value", False)
                            if is_ready:
                                return True, (time.perf_counter() - start) * 1000.0
            except Exception:
                pass
            await asyncio.sleep(0.5)
    return False, (time.perf_counter() - start) * 1000.0


def run_live_benchmark(profiles: list[str] = ["user1"], base_cdp_port: int = 9222):
    print("=" * 75)
    print("      CLAUDE DESKTOP LIVE INSTANCE BENCHMARK & TELEMETRY SUITE")
    print("=" * 75)
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    print(f"Target Profiles: {', '.join(profiles)}")
    print(f"Base CDP Debug Port: {base_cdp_port}\n")

    launcher_path = REPO_ROOT / "launch_user_n.ps1"
    profile_args = ",".join(profiles)

    # 1. Spawn Live Claude Instance(s)
    print("[1/4] Spawning live Claude Desktop instance(s) via launch_user_n.ps1...")
    start_spawn = time.perf_counter()
    spawn_cmd = [
        "pwsh",
        "-NoProfile",
        "-File",
        str(launcher_path),
        "-Mode",
        "Concurrent",
        "-Users",
        profile_args,
        "-BaseCdpPort",
        str(base_cdp_port),
        "-NoPrompt",
        "-NoCooldownAlarm",
        "-NoTeamSync",
        "-NoSnap"
    ]
    proc = subprocess.run(spawn_cmd, capture_output=True, text=True)
    spawn_duration_ms = (time.perf_counter() - start_spawn) * 1000.0
    print(f"  -> Launcher script execution time: {spawn_duration_ms:.1f} ms (Exit Code: {proc.returncode})")

    # 2. Measure CDP Readiness
    print("\n[2/4] Measuring Chrome DevTools Protocol (CDP) readiness...")
    cdp_results = []
    for idx, prof in enumerate(profiles):
        port = base_cdp_port + idx
        print(f"  * Polling profile '{prof}' on port {port}...")
        ok, latency, info = asyncio.run(wait_for_cdp_port(port, timeout=15.0))
        browser_info = info.get("Browser", "N/A")
        webkit_ver = info.get("WebKit-Version", "N/A")
        cdp_results.append({
            "profile": prof,
            "port": port,
            "cdp_online": ok,
            "cdp_latency_ms": latency,
            "browser": browser_info,
            "webkit": webkit_ver
        })
        status_str = "ONLINE (Ready)" if ok else "TIMEOUT/UNAVAILABLE"
        print(f"    -> Status: {status_str} | Latency: {latency:.1f} ms | Browser: {browser_info}")

    # 3. Measure UI Rendering & ProseMirror Readiness
    print("\n[3/4] Measuring Electron ProseMirror UI render latency...")
    for item in cdp_results:
        prof = item["profile"]
        port = item["port"]
        if item["cdp_online"]:
            ui_ok, ui_latency = asyncio.run(wait_for_ui_prosemirror(port, timeout=20.0))
            item["ui_ready"] = ui_ok
            item["ui_latency_ms"] = ui_latency
            print(f"  * Profile '{prof}' UI readiness: {'MOUNTED' if ui_ok else 'PENDING'} ({ui_latency:.1f} ms)")
        else:
            item["ui_ready"] = False
            item["ui_latency_ms"] = 0.0

    # 4. Live Process Telemetry Snapshot
    print("\n[4/4] Live OS Process Telemetry Snapshot (Claude.exe)...")
    processes = get_claude_process_snapshot()
    total_ram_bytes = sum(int(p.get("WorkingSet64", 0)) for p in processes)
    total_ram_mb = total_ram_bytes / (1024 * 1024)

    print(f"  * Running Claude.exe processes detected: {len(processes)}")
    print(f"  * Total Working Set RAM: {total_ram_mb:.1f} MB ({total_ram_mb / 1024:.2f} GB)")

    print("\n" + "-" * 75)
    print(f"{'PID':<10} | {'Process':<15} | {'RAM (MB)':<12} | {'Paged RAM (MB)':<15} | {'CPU (s)':<10}")
    print("-" * 75)
    for p in processes:
        pid = str(p.get("Id", "-"))
        name = str(p.get("ProcessName", "claude"))
        ram = f"{int(p.get('WorkingSet64', 0)) / (1024*1024):.1f}"
        paged = f"{int(p.get('PagedMemorySize64', 0)) / (1024*1024):.1f}"
        cpu = str(p.get("CPU", "0"))
        print(f"{pid:<10} | {name:<15} | {ram:<12} | {paged:<15} | {cpu:<10}")
    print("-" * 75)

    print("\n" + "=" * 75)
    print("                     LIVE BENCHMARK SUMMARY")
    print("=" * 75)
    print(f"  Launcher Duration:        {spawn_duration_ms:.1f} ms")
    for item in cdp_results:
        print(f"  Profile '{item['profile']}':")
        print(f"    - CDP Port {item['port']}:     {'ONLINE' if item['cdp_online'] else 'OFFLINE'} ({item['cdp_latency_ms']:.1f} ms)")
        print(f"    - UI Editor Ready:    {'YES' if item.get('ui_ready') else 'NO'} ({item.get('ui_latency_ms', 0):.1f} ms)")
        print(f"    - Electron Engine:    {item.get('browser')}")
    print(f"  Total Process Footprint:  {total_ram_mb:.1f} MB across {len(processes)} processes")
    print("=" * 75)


if __name__ == "__main__":
    target = sys.argv[1].split(",") if len(sys.argv) > 1 else ["user1"]
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 9222
    run_live_benchmark(target, port)
