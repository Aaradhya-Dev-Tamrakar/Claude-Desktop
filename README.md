# Claude Desktop Multi-Profile Orchestration & FastMCP Ecosystem

Orchestrate multiple isolated Windows Claude Desktop accounts through terminal-independent PowerShell profile launching, stdio FastMCP coordination, and decentralized filesystem state contracts.

---

## 1. System Architecture & Core Workflow

This repository provides the interactive coordination hub for Claude Desktop on Windows. It operates with zero background terminal daemons and zero Chromium DevTools Protocol (CDP) browser puppeteering.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       INTERACTIVE CLAUDE DESKTOP PROFILES                   │
│   Account 1: Lead/Architect        Account 2: Builder/Coder       Account 6: QA Reviewer   │
│   (planning / scratchpad)          (workspace file I/O / code)    (adversarial audit)      │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │ stdio JSON-RPC (team-mcp.json)
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│          FAST MCP COORDINATION & FILE I/O SERVER (run_server.py)             │
│   get_context_bundle | init_scratchpad | append_scratchpad | submit_review  │
│   write_file_to_workspace | read_workspace_file | submit_checkpoint        │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │ Plain JSON & Markdown State
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                 FILESYSTEM COORDINATION STATE (orchestrator-state/)         │
│   tasks/          checkpoints/      qa-reviews/      live-status/          │
│   (spec/status)   (deliverables)    (pass/fail)      (heartbeats)          │
│   ─────────────────────────────────────────────────────────────             │
│   scratchpads/shared_scratchpad.md (Multi-Account Shared Blackboard)        │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Key Principles

1. **Terminal Independence**:
   - Profiles launch via `launch.bat` using PowerShell's detached `Start-Process`.
   - Once Claude Desktop starts, the launcher terminal closes immediately without interrupting Claude Desktop or its stdio MCP child processes.
2. **Automatic Instance Teardown**:
   - In Isolated Mode (Option `1`, default), the launcher detects and terminates prior running Claude Desktop instances before configuring and starting the selected profile.
3. **Manual Version Control**:
   - Automatic Git commit spam on profile launch is disabled.
   - All repository synchronization runs deliberately through `.\sync.bat`.
4. **Direct In-Workspace File I/O**:
   - Claude Desktop instances call `write_file_to_workspace` and `read_workspace_file` to inspect and write repository code directly on disk, eliminating manual clipboard transfer.
5. **Decoupled Headless Execution**:
   - Background batch processing, REST schedulers, and autonomous Copilot queue workers reside in the companion repository: [`Fleet-Orchestrator`](../Fleet-Orchestrator).

---

## 2. Scope Boundaries & Architectural Non-Goals

To maintain system reliability and prevent operational drift, this repository enforces strict architectural boundaries:

- **Zero Browser Automation**: Chromium DevTools Protocol (CDP) port automation (ports 9222–9229) is retired. All legacy browser scripts are archived in `legacy/`. Claude Desktop operates strictly as an interactive native Windows desktop application.
- **Zero Background Daemons**: Launching a profile spawns no long-running PowerShell daemons. Claude Desktop communicates with FastMCP tools via standard stdio pipes managed by the Electron runtime.
- **Zero Headless Worker Fleets**: Headless Copilot worker daemons, FastAPI HTTP endpoints, SQLite WAL task queues, and multi-account credit pooling belong exclusively to `Fleet-Orchestrator`.
- **Zero Automatic Commit Churn**: Opening or closing profiles never generates automated git commits. Version control is explicit and verified before each push.

---

## 3. Verified Empirical Metrics

Every release and architectural change must satisfy local deterministic verification gates before merging:

| Subsystem | Metric | Verification Command |
| :--- | :--- | :--- |
| **FastMCP Server** | 37 / 37 passed (100%) | `pytest tests/orchestrator_mcp_test.py -q` |
| **PowerShell Launcher** | 51 / 51 passed (100%) | `pwsh -Command "Invoke-Pester .\tests\launch_user_n.Tests.ps1 -Output Detailed"` |
| **MCP Tool Surface** | 27 registered tools | `mcp-servers/orchestrator-mcp/run_server.py` |
| **Configured Profiles** | 26 isolated accounts | `%USERPROFILE%\.claude-profiles` |

---

## 4. Repository Structure

```
Claude-Desktop/
├── launch.bat                     # Double-click launcher wrapper for Claude Desktop profiles
├── launch_user_n.ps1              # Core launcher: profile swap, instance teardown, detached GUI launch
├── sync.bat                       # Windows git sync entrypoint (PowerShell ExecutionPolicy bypass)
├── sync.ps1                       # Git sync engine: pull --rebase, secret scan, commit, push
├── sync-mcp.ps1                   # Syncs team-mcp.json into all Claude Desktop profile configs
├── profiles.json                  # Account name -> nickname/paths/role metadata map
├── team-mcp.json                  # Shared MCP config (orchestrator-mcp, notebooklm-mcp, md2pdf, super-nlm)
├── team-claude-config.json        # Sanitized team-wide Claude desktop config template
├── team-context.md                # Static identity scaffold, read via get_context_bundle
├── team-memory.md                 # Shared memory log, auto-appended by sync.ps1 + manual entries
├── AGENTS.md                      # Authoritative single source of truth for agent rules & workflows
├── GEMINI.md                      # Agent rules pointer referencing AGENTS.md
├── README.md                      # Repository documentation and architecture guide
├── LICENSE
│
├── orchestrator-state/            # Filesystem coordination state contract
│   ├── SCHEMA.md                  # File contract & invariant documentation
│   ├── tasks/                     # Task definitions (kind: code|text, status: pending|claimed|done|merged)
│   ├── checkpoints/               # Deliverables (commit_sha, branch_name, summary, result_text)
│   ├── qa-reviews/                # Adversarial QA audit results (verdict: pass|fail|revision_needed)
│   ├── live-status/               # Individual worker heartbeats (last-write-wins)
│   ├── scratchpads/               # Shared multi-account collaboration scratchpads
│   └── memory/                    # Shared immutable team-memory entries
│
├── mcp-servers/
│   ├── orchestrator-mcp/          # FastMCP coordination server with direct workspace file I/O
│   │   ├── requirements.txt
│   │   └── run_server.py
│   ├── notebooklm-mcp/            # uvx launcher for NotebookLM MCP server
│   ├── md2pdf-mcp/                # Markdown-to-PDF generation MCP server
│   └── super-nlm-mcp/             # Launcher shim for multi-account Super-NLM MCP
│
├── worker-prompts/                # Specialized role system prompts & setup guides
│   ├── CLAUDE_DESKTOP_PROFILES.md # Copy-pasteable Custom Instructions for Claude Desktop GUI
│   ├── orchestrator.md            # Lead Architect system prompt
│   ├── coder.md                   # Builder / Implementation Engineer system prompt
│   ├── qa-reviewer.md             # Adversarial QA Reviewer system prompt
│   ├── researcher.md              # Research Scout prompt
│   ├── writer.md                  # Copywriter prompt
│   ├── seo-optimizer.md           # SEO optimization prompt
│   └── formatter.md               # Formatting & schema compliance prompt
│
├── tools/
│   └── md2pdf_app.py              # CLI and rendering engine for md2pdf
│
└── tests/
    ├── orchestrator_mcp_test.py   # Full FastMCP test suite (37 specs)
    └── launch_user_n.Tests.ps1    # Pester specs for profile launcher (51 specs)
```

---

## 5. Quick Start

### 1. Launching Claude Desktop
Double-click [`launch.bat`](launch.bat) or run from PowerShell:
```powershell
.\launch.bat -Account user1
```
- Select your profile from the interactive table.
- In Isolated mode (Option `1`), any other running Claude instances will be cleanly closed before starting the selected profile.
- Once Claude Desktop starts, you can close the terminal window immediately.

### 2. Synchronizing MCP Tools Across Profiles
To propagate [`team-mcp.json`](team-mcp.json) into all installed user profiles in `%USERPROFILE%\.claude-profiles`:
```powershell
pwsh -File .\sync-mcp.ps1
```

### 3. Running Verification Gates
```powershell
# 1. FastMCP test suite (37 tests)
pytest tests/orchestrator_mcp_test.py -v

# 2. PowerShell / Pester launcher suite (51 tests)
pwsh -Command "Invoke-Pester .\tests\launch_user_n.Tests.ps1 -Output Detailed"

# 3. Repository state self-healing & secret scan
python scripts/ci_self_healing.py --heal
```

### 4. Synchronizing Repository Changes
All version control runs through `.\sync.bat`:
```powershell
.\sync.bat -m "type(scope): summary (#issue_id)"
```
To preview pending changes without touching git state:
```powershell
.\sync.bat -WhatIf
```
