"""
Live Claude Desktop Fleet Test Runner:
1. Launches the physical Claude Desktop application window on screen.
2. Identifies the active Electron window handle (HWND).
3. Focuses the input box and pastes a real test prompt via Windows UI Automation.
4. Submits the prompt to let Claude Desktop generate the live response in front of the user.
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from client.adapters.claude_desktop_cdp import ClaudeDesktopUIAAdapter


def find_claude_windows() -> list[tuple[int, str, int]]:
    """Enumerate top-level windows belonging to Claude.exe."""
    import win32gui
    import win32process

    found = []

    def enum_cb(hwnd, extra):
        if win32gui.IsWindow(hwnd) and win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            rect = win32gui.GetWindowRect(hwnd)
            w = rect[2] - rect[0]
            h = rect[3] - rect[1]
            if w > 200 and h > 200:
                if "claude" in title.lower() or title == "":
                    # Verify process name
                    try:
                        import psutil
                        proc = psutil.Process(pid)
                        if "claude" in proc.name().lower():
                            found.append((hwnd, title, pid))
                    except Exception:
                        pass
        return True

    win32gui.EnumWindows(enum_cb, None)
    return found


def launch_and_dispatch_live(account: str = "user1", prompt: str = "Hello Claude! Please write a concise 3-point summary of why exponential backoff with jitter is essential in distributed systems."):
    print("=" * 75)
    print("        LAUNCHING REAL LIVE CLAUDE DESKTOP APPLICATION SESSION")
    print("=" * 75)
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    print(f"Target Profile: {account}")
    print(f"Prompt to send: \"{prompt[:80]}...\"\n")

    launcher_path = REPO_ROOT / "launch_user_n.ps1"

    # 1. Launch Claude Desktop window
    print("[1/3] Launching live Claude Desktop window on your screen...")
    cmd = [
        "pwsh",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(launcher_path),
        "-Mode",
        "Concurrent",
        "-Users",
        account,
        "-NoTUI",
        "-NoTeamSync",
        "-NoSnap",
        "-NoPrompt",
        "-NoCooldownAlarm"
    ]
    subprocess.Popen(cmd)

    # 2. Wait for window to appear
    print("[2/3] Waiting for Claude Desktop UI window to mount...")
    target_hwnd = None
    for attempt in range(25):
        time.sleep(1.0)
        wins = find_claude_windows()
        if wins:
            target_hwnd, title, pid = wins[0]
            print(f"  [+] Found live Claude Desktop window! HWND: {target_hwnd}, PID: {pid}, Title: '{title}'")
            break
        print(f"  ... waiting for window ({attempt + 1}/25s)")

    if not target_hwnd:
        print("[!] Could not locate Claude Desktop window handle within 25s.")
        return False

    # Allow electron renderer 3s to initialize the ProseMirror input box
    print("\n[3/3] Focusing input box and typing prompt into Claude Desktop...")
    time.sleep(3.0)

    adapter = ClaudeDesktopUIAAdapter(worker_id=account, nickname=account, hwnd=target_hwnd)
    res = asyncio.run(adapter.send_text(prompt))

    if res.get("success"):
        print("\n" + "=" * 75)
        print("  [SUCCESS] PROMPT DISPATCHED TO LIVE CLAUDE DESKTOP WINDOW!")
        print("  -> Look at your Claude Desktop window to see the response streaming live.")
        print("=" * 75)
        return True
    else:
        print(f"\n[!] Dispatch failed: {res.get('error')}")
        return False


if __name__ == "__main__":
    account = sys.argv[1] if len(sys.argv) > 1 else "user1"
    prompt = sys.argv[2] if len(sys.argv) > 2 else "Explain why exponential backoff with jitter is critical in distributed systems in 3 bullet points."
    launch_and_dispatch_live(account, prompt)
