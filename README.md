# Claude Desktop Multi-Profile Orchestration & FastMCP Ecosystem

PowerShell automation, stdio FastMCP servers, and decentralized filesystem state contracts to orchestrate multi-account workflows for the Claude Desktop application on Windows.

---

## 1. System Architecture & Operational Layers

The repository operates across three complementary architectural layers:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       LAYER 1: INTERACTIVE CLAUDE DESKTOP                   │
│   Account 1: Lead/Architect        Account 2: Builder/Coder       Account 6: QA Reviewer   │
│   (create_task / plan)             (workspace edits / tests)      (adversarial audit)      │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │ stdio JSON-RPC (team-mcp.json)
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│            FAST MCP COORDINATION SERVER (run_server.py: 34 Tools)           │
│   get_context_bundle | init_scratchpad | append_scratchpad | submit_review  │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │ Plain JSON State Contracts
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                 FILESYSTEM STATE CONTRACT (orchestrator-state/)              │
│   tasks/          checkpoints/      qa-reviews/      live-status/          │
│   (spec/status)   (deliverables)    (pass/fail)      (heartbeats)          │
│   ─────────────────────────────────────────────────────────────             │
│   scratchpads/shared_scratchpad.md (Multi-Account Shared Blackboard)        │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │ Background Queue Polling
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│             LAYER 2: BACKGROUND CODE EXECUTION (Copilot Queue Worker)       │
│   launch_copilot_worker.bat  ──>  CopilotCLIAdapter (27 ready accounts)     │
│   Executes non-interactively in isolated git worktrees, submits checkpoints │
└─────────────────────────────────────────────────────────────────────────────┘
                                       │
┌─────────────────────────────────────────────────────────────────────────────┐
│             LAYER 3: CLOUD COORDINATION BACKEND (v2 - Optional)             │
│   server/ (FastAPI + SQLite WAL) + Hosted Remote HTTP/SSE MCP Server        │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Layer 1: Interactive Multi-Profile Claude Desktop
- **Zero-CDP Stdio Protocol**: Puppeteering via Chrome DevTools Protocol (CDP ports 9222–9229) is retired in favor of native stdio FastMCP (`mcp-servers/orchestrator-mcp/run_server.py`).
- **Shared Scratchpad**: Multi-account coordination occurs in-session via [`orchestrator-state/scratchpads/shared_scratchpad.md`](orchestrator-state/scratchpads/shared_scratchpad.md).
- **Single-Call Bootstrap**: Profiles bootstrap context in one tool call via `get_context_bundle(account="<account>", scratchpad_id="shared")`.
- **Profile Prompts & Instructions**: Pre-calibrated Custom Instructions for Architect (`user1`), Builder (`user2`), and QA Reviewer (`user6`) are cataloged in [`worker-prompts/CLAUDE_DESKTOP_PROFILES.md`](worker-prompts/CLAUDE_DESKTOP_PROFILES.md).

### Layer 2: Background Code Execution (Copilot Queue Worker)
- One-click runner [`launch_copilot_worker.bat`](launch_copilot_worker.bat) polls `orchestrator-state/tasks/` for `kind: "code"` and `status: "pending"`.
- Claims tasks using round-robin account rotation across 27 worker profiles, provisions isolated git worktrees, executes non-interactively via Copilot CLI, and writes deliverable checkpoints.

### Layer 3: Cloud Coordination Backend (v2 - Optional)
- High-concurrency SQLite WAL coordination server located in [`server/`](server/) with REST APIs for batch SKU expansion and a Hosted Remote MCP server (`server/mcp_remote.py`).

---

## 2. Repository Structure

```Claude-Desktop/
├── launch_copilot_worker.bat      # One-click runner for Copilot queue worker
├── launch_copilot_fleet.bat       # Multi-account Copilot fleet runner
├── sync.bat                       # Zero-friction git sync wrapper (PowerShell ExecutionPolicy bypass)
├── sync.ps1                       # Git sync: pull --rebase --autostash, memory auto-sync, commit, push
├── sync-mcp.ps1                   # Syncs team-mcp.json into all Claude Desktop profile configs
├── profiles.json                  # Account name -> nickname/paths/role metadata map
├── team-mcp.json                  # Shared MCP config (orchestrator-mcp, notebooklm-mcp, md2pdf, super-nlm)
├── team-claude-config.json        # Sanitized team-wide Claude desktop config template
├── team-context.md                # Static identity scaffold, read via get_context_bundle
├── team-memory.md                 # Shared memory log, auto-appended by sync.ps1 + manual entries
├── AGENTS.md                      # Authoritative single source of truth for agent rules & workflows
├── GEMINI.md                      # Agent rules pointer referencing AGENTS.md
├── README.md                      # Ecosystem architecture and user guide
├── LICENSE
│
├── legacy/                        # Archived legacy CDP automation & multi-window scripts
│   ├── README.md                  # Documentation of retired CDP components & rationale
│   ├── launch_user_n.ps1          # Retired multi-profile CDP launcher
│   ├── launch.bat                 # Retired double-click launcher
│   ├── launch-gui.bat / .ps1      # Retired Tkinter fleet GUI launcher
│   ├── close.bat                  # Retired instance closer
│   ├── launch-fleet.ps1           # Retired virtual desktop launcher
│   ├── fleet_gui.py               # Retired Tkinter CDP window controller
│   └── VirtualDesktop.exe / .cs   # Retired virtual desktop P/Invoke CLI
│
├── orchestrator-state/            # Filesystem coordination state contract
│   ├── SCHEMA.md                  # File contract & invariant documentation
│   ├── tasks/                     # Task definitions (kind: code|text, status: pending|claimed|done|merged)
│   ├── checkpoints/               # Worker deliverables (commit_sha, branch_name, summary, result_text)
│   ├── qa-reviews/                # Adversarial QA audit results (verdict: pass|fail|revision_needed)
│   ├── live-status/               # Individual worker heartbeats (last-write-wins)
│   ├── scratchpads/               # Shared multi-account collaboration scratchpads
│   └── memory/                    # Shared immutable team-memory entries
│
├── mcp-servers/
│   ├── orchestrator-mcp/          # Hand-written FastMCP local coordination server (34 tools)
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
├── client/                        # Autonomous worker client daemon & adapters
│   ├── worker_daemon.py           # Polling daemon: registers worker, claims tasks, runs execution loop
│   └── adapters/                  # LLM provider adapters (Copilot, Ollama, Gemini, Groq)
│
├── server/                        # Cloud-native FastAPI coordination backend
│   ├── main.py                    # Application entrypoint & background supervisor lifecycle
│   ├── mcp_remote.py              # Hosted Streamable HTTP/SSE Remote MCP Server
│   └── database/schema.sql        # SQLite WAL DDL
│
├── sku-templates/                 # Production pipeline DAG definitions
├── dev-logs/                      # Development notes, handoff transcripts, and milestone logs
├── outputs/                       # Generated reports and deliverables (gitignored)
│
└── tests/
    ├── orchestrator_mcp_test.py   # Complete test suite for orchestrator-mcp (34 specs)
    ├── test_copilot_cli_adapter.py # Copilot CLI adapter tests
    ├── test_remote_mcp.py         # Hosted Remote MCP and memory route tests
    ├── test_cloud_scheduler.py    # Cloud scheduler and supervisor recovery tests
    ├── test_pipeline_engine.py    # SKU pipeline decomposition tests
    └── launch_user_n.Tests.ps1    # Pester specs for legacy launcher
```

---

## 3. Getting Started

### 1. Synchronizing Claude Desktop Profiles with MCP
To configure `team-mcp.json` into all local Claude Desktop user profiles:
```powershell
pwsh -File .\sync-mcp.ps1
```
Open Claude Desktop naturally. The `orchestrator-mcp` tools will appear in your tools menu.

### 2. Configuring Profile Custom Instructions
Open Claude Desktop → **Settings** → **Profile** / **Custom Instructions**. Copy-paste the corresponding prompt blocks from [`worker-prompts/CLAUDE_DESKTOP_PROFILES.md`](worker-prompts/CLAUDE_DESKTOP_PROFILES.md):
- **Box 1 & 2 for Architect** (`user1` `adevtmr`)
- **Box 1 & 2 for Builder/Coder** (`user2` `dev83`)
- **Box 1 & 2 for Adversarial QA** (`user6` `adt_ieee`)

### 3. Launching Background Copilot Workers
To process code tasks asynchronously in the background:
```bat
.\launch_copilot_worker.bat
```
The worker watches `orchestrator-state/tasks/`, claims pending tasks, executes changes in isolated worktrees, and submits deliverable checkpoints.

### 4. Running the Test Suite
Ensure the local Python environment has `pytest` and `mcp` installed:
```powershell
pytest tests/orchestrator_mcp_test.py -v
```

### 5. Synchronizing the Repository
All version control must run through `.\sync.bat` (or `.\sync.ps1`):
```powershell
.\sync.bat -m "feat(scope): concise conventional commit summary"
```
To pull latest changes safely:
```powershell
.\sync.bat -PullOnly
```
