# Legacy Chrome DevTools Protocol (CDP) & Multi-Window Runner Archive

This directory contains deprecated Chromium DevTools Protocol (CDP) automation, multi-window Electron launcher scripts, and virtual desktop window management utilities originally developed for unattended Claude Desktop automation.

---

## 1. Archived Components

| Component | Original Purpose | Deprecation Rationale |
| :--- | :--- | :--- |
| `launch_user_n.ps1` | Multi-profile launcher supporting isolated profile swap and concurrent windows with CDP remote debugging ports (`--remote-debugging-port=9222..9229`). | Discarded due to 1.17 GB RAM overhead per Electron window, port collisions, focus-stealing, and fragility of UI-based prompt injection. |
| `launch.bat` | Double-click Windows Explorer wrapper for `launch_user_n.ps1`. | Retired alongside `launch_user_n.ps1`. |
| `launch-gui.bat` / `launch-gui.ps1` | Interactive Tkinter GUI launcher for launching multi-window fleet. | Replaced by direct Claude Desktop interactive GUI usage + stdio FastMCP. |
| `launch-fleet.ps1` | Multi-instance virtual desktop fleet launcher. | Replaced by decoupled background Copilot queue workers. |
| `close.bat` | Hook to kill all running Claude Desktop instances. | No longer needed for single-window interactive use. |
| `fleet_gui.py` | Tkinter desktop application managing virtual desktops, window tiling, and CDP injection. | Retired along with the multi-window CDP architecture. |
| `VirtualDesktop.exe` / `.cs` | Win32 virtual desktop manipulation CLI (P/Invoke to internal `IVirtualDesktopManagerInternal` APIs). | Deprecated as dedicated virtual desktops are no longer required. |
| `find_live_windows.py` | Win32 API window title and HWND inspection. | Retired CDP diagnostic utility. |
| `restore_claude_window.py` | Win32 API window activation and restore helper. | Retired CDP diagnostic utility. |
| `launch_and_test_live_claude.py` | Live test runner spawning Claude and connecting via websockets. | Retired CDP test runner. |

---

## 2. Modern Architecture Replacement

- **Interactive Claude Desktop**: Claude Desktop operates normally as an interactive desktop client communicating via standard stdio JSON-RPC (`team-mcp.json`).
- **MCP Server**: FastMCP stdio server at `mcp-servers/orchestrator-mcp/run_server.py` exposing atomic tools (`create_task`, `claim_task`, `submit_checkpoint`, `submit_qa_review`, `get_context_bundle`, `init_scratchpad`, `append_scratchpad`).
- **Filesystem State Contract**: All state is externalized in plain JSON files under `orchestrator-state/` (`tasks/`, `checkpoints/`, `qa-reviews/`, `live-status/`, `scratchpads/`).
- **Code Execution**: Headless background queue workers (`launch_copilot_worker.bat` / `copilot_queue_worker.py`) poll `orchestrator-state/tasks` for `kind: "code"`, claim tasks, execute via Copilot CLI in isolated worktrees, write checkpoints, and mark tasks `done`.
- **Adversarial QA Gate**: Reviewer Claude profiles perform verification via `submit_qa_review`.
