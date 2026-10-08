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
   - FastMCP stdio server registering **25 native MCP tools**.
   - **Shared Scratchpad Tools**:
     - `init_scratchpad(scratchpad_id="shared", title="...", spec="...", author="...")`
     - `read_scratchpad(scratchpad_id="shared")`
     - `append_scratchpad(content="...", author="...", scratchpad_id="shared", heading="...")`
     - `overwrite_scratchpad(content="...", author="...", scratchpad_id="shared")`
   - **Task Lifecycle Tools**:
     - `create_task`, `decompose_task`, `claim_task`, `release_task`, `mark_blocked`, `unblock_task`
     - `submit_checkpoint`, `list_tasks`, `merge_results`
     - `submit_qa_review`, `create_job`, `list_jobs`, `get_job_metrics`
   - **Context & Memory Tools**:
     - `get_context_bundle(account, scratchpad_id="shared")` (Single-call bootstrap returning scratchpad, team context, recent memory, active tasks, and active workers).
     - `push_memory_entry`, `read_team_memory`, `archive_memory`, `read_team_context`, `push_live_status`, `read_all_live_status`
   - **100% Passing Tests**: **34 / 34 pytest specs passing** in `tests/orchestrator_mcp_test.py`.

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

## 3. Immediate Objectives & Backlog for This Session

1. **Profile Prompts & Instructions Customization**:
   - Write standard instructions/prompt snippets for Claude Desktop profiles to maximize token efficiency:
     - Bootstrap via `get_context_bundle(account="<my_profile>", scratchpad_id="shared")`.
     - Read the shared scratchpad first to immediately understand current state.
     - Document intermediate findings and handoff state via `append_scratchpad`.
2. **Clean Up Legacy CDP Artifacts**:
   - Safely move obsolete CDP launcher scripts (`launch_user_n.ps1`, `launch-gui.bat`, `close.bat`, `VirtualDesktop.exe`) into an `archive/cdp_legacy/` folder to clean the root namespace.
3. **Validate Intra-Claude Multi-Account Handshake**:
   - Simulate/verify a 2-account workflow in Claude Desktop:
     - Profile A initializes the scratchpad and decomposes a task.
     - Profile B boots up, reads the scratchpad in its context bundle, claims the task, implements it, appends its completion notes, and submits checkpoint.
     - Profile A or C inspects the checkpoint and submits QA review.

---

## 4. Operational Invariants & Rules

- **Zero Raw Git Commands**: Never run raw `git add`, `git commit`, or `git push`. Always execute `.\sync.bat` (or `.\sync.ps1`).
- **Strict File Contract**: Adhere strictly to `orchestrator-state/SCHEMA.md` (one entity per file; zero shared multi-account writes).
- **Strictly No CDP / Electron Automation**: Keep Claude Desktop purely as an interactive desktop app communicating over stdio MCP.
