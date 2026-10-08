# Claude Desktop Multi-Profile Orchestration & FastMCP Ecosystem

PowerShell automation, terminal-independent profile launching, stdio FastMCP servers, and decentralized filesystem state contracts to orchestrate multi-account workflows for the Claude Desktop application on Windows.

---

## 1. System Architecture & Core Workflow

This repository provides the **interactive, human-in-the-loop coordination hub** for Claude Desktop. It is completely self-contained and operates with **zero background terminal daemons** and **zero CDP browser puppeteering**.

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
   - Once Claude Desktop launches, you can **close the launcher terminal immediately**. Claude Desktop and its stdio MCP tools remain fully alive and self-sufficient.
2. **Automatic Instance Teardown**:
   - In **Isolated Mode** (the default `[1]`), the launcher automatically detects, prompts, and cleanly shuts down all other running or concurrent Claude Desktop instances before configuring and starting the chosen profile.
3. **Manual Version Control**:
   - Automatic Git commit spam on profile launch is completely disabled.
   - All repository synchronization and version control is deliberate and manually managed via `.\sync.bat`.
4. **Frictionless Code Delivery (Zero Copy-Pasting)**:
   - Claude Desktop instances use `write_file_to_workspace` and `read_workspace_file` to write code, diffs, and scripts directly to disk inside the repository with a single tool call.
5. **Decoupled Headless Execution**:
   - Complex headless batch processing, API schedulers, and autonomous Copilot queue workers reside in the dedicated companion repository: [`Fleet-Orchestrator`](../Fleet-Orchestrator).

---

## 2. Repository Structure

```
Claude-Desktop/
├── launch.bat                     # Double-click launcher wrapper for Claude Desktop profiles
├── launch_user_n.ps1              # Core launcher: profile swap, instance teardown, detached GUI launch
├── sync.bat                       # Zero-friction git sync wrapper (PowerShell ExecutionPolicy bypass)
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

## 3. Quick Start

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
Invoke-Pester .\tests\launch_user_n.Tests.ps1 -Output Detailed

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
