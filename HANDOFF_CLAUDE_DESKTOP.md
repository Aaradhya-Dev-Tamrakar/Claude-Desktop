# Handoff: Claude-Desktop Orchestration & Native MCP Architecture

**Target Repository:** `F:\Aaradhya-Dev-Tamrakar\Claude-Desktop`  
**Date:** 2026-10-08  
**Working Branch:** `main` (clean, synced with `origin/main`)  
**Companion Repos:** `Fleet-Orchestrator` (`F:\Aaradhya-Dev-Tamrakar\Fleet-Orchestrator`), `brainstorm` (`F:\Aaradhya-Dev-Tamrakar\brainstorm`)

---

## 1. System Context & Architecture Overview

`Claude-Desktop` serves as the **interactive planning, decomposition, and adversarial QA review hub** for the multi-tier agent ecosystem. 

### Key Architectural Shift (Decoupling from CDP):
- **Discarded Fragile Automation**: Browser automation via Chromium DevTools Protocol (CDP port scanning `9222-9225`, multi-window Electron instances consuming 1.17 GB RAM per window, virtual desktops) has been **fully abandoned** due to high operational management overhead.
- **Adopted Looser Stdio File-Based Coordination**: Claude Desktop operates normally as an interactive GUI client and interfaces natively with local tools via standard stdio JSON-RPC (`team-mcp.json`).
- **Zero-Daemon Filesystem Coordination**: All coordination state is externalized in plain JSON files under `orchestrator-state/`. There are no background daemons, locks, or network dependencies for Claude.

```
[Claude Desktop (Any Profile)]
       │
       ▼ (create_task / decompose_task via orchestrator-mcp stdio)
[orchestrator-state/tasks/task_*.json]
       │
       ▼ (launch_copilot_worker.bat polls & claims task)
[Copilot CLI (27-Worker Fleet)] ──> writes ──> [orchestrator-state/checkpoints/task_*.json]
       │
       ▼ (submit_qa_review via Claude Desktop UI)
[orchestrator-state/qa-reviews/task_*.json]
       │
       ▼ (User final audit & commit)
[.\sync.bat]
```

---

## 2. Current State & Assets in `Claude-Desktop`

1. **`mcp-servers/orchestrator-mcp/run_server.py`**:
   - 1,009-line robust FastMCP stdio server.
   - Core tools registered:
     - `create_task(spec, kind, parent_id, created_by)`
     - `decompose_task(parent_id, subtask_specs, kind, created_by)`
     - `claim_task(task_id, account, branch_name)`
     - `submit_checkpoint(task_id, account, summary, result_text, branch_name, commit_sha)`
     - `submit_qa_review(task_id, reviewer_account, verdict, notes)`
     - `list_tasks(status, parent_id, kind)`
     - `get_context_bundle(account, memory_limit, memory_hours)`
     - `push_memory_entry(account, text, tags, priority)`
     - `read_team_memory(since, limit, project)`
   - Verified with 29/29 passing tests in `tests/orchestrator_mcp_test.py`.

2. **`orchestrator-state/` Directory Contract**:
   - `tasks/<task_id>.json`: Task definitions (`kind: "code"|"text"`, `status: "pending"|"claimed"|"done"|"blocked"`).
   - `checkpoints/<task_id>.json`: Code executor deliverables with git branch & commit SHA.
   - `qa-reviews/<task_id>.json`: Claude Desktop QA audit results with pass/fail verdicts.
   - `live-status/<account>.json`: Status lights per worker.
   - `memory/<account>__<entry_id>.json`: Shared team knowledge memory entries.

3. **`launch_copilot_worker.bat`**:
   - One-click runner executing `..\Fleet-Orchestrator\tools\copilot_queue_worker.py` pointing to `orchestrator-state/`.

4. **`team-mcp.json`**:
   - MCP client config registering `orchestrator-mcp` for Claude Desktop profiles.

---

## 3. Immediate Objectives & Backlog for This Session

1. **Profile Prompts & Guidelines Hardening**:
   - Provide standard system prompt snippets or custom instructions for Claude Desktop profiles (e.g. Architect/Planner, QA Reviewer) to optimize token efficiency when interacting with `orchestrator-mcp`.
   - Enforce bootstrap convention: use `get_context_bundle(account="...", ...)` rather than multiple distinct round-trips.

2. **Clean Up Legacy CDP Artifacts**:
   - Review and safely deprecate or archive legacy CDP launcher scripts (`launch_user_n.ps1`, `launch-gui.bat`, `close.bat`, `VirtualDesktop.exe`) into an `archive/` or `legacy/` directory to prevent confusion.
   - Ensure documentation (`README.md`, `team-context.md`) reflects the clean file-based stdio architecture.

3. **Interactive End-to-End Workflow Validation**:
   - Conduct a live verification: Create a task in Claude Desktop via `create_task`, observe `launch_copilot_worker.bat` pickup and completion, and run `submit_qa_review` from Claude Desktop.

---

## 4. Operational Invariants & Rules

- **Zero Raw Git Commands**: Never run raw `git add`, `git commit`, or `git push`. Always run `.\sync.bat` (or `.\sync.ps1`).
- **Strict File Contract**: Adhere strictly to `orchestrator-state/SCHEMA.md`. Never create shared files edited concurrently by multiple entities.
- **Zero CDP / Electron Scraping**: Do not reintroduce browser automation, websockets, or port polling. Claude Desktop is purely an interactive desktop client.
