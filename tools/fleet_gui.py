#!/usr/bin/env python3
"""
Claude Desktop Autonomous Fleet Control Center (Native GUI)
Allows one-click launch, layout arrangement, virtual desktop switching,
direct in-window prompt injection, and task monitoring for multi-instance Claude.
"""

from __future__ import annotations

import asyncio
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk, scrolledtext

import httpx

# Paths
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

FLEET_JSON = REPO_ROOT / "orchestrator-state" / "live-status" / "active_fleet.json"
VD_EXE = REPO_ROOT / "tools" / "VirtualDesktop.exe"
LAUNCH_SCRIPT = REPO_ROOT / "launch-fleet.ps1"
ORCHESTRATOR_URL = os.getenv("ORCHESTRATOR_URL", "http://127.0.0.1:8000/api/v1")

# Win32 desktop attachment helper
def attach_default_desktop():
    try:
        user32 = ctypes.windll.user32
        h_def = user32.OpenDesktopW("Default", 0, False, 0x01FF)
        if h_def:
            user32.SetThreadDesktop(h_def)
            return True
    except Exception:
        pass
    return False

def ensure_orchestrator_server():
    try:
        r = httpx.get("http://127.0.0.1:8000/health", timeout=1.0)
        if r.status_code == 200:
            return True
    except Exception:
        pass

    py_exe = REPO_ROOT / ".venv" / "Scripts" / "python.exe"
    exe_str = str(py_exe) if py_exe.exists() else "python"
    try:
        subprocess.Popen(
            [exe_str, "-m", "uvicorn", "server.main:app", "--host", "127.0.0.1", "--port", "8000"],
            cwd=str(REPO_ROOT),
            creationflags=0x08000000 if sys.platform == "win32" else 0, # CREATE_NO_WINDOW
        )
    except Exception:
        pass
    return False

# UI Colors & Fonts (Modern Dark Palette)
BG_MAIN = "#121214"
BG_CARD = "#1c1c21"
BG_INPUT = "#26262e"
BORDER_COLOR = "#32323d"
TEXT_PRIMARY = "#f4f4f5"
TEXT_MUTED = "#a1a1aa"
ACCENT_BLUE = "#3b82f6"
ACCENT_GREEN = "#10b981"
ACCENT_PURPLE = "#8b5cf6"
ACCENT_AMBER = "#f59e0b"
ACCENT_RED = "#ef4444"

FONT_TITLE = ("Segoe UI", 13, "bold")
FONT_SUBTITLE = ("Segoe UI", 10, "bold")
FONT_BODY = ("Segoe UI", 9)
FONT_MONO = ("Consolas", 9)
FONT_BADGE = ("Segoe UI", 8, "bold")


class FleetControlApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Claude Desktop Fleet Control Center")
        self.geometry("1020x760")
        self.minsize(880, 640)
        self.configure(bg=BG_MAIN)

        attach_default_desktop()

        self._init_styles()
        self._build_ui()

        # Start background polling for status and tasks
        self.after(500, self.refresh_all_status)
        self._auto_refresh_loop()

    def _init_styles(self):
        self.style = ttk.Style(self)
        self.style.theme_use("clam")

        # Configure generic TTK elements
        self.style.configure(".", background=BG_MAIN, foreground=TEXT_PRIMARY, font=FONT_BODY)
        self.style.configure("TLabel", background=BG_MAIN, foreground=TEXT_PRIMARY)
        self.style.configure("Card.TFrame", background=BG_CARD)
        self.style.configure("TFrame", background=BG_MAIN)

        # Treeview styling
        self.style.configure(
            "Treeview",
            background=BG_CARD,
            foreground=TEXT_PRIMARY,
            fieldbackground=BG_CARD,
            rowheight=26,
            font=FONT_BODY,
            borderwidth=0,
        )
        self.style.configure(
            "Treeview.Heading",
            background=BG_INPUT,
            foreground=TEXT_PRIMARY,
            font=FONT_SUBTITLE,
            relief="flat",
        )
        self.style.map("Treeview", background=[("selected", ACCENT_BLUE)])

    def _build_ui(self):
        # 1. Header Toolbar
        header_frame = tk.Frame(self, bg=BG_CARD, height=56, relief="flat", highlightbackground=BORDER_COLOR, highlightthickness=1)
        header_frame.pack(fill="x", padx=12, pady=(12, 6))

        title_lbl = tk.Label(
            header_frame,
            text="⚡ CLAUDE DESKTOP AUTONOMOUS FLEET CONTROL",
            font=FONT_TITLE,
            bg=BG_CARD,
            fg=TEXT_PRIMARY,
        )
        title_lbl.pack(side="left", padx=16, pady=12)

        self.server_badge = tk.Label(
            header_frame,
            text="● ORCHESTRATOR: CHECKING",
            font=FONT_BADGE,
            bg="#27272a",
            fg=ACCENT_AMBER,
            padx=8,
            pady=4,
        )
        self.server_badge.pack(side="right", padx=16, pady=14)

        # 2. Main Action Control Bar
        action_bar = tk.Frame(self, bg=BG_MAIN)
        action_bar.pack(fill="x", padx=12, pady=6)

        btn_launch = tk.Button(
            action_bar,
            text="🚀 Launch Fleet (Desktop 2)",
            bg=ACCENT_BLUE,
            fg="#ffffff",
            activebackground="#2563eb",
            activeforeground="#ffffff",
            font=FONT_SUBTITLE,
            relief="flat",
            padx=14,
            pady=6,
            command=self.on_launch_fleet,
            cursor="hand2",
        )
        btn_launch.pack(side="left", padx=(0, 8))

        btn_tile = tk.Button(
            action_bar,
            text="🪟 Tile Windows (3-Column Grid)",
            bg=BG_CARD,
            fg=TEXT_PRIMARY,
            activebackground=BG_INPUT,
            activeforeground=TEXT_PRIMARY,
            font=FONT_BODY,
            relief="flat",
            highlightbackground=BORDER_COLOR,
            highlightthickness=1,
            padx=12,
            pady=6,
            command=self.on_tile_windows,
            cursor="hand2",
        )
        btn_tile.pack(side="left", padx=4)

        btn_vdesk2 = tk.Button(
            action_bar,
            text="🖥️ Switch to Desktop 2 (Fleet)",
            bg=BG_CARD,
            fg=TEXT_PRIMARY,
            activebackground=BG_INPUT,
            activeforeground=TEXT_PRIMARY,
            font=FONT_BODY,
            relief="flat",
            highlightbackground=BORDER_COLOR,
            highlightthickness=1,
            padx=12,
            pady=6,
            command=lambda: self.on_switch_desktop(1),
            cursor="hand2",
        )
        btn_vdesk2.pack(side="left", padx=4)

        btn_vdesk1 = tk.Button(
            action_bar,
            text="🏠 Return to Desktop 1",
            bg=BG_CARD,
            fg=TEXT_PRIMARY,
            activebackground=BG_INPUT,
            activeforeground=TEXT_PRIMARY,
            font=FONT_BODY,
            relief="flat",
            highlightbackground=BORDER_COLOR,
            highlightthickness=1,
            padx=12,
            pady=6,
            command=lambda: self.on_switch_desktop(0),
            cursor="hand2",
        )
        btn_vdesk1.pack(side="left", padx=4)

        btn_refresh = tk.Button(
            action_bar,
            text="🔄 Refresh",
            bg=BG_CARD,
            fg=TEXT_PRIMARY,
            activebackground=BG_INPUT,
            activeforeground=TEXT_PRIMARY,
            font=FONT_BODY,
            relief="flat",
            highlightbackground=BORDER_COLOR,
            highlightthickness=1,
            padx=12,
            pady=6,
            command=self.refresh_all_status,
            cursor="hand2",
        )
        btn_refresh.pack(side="right")

        # 3. Instance Status Cards (user1, user2, user3)
        cards_frame = tk.Frame(self, bg=BG_MAIN)
        cards_frame.pack(fill="x", padx=12, pady=6)

        self.cards = {}
        profiles_meta = [
            ("user1", "adevtmr", "Orchestrator", "claude-3-7-sonnet", "Thinking: 8k", ACCENT_PURPLE),
            ("user2", "dev83", "Researcher", "claude-3-5-haiku", "Fast Analysis", ACCENT_BLUE),
            ("user3", "xavier", "Writer", "claude-3-5-sonnet", "Copy Specialist", ACCENT_GREEN),
        ]

        for idx, (acc, nick, role, model, extra, color) in enumerate(profiles_meta):
            card = tk.Frame(cards_frame, bg=BG_CARD, relief="flat", highlightbackground=BORDER_COLOR, highlightthickness=1)
            card.pack(side="left", fill="both", expand=True, padx=4 if idx == 1 else 0)

            # Top header of card
            header = tk.Frame(card, bg=BG_CARD)
            header.pack(fill="x", padx=12, pady=(10, 4))

            title_role = tk.Label(header, text=f"{role.upper()} ({acc})", font=FONT_SUBTITLE, bg=BG_CARD, fg=color)
            title_role.pack(side="left")

            status_badge = tk.Label(header, text="OFFLINE", font=FONT_BADGE, bg="#27272a", fg=TEXT_MUTED, padx=6, pady=2)
            status_badge.pack(side="right")

            # Model info
            lbl_model = tk.Label(card, text=f"Model: {model} ({extra})", font=FONT_BODY, bg=BG_CARD, fg=TEXT_PRIMARY)
            lbl_model.pack(anchor="w", padx=12, pady=2)

            # HWND & Window info
            lbl_hwnd = tk.Label(card, text="Window HWND: Not Attached", font=FONT_MONO, bg=BG_CARD, fg=TEXT_MUTED)
            lbl_hwnd.pack(anchor="w", padx=12, pady=(2, 10))

            self.cards[acc] = {
                "frame": card,
                "status_badge": status_badge,
                "lbl_hwnd": lbl_hwnd,
                "role": role,
                "model": model,
            }

        # 4. Prompt Injection & Dispatch Console (Path B)
        console_frame = tk.LabelFrame(
            self,
            text=" Automated Prompt Injection (Path B) ",
            bg=BG_CARD,
            fg=TEXT_PRIMARY,
            font=FONT_SUBTITLE,
            relief="flat",
            highlightbackground=BORDER_COLOR,
            highlightthickness=1,
        )
        console_frame.pack(fill="x", padx=12, pady=6)

        ctrl_row = tk.Frame(console_frame, bg=BG_CARD)
        ctrl_row.pack(fill="x", padx=12, pady=(8, 4))

        tk.Label(ctrl_row, text="Target Instance:", font=FONT_BODY, bg=BG_CARD, fg=TEXT_PRIMARY).pack(side="left", padx=(0, 6))

        self.target_var = tk.StringVar(value="user1 (Orchestrator)")
        target_cb = ttk.Combobox(
            ctrl_row,
            textvariable=self.target_var,
            values=["user1 (Orchestrator)", "user2 (Researcher)", "user3 (Writer)", "⚡ Broadcast All"],
            state="readonly",
            width=24,
            font=FONT_BODY,
        )
        target_cb.pack(side="left", padx=(0, 14))

        tk.Label(ctrl_row, text="Quick Templates:", font=FONT_BODY, bg=BG_CARD, fg=TEXT_MUTED).pack(side="left", padx=(0, 6))

        btn_t1 = tk.Button(ctrl_row, text="Coordinate (user1)", font=FONT_BADGE, bg=BG_INPUT, fg=TEXT_PRIMARY, relief="flat", command=self._set_template_orch)
        btn_t1.pack(side="left", padx=2)

        btn_t2 = tk.Button(ctrl_row, text="Claim Research (user2)", font=FONT_BADGE, bg=BG_INPUT, fg=TEXT_PRIMARY, relief="flat", command=self._set_template_research)
        btn_t2.pack(side="left", padx=2)

        btn_t3 = tk.Button(ctrl_row, text="Claim Draft (user3)", font=FONT_BADGE, bg=BG_INPUT, fg=TEXT_PRIMARY, relief="flat", command=self._set_template_draft)
        btn_t3.pack(side="left", padx=2)

        btn_t4 = tk.Button(ctrl_row, text="Status Ping (All)", font=FONT_BADGE, bg=BG_INPUT, fg=TEXT_PRIMARY, relief="flat", command=self._set_template_ping)
        btn_t4.pack(side="left", padx=2)

        # Text input & send button
        text_row = tk.Frame(console_frame, bg=BG_CARD)
        text_row.pack(fill="x", padx=12, pady=(4, 10))

        self.prompt_text = tk.Text(
            text_row,
            height=3,
            bg=BG_INPUT,
            fg=TEXT_PRIMARY,
            insertbackground=TEXT_PRIMARY,
            relief="flat",
            font=FONT_BODY,
            wrap="word",
        )
        self.prompt_text.pack(side="left", fill="both", expand=True, padx=(0, 8))
        self.prompt_text.insert("1.0", "You are user1, the Fleet Orchestrator. Inspect active tasks using list_tasks and coordinate work.")

        btn_send = tk.Button(
            text_row,
            text="🚀 Dispatch &\nHit Enter",
            bg=ACCENT_GREEN,
            fg="#ffffff",
            activebackground="#059669",
            activeforeground="#ffffff",
            font=FONT_SUBTITLE,
            relief="flat",
            padx=16,
            command=self.on_dispatch_prompt,
            cursor="hand2",
        )
        btn_send.pack(side="right", fill="y")

        # 5. Bottom Split: Live Task Board + Activity Log
        bottom_frame = tk.Frame(self, bg=BG_MAIN)
        bottom_frame.pack(fill="both", expand=True, padx=12, pady=(4, 12))

        # Tasks Table Frame (Left 60%)
        tasks_frame = tk.LabelFrame(
            bottom_frame,
            text=" Orchestrator Pipeline Tasks ",
            bg=BG_CARD,
            fg=TEXT_PRIMARY,
            font=FONT_SUBTITLE,
            relief="flat",
            highlightbackground=BORDER_COLOR,
            highlightthickness=1,
        )
        tasks_frame.pack(side="left", fill="both", expand=True, padx=(0, 6))

        # Task Action Toolbar
        task_toolbar = tk.Frame(tasks_frame, bg=BG_CARD)
        task_toolbar.pack(fill="x", padx=8, pady=(4, 4))

        btn_create_tasks = tk.Button(
            task_toolbar,
            text="➕ Create Sample Pipeline Tasks",
            font=FONT_BADGE,
            bg=BG_INPUT,
            fg=TEXT_PRIMARY,
            relief="flat",
            command=self.on_create_sample_tasks,
        )
        btn_create_tasks.pack(side="left", padx=2)

        # Treeview for tasks
        tree_cols = ("id", "stage", "status", "worker", "priority")
        self.tree = ttk.Treeview(tasks_frame, columns=tree_cols, show="headings", height=8)
        self.tree.heading("id", text="Task ID")
        self.tree.heading("stage", text="Stage")
        self.tree.heading("status", text="Status")
        self.tree.heading("worker", text="Assigned Worker")
        self.tree.heading("priority", text="Priority")

        self.tree.column("id", width=140, anchor="w")
        self.tree.column("stage", width=80, anchor="center")
        self.tree.column("status", width=80, anchor="center")
        self.tree.column("worker", width=100, anchor="center")
        self.tree.column("priority", width=60, anchor="center")

        self.tree.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        # Activity Log Frame (Right 40%)
        log_frame = tk.LabelFrame(
            bottom_frame,
            text=" Fleet Activity Log ",
            bg=BG_CARD,
            fg=TEXT_PRIMARY,
            font=FONT_SUBTITLE,
            relief="flat",
            highlightbackground=BORDER_COLOR,
            highlightthickness=1,
            width=380,
        )
        log_frame.pack(side="right", fill="both", padx=(6, 0))

        self.log_text = scrolledtext.ScrolledText(
            log_frame,
            bg=BG_INPUT,
            fg=TEXT_PRIMARY,
            insertbackground=TEXT_PRIMARY,
            relief="flat",
            font=FONT_MONO,
            width=45,
        )
        self.log_text.pack(fill="both", expand=True, padx=8, pady=8)

        self.log("Fleet Control Center GUI initialized.")

    # --- Logging Helper ---
    def log(self, message: str):
        now_str = time.strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{now_str}] {message}\n")
        self.log_text.see(tk.END)

    # --- Quick Templates ---
    def _set_template_orch(self):
        self.target_var.set("user1 (Orchestrator)")
        self.prompt_text.delete("1.0", tk.END)
        self.prompt_text.insert("1.0", "You are user1, the Fleet Orchestrator. Inspect active tasks using list_tasks and coordinate work.")

    def _set_template_research(self):
        self.target_var.set("user2 (Researcher)")
        self.prompt_text.delete("1.0", tk.END)
        self.prompt_text.insert("1.0", "You are user2 (Role: Researcher). Use claim_task to claim pending research tasks and call submit_task_checkpoint with findings.")

    def _set_template_draft(self):
        self.target_var.set("user3 (Writer)")
        self.prompt_text.delete("1.0", tk.END)
        self.prompt_text.insert("1.0", "You are user3 (Role: Writer). Use claim_task to claim draft tasks and call submit_task_checkpoint with drafted deliverable.")

    def _set_template_ping(self):
        self.target_var.set("⚡ Broadcast All")
        self.prompt_text.delete("1.0", tk.END)
        self.prompt_text.insert("1.0", "Autonomous Claude Fleet: check in and report status.")

    # --- Actions ---
    def on_launch_fleet(self):
        def _worker():
            self.log("Starting fleet launch on Desktop 2...")
            cmd = ["pwsh", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(LAUNCH_SCRIPT)]
            try:
                proc = subprocess.Popen(
                    cmd,
                    cwd=str(REPO_ROOT),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                )
                for line in proc.stdout:
                    clean = line.strip()
                    if clean:
                        self.log(clean)
                proc.wait()
                if proc.returncode == 0:
                    self.log("[SUCCESS] Fleet launched successfully.")
                else:
                    self.log(f"[!] Fleet launcher exited with code {proc.returncode}")
            except Exception as e:
                self.log(f"[ERROR] Launch failed: {e}")
            self.refresh_all_status()

        threading.Thread(target=_worker, daemon=True).start()

    def on_tile_windows(self):
        def _worker():
            attach_default_desktop()
            user32 = ctypes.windll.user32
            sw = user32.GetSystemMetrics(0)
            sh = user32.GetSystemMetrics(1)
            col_w = sw // 3

            fleet = self._load_fleet_data()
            hwnds = [inst.get("Hwnd") for inst in fleet if inst.get("Hwnd")]
            if not hwnds:
                self.log("[!] No active window handles found in active_fleet.json.")
                return

            self.log(f"Tiling {len(hwnds)} windows across {sw}x{sh} on Desktop 2...")
            import win32gui, win32con
            for i, h in enumerate(hwnds[:3]):
                if user32.IsWindow(h):
                    x = i * col_w
                    y = 0
                    w = col_w
                    h_win = sh - 40
                    win32gui.ShowWindow(h, win32con.SW_RESTORE)
                    win32gui.SetWindowPos(h, 0, x, y, w, h_win, win32con.SWP_NOZORDER | win32con.SWP_NOACTIVATE | win32con.SWP_SHOWWINDOW)
                    self.log(f"Snapped HWND {h} to ({x}, {y}, {w}, {h_win})")
            self.log("[SUCCESS] Windows snapped into 3-column layout.")

        threading.Thread(target=_worker, daemon=True).start()

    def on_switch_desktop(self, desk_num: int):
        def _worker():
            if VD_EXE.exists():
                self.log(f"Switching to Desktop {desk_num + 1}...")
                subprocess.run([str(VD_EXE), f"/Switch:{desk_num}"], capture_output=True)
                self.log(f"Switched to Desktop {desk_num + 1}.")
            else:
                self.log(f"[!] VirtualDesktop.exe not found at {VD_EXE}")

        threading.Thread(target=_worker, daemon=True).start()

    def on_dispatch_prompt(self):
        target_str = self.target_var.get()
        prompt = self.prompt_text.get("1.0", tk.END).strip()
        if not prompt:
            messagebox.showwarning("Warning", "Prompt cannot be empty.")
            return

        def _worker():
            from client.adapters.claude_desktop_cdp import ClaudeDesktopUIAAdapter
            fleet = self._load_fleet_data()

            if "Broadcast" in target_str:
                self.log(f"Broadcasting prompt to all {len(fleet)} instances...")
                for inst in fleet:
                    acc = inst.get("Account")
                    hwnd = inst.get("Hwnd")
                    if hwnd:
                        adapter = ClaudeDesktopUIAAdapter(worker_id=acc, nickname=acc, hwnd=hwnd)
                        res = asyncio.run(adapter.send_text(prompt))
                        tag = "[SUCCESS]" if res.get("success") else "[FAILED]"
                        self.log(f"  {tag} Dispatched to {acc} (HWND={hwnd})")
                        time.sleep(0.3)
                self.log("[SUCCESS] Broadcast completed.")
            else:
                acc = target_str.split()[0]
                target_inst = next((i for i in fleet if i.get("Account") == acc), None)
                if not target_inst or not target_inst.get("Hwnd"):
                    self.log(f"[!] Instance {acc} has no valid window HWND.")
                    return

                hwnd = target_inst.get("Hwnd")
                self.log(f"Dispatching prompt to {acc} (HWND={hwnd})...")
                adapter = ClaudeDesktopUIAAdapter(worker_id=acc, nickname=acc, hwnd=hwnd)
                res = asyncio.run(adapter.send_text(prompt))
                if res.get("success"):
                    self.log(f"[SUCCESS] Prompt dispatched to {acc} window and Enter submitted.")
                else:
                    self.log(f"[FAILED] Dispatch to {acc} failed: {res.get('error')}")

        threading.Thread(target=_worker, daemon=True).start()

    def on_create_sample_tasks(self):
        def _worker():
            self.log("Submitting sample research + draft pipeline tasks to Orchestrator...")
            tasks_data = [
                {
                    "stage": "research",
                    "kind": "text",
                    "spec": "Research the architectural benefits of multi-profile isolated Claude Desktop fleets vs session swapping.",
                    "priority": 10,
                },
                {
                    "stage": "draft",
                    "kind": "text",
                    "spec": "Draft the executive summary and key findings based on the research findings.",
                    "priority": 5,
                },
            ]
            try:
                for td in tasks_data:
                    r = httpx.post(f"{ORCHESTRATOR_URL}/tasks", json=td, timeout=4.0)
                    if r.status_code in (200, 201):
                        data = r.json()
                        self.log(f"  [+] Created Task: {data.get('id')} ({data.get('stage')})")
                    else:
                        self.log(f"  [!] Failed to create task: {r.status_code}")
                self.log("[SUCCESS] Sample tasks queued.")
                self.refresh_tasks()
            except Exception as e:
                self.log(f"[ERROR] Task creation failed: {e}")

        threading.Thread(target=_worker, daemon=True).start()

    # --- Status Polling & Updates ---
    def _load_fleet_data(self) -> list[dict]:
        if FLEET_JSON.exists():
            try:
                return json.loads(FLEET_JSON.read_text(encoding="utf-8"))
            except Exception:
                pass
        return []

    def refresh_all_status(self):
        threading.Thread(target=self._refresh_worker, daemon=True).start()

    def _refresh_worker(self):
        attach_default_desktop()
        user32 = ctypes.windll.user32
        fleet = self._load_fleet_data()
        fleet_map = {item.get("Account"): item for item in fleet}

        # Check FastAPI server health
        server_ok = False
        try:
            r = httpx.get("http://127.0.0.1:8000/api/v1/tasks", timeout=1.5)
            server_ok = (r.status_code == 200)
        except Exception:
            server_ok = False

        # Update server badge on main thread
        def _update_server_badge():
            if server_ok:
                self.server_badge.config(text="● ORCHESTRATOR: ONLINE (:8000)", fg=ACCENT_GREEN)
            else:
                self.server_badge.config(text="● ORCHESTRATOR: OFFLINE", fg=ACCENT_RED)
        self.after(0, _update_server_badge)

        # Update instance cards
        for acc, card_widgets in self.cards.items():
            inst = fleet_map.get(acc)
            hwnd = inst.get("Hwnd") if inst else None
            is_alive = bool(hwnd and user32.IsWindow(hwnd))

            def _update_card(a=acc, alive=is_alive, h=hwnd):
                widgets = self.cards[a]
                if alive:
                    widgets["status_badge"].config(text="● VISIBLE / READY", fg=ACCENT_GREEN, bg="#064e3b")
                    widgets["lbl_hwnd"].config(text=f"Window HWND: {h} (Desktop 2)", fg=TEXT_PRIMARY)
                else:
                    widgets["status_badge"].config(text="OFFLINE", fg=TEXT_MUTED, bg="#27272a")
                    widgets["lbl_hwnd"].config(text="Window HWND: Not Attached", fg=TEXT_MUTED)

            self.after(0, _update_card)

        # Refresh tasks
        self.refresh_tasks()

    def refresh_tasks(self):
        try:
            r = httpx.get(f"{ORCHESTRATOR_URL}/tasks", timeout=2.0)
            if r.status_code == 200:
                tasks = r.json()
                def _update_tree():
                    for item in self.tree.get_children():
                        self.tree.delete(item)
                    for t in tasks:
                        self.tree.insert(
                            "",
                            "end",
                            values=(
                                t.get("id"),
                                t.get("stage"),
                                t.get("status"),
                                t.get("owner_worker_id") or "-",
                                t.get("priority", 0),
                            ),
                        )
                self.after(0, _update_tree)
        except Exception:
            pass

    def _auto_refresh_loop(self):
        self.refresh_all_status()
        self.after(6000, self._auto_refresh_loop)


def main():
    app = FleetControlApp()
    app.mainloop()


if __name__ == "__main__":
    main()
