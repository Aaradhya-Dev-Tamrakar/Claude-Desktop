# Handoff: Claude-Desktop Multi-Account Orchestration & Shared Scratchpad Architecture

**Target Repository:** `F:\Aaradhya-Dev-Tamrakar\Claude-Desktop`  
**Date:** 2026-10-08  
**Working Branch:** `main` (clean, synced with `origin/main`)  
**Companion Repos:** `Fleet-Orchestrator` (`F:\Aaradhya-Dev-Tamrakar\Fleet-Orchestrator`), `brainstorm` (`F:\Aaradhya-Dev-Tamrakar\brainstorm`)

---

## 1. System Context & Architectural Vision

This repository implements **pure intra-Claude Desktop multi-account orchestration**. 

### Core Operating Principle (Zero External Switching):
- **No Ecosystem Hopping**: All planning, implementation, and review work happens **strictly within Claude Desktop instances** across the user's multiple Claude Desktop accounts (`user1`, `user2`, `user3`, `user4`, etc.). Switching across tools or to external CLI fleets is unnecessary overhead.
- **Shared Persistent Scratchpad**: All Claude Desktop accounts share a common markdown scratchpad (`orchestrator-state/scratchpads/<scratchpad_id>_scratchpad.md`).
- **Serial & Parallel Multi-Account Flow**:
  - When Account 1 hits rate limits, Account 2 reads the scratchpad via `get_context_bundle()` and resumes instantly with zero lost context.
  - Or Account 1 acts as Lead/Architect (decomposing specs), Account 2 acts as Developer/Coder (implementing code and testing in the local repo), and Account 3 acts as QA Auditor.
- **Zero-Daemon Stdio Architecture**: Each Claude Desktop profile talks to `mcp-servers/orchestrator-mcp/run_server.py` over stdio via `team-mcp.json`. No CDP browser puppeteering, no port scanning, no Electron window management.
- **Thinking-Off / Low-Effort Transition Invariant**: Model selection and thinking effort cannot be changed automatically via MCP tools. When initiating a transition handoff, the **very first line of the agent's response must instruct the user to toggle thinking OFF (or switch to low effort)** in the Claude Desktop UI before recording the handoff note.

```
┌─────────────────────────┐     ┌─────────────────────────┐     ┌─────────────────────────┐
│ Claude Profile: user1   │     │ Claude Profile: user2   │     │ Claude Profile: user3   │
│ (Lead / Architect)      │     │ (Builder / Developer)   │     │ (Reviewer / QA)         │
└───────────┬─────────────┘     └───────────┬─────────────┘     └───────────┬─────────────┘
            │                               │                               │
            │ create_task / init_scratchpad │ append_scratchpad / checkpoint│ submit_qa_review
            ▼                               ▼                               ▼
═════════════════════════════════════════════════════════════════════════════════════════════
                   LOCAL ORCHESTRATOR STATE (Plain JSON & Markdown)
  • orchestrator-state/scratchpads/shared_scratchpad.md (Shared live working document)
  • orchestrator-state/tasks/<task_id>.json            (Atomic task units)
  • orchestrator-state/checkpoints/<task_id>.json      (Completed deliverables)
  • orchestrator-state/qa-reviews/<task_id>.json       (Audit verdicts)
═════════════════════════════════════════════════════════════════════════════════════════════
```

---

## 2. Current State & Assets in `Claude-Desktop`

1. **`mcp-servers/orchestrator-mcp/run_server.py`**:
   - FastMCP stdio server registering **27 native MCP tools**.
   - **Shared Scratchpad Tools**:
     - `init_scratchpad(scratchpad_id="shared", title="...", spec="...", author="...")`
     - `read_scratchpad(scratchpad_id="shared")`
     - `append_scratchpad(content="...", author="...", scratchpad_id="shared", heading="...")`
     - `overwrite_scratchpad(content="...", author="...", scratchpad_id="shared")`
   - **Workspace File I/O Tools**:
     - `write_file_to_workspace(rel_path="...", content="...", overwrite=False)`
     - `read_workspace_file(rel_path="...")`
   - **Task Lifecycle Tools**:
     - `create_task`, `decompose_task`, `claim_task`, `release_task`, `mark_blocked`, `unblock_task`
     - `submit_checkpoint`, `list_tasks`, `merge_results`
     - `submit_qa_review`, `create_job`, `list_jobs`, `get_job_metrics`
   - **Context & Memory Tools**:
     - `get_context_bundle(account, scratchpad_id="shared")` (Single-call bootstrap returning scratchpad, team context, recent memory, active tasks, and active workers).
     - `push_memory_entry`, `read_team_memory`, `archive_memory`, `read_team_context`, `push_live_status`, `read_all_live_status`, `read_worker_roles`
   - **Local Verification Metrics**:
     - **37 / 37 passing pytest specs** in `tests/orchestrator_mcp_test.py` (FastMCP contracts, workspace file I/O, concurrency guards).
     - **51 / 51 passing Pester specs** in `tests/launch_user_n.Tests.ps1` (profile parsing, table rendering, MCP sync).

2. **File State Directory (`orchestrator-state/`)**:
   - `scratchpads/`: Shared markdown logs for cross-account handoffs.
   - `tasks/`: Task specifications and claim states.
   - `checkpoints/`: Milestone reports and commit hashes.
   - `qa-reviews/`: Formal verification logs.
   - `live-status/`: Per-account status lights.
   - `memory/`: Timestamped cross-session memory notes.

3. **`team-mcp.json`**:
   - Standard MCP config registering `orchestrator-mcp` for Claude Desktop profiles.

---

## 3. Completed Architecture & Active Backlog

1. **Completed Core Milestones**:
   - **Profile Launcher & Instance Teardown**: `launch.bat` and `launch_user_n.ps1` handle interactive profile selection, automatic cleanup of stale Claude instances in Isolated Mode, Win32 parent process reparenting (`PROC_THREAD_ATTRIBUTE_PARENT_PROCESS`) to `explorer.exe` to guarantee Job Object detachment from Windows Terminal, and console output suppression via `ELECTRON_NO_ATTACH_CONSOLE=1`. Documented in [`docs/how-we-decoupled-claude-desktop-from-windows-terminal-job-object.md`](docs/how-we-decoupled-claude-desktop-from-windows-terminal-job-object.md).
   - **Headless Fleet Decoupling (#8)**: Pruned 10,700 lines of headless Copilot workers and web servers from this repository, preserving Claude-Desktop strictly as the human-in-the-loop desktop hub while delegating background execution to `Fleet-Orchestrator`.
   - **FastMCP In-Workspace File I/O**: Implemented `write_file_to_workspace` and `read_workspace_file` with directory traversal guards, enabling direct repository code changes from Claude Desktop without manual copy-pasting.
   - **Profile Custom Instructions**: Formulated token-optimized custom instructions in `worker-prompts/CLAUDE_DESKTOP_PROFILES.md` for Lead Architect, Builder, and QA Reviewer personas.

2. **Active Backlog**:
   - **Documentation Refinement**: Keep documentation aligned with the calm-authority engineering standard (`blog-writing-like-claude`), documenting exact metrics and explicit scope boundaries.
   - **Profile Token Optimization**: Monitor session token churn across repeated `get_context_bundle` calls and tune scratchpad pruning thresholds.

---

## 4. Operational Invariants & Rules

- **Zero Raw Git Commands**: Never run raw `git add`, `git commit`, or `git push`. Always execute `.\sync.bat` (or `.\sync.ps1`).
- **Strict File Contract**: Adhere strictly to `orchestrator-state/SCHEMA.md` (one entity per file; zero shared multi-account writes).
- **Strictly No CDP / Electron Automation**: Keep Claude Desktop purely as an interactive desktop app communicating over stdio MCP.
