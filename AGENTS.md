# Agent Rules & Workflow Guidelines — Claude-Desktop Ecosystem

Welcome, Agent. This repository (`F:\Aaradhya-Dev-Tamrakar\Claude-Desktop`) serves as the **interactive planning, architectural decomposition, and adversarial QA review hub** for the multi-tier agent ecosystem.

To preserve repository integrity, eliminate fragile browser automation, prevent merge collisions, and enforce deterministic verification, you **MUST** strictly adhere to the following operating principles.

---

## 1. Git Workflow & Ecosystem Automation (CRITICAL — STRICT ENFORCEMENT)

To avoid breaking multi-account coordination and prevent wasteful multi-step Git conflicts, **NEVER run individual `git add`, `git commit`, `git push`, or `git pull` commands directly.**

**ALWAYS execute `.\sync.bat` (or `.\sync.ps1`) for repository synchronization and version control.**  
*(Note: `.\sync.bat` is the zero-friction execution wrapper that automatically bypasses PowerShell ExecutionPolicy restrictions across Windows machines).*

### Core Version Control Commands

- **Routine / Minor Sync**:
  ```powershell
  .\sync.bat                              # or .\sync.ps1
  ```
  _Automatically runs pre-commit secret scans, checks branch health, detects uncommitted changes, formats conventional commits with diff churn stats, and pushes with `--rebase --autostash` safety._

- **Major Features / Architectural Changes**:
  ```powershell
  .\sync.bat -m "feat(scope): detailed architectural commit summary"
  ```

- **Skip CI for Operational / Doc Commits**:
  ```powershell
  .\sync.bat -SkipCI                      # or .\sync.bat -m "docs: notes" -SkipCI
  ```
  _Explicitly appends `[skip ci]` to bypass GitHub Actions runner matrix. Automatically auto-detected when only operational state, memory dumps, or markdown files are staged._

- **Safe Pull Only**:
  ```powershell
  .\sync.bat -PullOnly
  ```

- **Dry-Run Mode (Preview changes without touching Git state)**:
  ```powershell
  .\sync.bat -WhatIf
  ```

---

## 2. GitHub Development Workflow (`github-workflow`)

The repository enforces a calibrated dual-track development model balancing founder velocity with strict institutional governance:

- **Track A: Solo Maintainer Velocity Bridge**:
  Direct commits and pushes via `.\sync.bat -m "..."` are authorized strictly for the solo repository administrator, provided local deterministic verification gates (`pytest`) pass 100% prior to pushing.

- **Track B: Feature Branch & Contributor Pull Request Standard**:
  All multi-step feature work, bug fixes, and non-trivial refactors **MUST** execute the standard GitHub Flow:
  1. **Issue Anchoring**: Formulate requirements with acceptance tasks (`- [ ]`) and create a tracked issue with full metadata (`gh issue create --assignee "AaradhyaDT" --label "<labels>"`).
  2. **Branch Isolation**: Branch off `main` via `<type>/<slug>-#<ID>` (e.g. `refactor/repo-curation-#3`), never committing multi-step changes directly to `main`.
  3. **Progressive Task Tracking**: Check off acceptance criteria progressively using `toggle-issue-task` / `gh-task`:
     ```bash
     gh-task --issue <ID> --task "<keyword>"
     ```
  4. **Verification Gate**: Enforce local test suite clean passes (`pytest tests/orchestrator_mcp_test.py`) before staging.
  5. **Ecosystem Synchronization**: Synchronize commits and push the isolated branch using `.\sync.bat -m "type(scope): summary (#ID)"`.
  6. **Pull Request & Review Dispatch**:
     Open PR via GitHub CLI with complete metadata, explicit usernames, and issue resolution keywords:
     ```bash
     gh pr create \
       --base main \
       --head <branch> \
       --title "type(scope): summary (#ID)" \
       --assignee "AaradhyaDT" \
       --label "<labels>" \
       --body "## Summary\n...\n\nCloses #<ID>\n\n## Verification\n- pytest: 34 passed"
     ```
     > [!IMPORTANT]
     > - **Never use `@me` in multi-developer repositories**: Always use explicit usernames (`--assignee AaradhyaDT`) so PRs are deterministically assigned.
     > - **Never use organization names as reviewer/assignee**: Use personal GitHub handles.
     > - **Reciprocal Review Standard**: Follow the project's peer review convention.

---

## 3. Architecture & Zero-CDP Invariants

1. **Decoupled Stdio FastMCP Coordination (Zero-CDP)**:
   - Chromium DevTools Protocol (CDP) puppeteering (`ports 9222-9229`, multi-window Electron instances consuming 1.17 GB RAM per window, virtual desktops) is **permanently retired**. All legacy scripts reside in [`legacy/`](legacy/).
   - Claude Desktop operates normally as an interactive desktop client communicating via standard stdio JSON-RPC (`team-mcp.json`).
   - The primary coordination engine is `mcp-servers/orchestrator-mcp/run_server.py`.
2. **Filesystem Coordination State Contract (`orchestrator-state/SCHEMA.md`)**:
   - `tasks/<task_id>.json`: Task definitions (`kind: "code"|"text"`, `status: "pending"|"claimed"|"done"|"merged"`).
   - `checkpoints/<task_id>.json`: Deliverable checkpoints with git commit SHAs, branch names, and summaries.
   - `qa-reviews/<task_id>.json`: Adversarial QA audit results with verdicts (`pass`, `fail`, `revision_needed`).
   - `live-status/<account>.json`: Individual worker heartbeats (last-write-wins, zero shared-file races).
   - `scratchpads/<scratchpad_id>_scratchpad.md`: Shared multi-account workspace blackboard.
3. **One Entity Per File Invariant**:
   - Never write to a shared multi-account file concurrently. Every entity is its own file to guarantee zero Git rebase collisions during sync.

---

## 4. Multi-Account Shared Scratchpad Protocol

Coordination across multiple Claude Desktop accounts (`user1` Lead, `user2` Coder, `user6` QA Reviewer) operates through the shared scratchpad:

1. **Mandatory Single-Call Session Bootstrap**:
   On the very first turn of any session, ALWAYS call:
   ```python
   get_context_bundle(account="<account>", memory_limit=5, memory_hours=24, scratchpad_id="shared")
   ```
   *Strictly avoid individual round-trips to `read_team_context`, `read_team_memory`, `list_tasks`, `read_all_live_status`, or `read_scratchpad`.*
2. **Inter-Account Handoffs**:
   - When completing an implementation step, submitting a checkpoint, or approaching context/message limits, append a high-signal handoff note:
     ```python
     append_scratchpad(
         content="Completed <work>. Next account should run test suite and submit QA review.",
         author="<account>",
         scratchpad_id="shared",
         heading="Session Handoff"
     )
     ```
3. **Cognitive Separation**:
   - **Architect / Lead (`user1` `adevtmr`)**: Initializes scratchpad, decomposes tasks via `create_task`, delegates work, synthesizes final merges via `merge_results`.
   - **Builder / Coder (`user2` `dev83`)**: Claims code tasks via `claim_task`, implements edits in the workspace, verifies tests, submits checkpoints via `submit_checkpoint`, and logs progress to scratchpad.
   - **Adversarial QA Reviewer (`user6` `adt_ieee`)**: Audits deliverables against task specs, authentic git commit SHAs, and test proofs. Submits verdicts via `submit_qa_review` (`pass` $\to$ `merged`, `revision_needed` $\to$ `pending` for rework).

---

## 5. Release SHA & Commit History Integrity

- **Zero Synthetic Placeholders**: NEVER use placeholder or synthetic strings (e.g., `rel50`, `rel55`, `upg47`) when documenting version releases, handoffs, or commit history.
- **Authentic Git SHAs**: Every commit reference must resolve to an authentic 7–40 hex Git commit SHA.

---

## 6. Collaborative Privacy & Boundary Isolation (Zero Personal Leakage)

> [!CAUTION]
> **Never commit personal developer resources into collaborative/public repositories.**
> Personal NotebookLM IDs, private journals, personal notes, and local machine configs found in global agent rules are strictly for local assistant tooling context. They must **never** be written into shared repository documentation, Markdown files, or committed artifacts.

---

## 7. Verification Gates & Self-Healing Pipeline

Before completing any task or syncing changes:
1. **Self-Healing Integrity & Secret Audit**:
   ```powershell
   python scripts/ci_self_healing.py --heal
   ```
   *Scans and normalizes `orchestrator-state/` entities, validates repository invariants, and guards against credential leaks.*

2. **Local Python FastMCP Test Suite**:
   ```powershell
   pytest tests/orchestrator_mcp_test.py -q --tb=short
   ```
   *Runs all 37 FastMCP orchestrator and workspace file I/O invariant specs (Target: 0 failures).*

3. **PowerShell Automation & Pester Suite**:
   ```powershell
   Invoke-Pester .\tests\launch_user_n.Tests.ps1 -Output Detailed
   ```
   *Runs all 51 Pester specs across profile parsing, layout calculation, and MCP merges.*

4. **Integration Lifecycle Checks**:
   ```powershell
   python scripts/test_e2e_task_lifecycle.py
   python scripts/test_multi_account_scratchpad_handshake.py
   ```
   *Exercises the cross-account task lifecycle and scratchpad handshakes.*

---

## 8. Architectural Boundary: Claude-Desktop vs. Fleet-Orchestrator

- **`Claude-Desktop` (This Hub)**: Dedicated solely to the interactive Claude Desktop application on Windows. Governs multi-account profile swapping (`launch.bat`, `launch_user_n.ps1`), terminal-independent GUI launches, isolated instance teardown, manual version control (`sync.bat`), shared scratchpads, and native stdio FastMCP tools with direct workspace file read/write capabilities (`write_file_to_workspace`, `read_workspace_file`).
- **`Fleet-Orchestrator` (`F:\Aaradhya-Dev-Tamrakar\Fleet-Orchestrator`)**: The companion headless automation engine. Hosts the FastAPI coordinator, SQLite WAL databases, Copilot CLI adapters, background queue workers (`copilot_queue_worker.py`), multi-account credit pooling, and synthetic benchmark suites.
