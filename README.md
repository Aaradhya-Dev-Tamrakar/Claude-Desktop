# Claude Desktop Multi-Profile & Sync Utilities

PowerShell scripts to manage multiple isolated user profiles for the Claude Desktop application on Windows and automate Git repository synchronization with smart commit messaging.

## Features

- **Multi-Profile Management**: Launch distinct Claude Desktop sessions via automated profile session swapping into native AppData paths.
- **Concurrent Multi-Monitor Sessions**: `-Mode Concurrent` (or `-Concurrent`) launches one or more profiles as independent, simultaneously-running windows via `--user-data-dir`, instead of swapping the single native install — drag each to its own monitor for side-by-side team use on one machine. `-Users <name1,name2,...>` launches a whole list non-interactively; per-account failures (missing exe, unknown profile) don't stop the rest of the list.
- **Native MSIX & OAuth Compatibility**: 100% compatible with Windows MSIX packages and browser OAuth deep links (`claude://`) without dual-window or authentication loop issues; concurrent windows don't need to be closed to sign in, only focused.
- **Dynamic Executable Resolution**: Automatically locates `Claude.exe` across MSIX/Windows Store App packages (`Get-AppxPackage *claude*`) and traditional local installation directories (`AppData\Local\Programs\Claude` and `WindowsApps`).
- **Cloud-Native Autonomous Worker Fleet (v2)**: Distributed task execution engine featuring a FastAPI coordinator backend, high-concurrency SQLite WAL persistence with atomic leasing, quota-aware scheduler, heartbeat supervisor, and autonomous client worker daemons supporting Claude Desktop proxy, Gemini free-tier, and local Ollama adapters.
- **Automated SKU Pipeline Decomposition**: Declarative SKU templates (`sku-templates/`) expanding high-level batch production jobs into dependency-ordered DAG task execution graphs with automated handoffs.
- **Automatic Session Backup & Persistence**: Automatically saves and syncs cookies, tokens, and local storage per profile on every switch.
- **Smart Git Synchronization**: Automatically stages, commits, pulls (with `--rebase` & `--autostash`), and pushes repository changes.
- **Auto-Sync on Launch & Reset**: `launch_user_n.ps1` and `reset_profiles.ps1` each auto-invoke `sync.ps1` (with a verbose, context-specific commit message) as their final step, skipped entirely under `-WhatIf`.
- **Intelligent Commit Messaging**: Dynamically generates conventional commit messages (`feat`, `refactor`, `chore`) derived from staged git diffs, hunk context headers, and line churn statistics (`+ins/-del`).
- **PowerShell 7 (`pwsh`) Compatible**: Fully compatible with PowerShell 7 (`pwsh`) and Windows PowerShell 5.1.

## Repo Structure

```Claude-Desktop/
├── launch_user_n.ps1              # Profile launcher (Isolated / Concurrent)
├── launch.bat                     # Double-click entry point for File Explorer
├── sync.ps1                       # Git sync: pull --rebase --autostash, memory auto-sync, commit, push
├── cooldown-reminder.ps1          # Post-login 5h cooldown toast, invoked by launch_user_n.ps1
├── usage-watchdog.ps1             # Tray UIA usage watchdog polling & auto-checkpointing on threshold
├── reset_profiles.ps1             # Wipes all profile state, resets profiles.json to {}
├── bypass-all-profiles.ps1        # Sets bypassPermissionsGateByAccount=true across all profile configs
├── profiles.json                  # Account name -> nickname/paths/last-login map
├── team-mcp.json                  # Shared MCP config, force-merged into every profile
├── team-claude-config.json        # Sanitized team-wide Claude desktop config template (mcpServers + preferences)
├── team-context.md                # Static identity scaffold, read via read_team_context
├── team-memory.md                 # Shared memory log, auto-appended by sync.ps1 + manual entries
├── gcal-credentials.json.example  # Google Calendar OAuth credential template
├── gcal-token.json.example        # Google Calendar token template
├── AGENTS.md                      # Repo conventions for agent contributors
├── README.md
├── LICENSE
├── .gitattributes
├── .gitignore
│
├── client/                        # Autonomous worker client daemon & adapters
│   ├── worker_daemon.py           # Polling daemon: registers worker, claims tasks, runs execution loop
│   └── adapters/                  # LLM provider adapters
│       ├── base_adapter.py        # Abstract adapter interface
│       ├── claude_desktop_proxy.py # Claude Desktop UI/MCP bridge adapter
│       ├── groq_adapter.py       # Groq-hosted LLM execution adapter
│       └── ollama_local_adapter.py # Local Ollama LLM provider adapter
│
├── server/                        # Cloud-native FastAPI coordination backend
│   ├── main.py                    # Application entrypoint & background supervisor lifecycle
│   ├── mcp_remote.py              # Hosted Streamable HTTP/SSE Remote MCP Server (23 tools)
│   ├── Dockerfile                 # Container packaging definition
│   ├── docker-compose.yml         # Compose stack (FastAPI orchestrator + cloudflared tunnel)
│   ├── requirements.txt           # Backend dependencies (fastapi, aiosqlite, uvicorn, pydantic, mcp, httpx)
│   ├── api/                       # REST API routes
│   │   ├── routes_jobs.py         # Batch job submission & template expansion
│   │   ├── routes_tasks.py        # Task lifecycle, atomic leasing, checkpoints & QA reviews
│   │   ├── routes_workers.py      # Worker registration, heartbeat & active status
│   │   └── routes_memory.py       # Shared database memory & durable team context
│   ├── core/                      # Core backend logic
│   │   ├── auth.py                # Bearer token / API key security dependency
│   │   ├── config.py              # Settings & database connection strings
│   │   ├── database.py            # SQLite WAL connection & migration manager
│   │   ├── pipeline_engine.py     # SKU template decomposition into DAG tasks & stage advancement
│   │   ├── scheduler.py           # Quota-aware task-to-worker capability matching & atomic leasing
│   │   └── supervisor.py          # Dead worker watchdog & stranded task / expired lease recovery
│   ├── database/
│   │   └── schema.sql             # SQLite WAL DDL for jobs, tasks, workers, checkpoints, QA reviews, memory, context
│   └── models/
│       └── schemas.py             # Pydantic request/response models

│
├── sku-templates/                 # Production pipeline definitions
│   ├── 100_product_descriptions.json # E-commerce catalog batch template
│   ├── 30_day_social_package.json # Multi-stage social content generation
│   ├── document_processing_50.json # Batch document extraction and synthesis
│   └── seo_content_batch.json     # Full-funnel SEO article research & generation
│
├── worker-prompts/                # Specialized role system prompts
│   ├── orchestrator.md            # Plan decomposition & task routing prompt
│   ├── researcher.md              # Research & context gathering prompt
│   ├── writer.md                  # Content generation prompt
│   ├── formatter.md               # Formatting & schema compliance prompt
│   ├── seo-optimizer.md           # SEO optimization & metadata prompt
│   └── qa-reviewer.md             # Quality assurance and verification prompt
│
├── Claude Skills + MCP/
│   ├── Cross-Linking Hub.md       # Map of GitHub repos to NotebookLM notebooks and central hub
│   ├── archive-org.skill          # Skill: Archive.org search and snapshot retrieval
│   ├── assume-reader-intelligence.skill # Skill: Terse, high-signal communication style
│   ├── pwsh-sandbox-setup.skill   # Skill: PowerShell sandbox execution conventions
│   ├── repo-conventions.skill     # Skill: Repository structure and sync conventions
│   └── notebooklm-mcp-0.9.5.mcpb  # Packaged NotebookLM MCP extension bundle
│
├── mcp-servers/
│   ├── notebooklm-mcp/
│   │   └── run_server.py          # uvx-shim launcher for the published NotebookLM CLI
│   └── orchestrator-mcp/
│       └── run_server.py          # Hand-written MCP server, 14 tools, requires `pip install mcp`
│
├── orchestrator-state/
│   ├── SCHEMA.md                  # File contract for tasks/live-status/checkpoints/memory
│   ├── tasks/.gitkeep
│   ├── live-status/.gitkeep
│   ├── checkpoints/.gitkeep
│   └── memory/.gitkeep
│
└── tests/
    ├── launch_user_n.Tests.ps1    # Pester specs (path guard, profile table, MCP merge, placeholder expansion)
    ├── orchestrator_mcp_test.py   # pytest specs for orchestrator-mcp coordination server
    ├── test_cloud_scheduler.py    # pytest specs for cloud scheduler capability matching & supervisor recovery
    └── test_pipeline_engine.py    # pytest specs for SKU pipeline decomposition & task waterfall
```

## Files

- **`launch_user_n.ps1`**: Profile launcher script. Two modes: **Isolated** (default) resolves the executable path and swaps a single profile's session data into the native AppData install; **Concurrent** (`-Mode Concurrent` / `-Concurrent`, optionally with `-Users <name1,name2,...>`) launches one or more profiles as independent windows via `--user-data-dir`, with no swap/mirror and no shared `claude://` handler changes. Auto-detects and launches the background FastAPI Orchestrator server (`Ensure-LocalOrchestratorServer`) on `http://127.0.0.1:8000` if not already running. Unless `-NoTeamSync`, force-merges `team-mcp.json` into each launching profile's `claude_desktop_config.json`. Supports `-NoCooldownAlarm` to skip scheduling the 5-hour reminder toast, and `-WhatIf` for dry-run simulation.
- **`launch.bat`**: Double-click launcher for Windows File Explorer.
- **`profiles.json`**: Configuration file mapping account profile names to display nicknames, user data storage paths, and last logged-in timestamps.
- **`server/`**: Cloud-native FastAPI orchestration backend. Manages persistent state in SQLite WAL mode (`schema.sql`), provides REST APIs for batch jobs, task lifecycles, and shared memory/context (`routes_jobs.py`, `routes_tasks.py`, `routes_workers.py`, `routes_memory.py`), expands SKU templates into DAG workflows (`pipeline_engine.py`), matches worker capabilities under rate/cooldown constraints (`scheduler.py`), monitors worker liveness (`supervisor.py`), and serves the **Hosted Streamable HTTP/SSE Remote MCP Server** (`mcp_remote.py`) at `/mcp`.
- **`client/`**: Distributed autonomous worker daemon (`worker_daemon.py`) connecting to the server API, claiming tasks matching its configured provider capabilities, and executing work via pluggable LLM adapters (`claude_desktop_proxy.py`, `groq_adapter.py`, `ollama_local_adapter.py`, `gemini_free_adapter.py`).
- **`sku-templates/`**: Pre-configured JSON workflow definitions outlining multi-stage agent pipelines (research, draft, optimize, QA, format) for high-throughput batch content creation.
- **`worker-prompts/`**: Role-specific system prompts defining operational guidelines and constraints for autonomous worker roles (`orchestrator`, `researcher`, `writer`, `formatter`, `seo-optimizer`, `qa-reviewer`).
- **`team-mcp.json`**: Shared MCP server config, force-merged into every profile's `claude_desktop_config.json` on launch (shared entries win on name collision; a profile's own extra servers are never removed). Wires in `notebooklm-mcp`, `orchestrator-mcp`, and `cloud-orchestrator-mcp`. Use the literal token `{{REPO_ROOT}}` anywhere a `command`/`args`/`env` value needs to reference a path inside the repo; `Expand-TeamMcpPlaceholders` resolves it to each machine's actual clone path at sync time.
- **`team-claude-config.json`**: Sanitized baseline desktop configuration template declaring shared MCP servers and global preferences (`coworkBrowserToolsEnabled`, `coworkWebSearchEnabled`, `coworkPreferredBrowser`), omitting account-specific authentication tokens.
- **`Claude Skills + MCP/`**: Directory housing custom Claude skill definitions (`.skill`), extension bundles (`.mcpb`), and `Cross-Linking Hub.md` (the authoritative mapping of leaf GitHub repositories and NotebookLM notebooks to the central Engineer's Personal Notebook hub).
- **`mcp-servers/notebooklm-mcp/run_server.py`**: `uvx` launcher for the NotebookLM MCP server, referenced by `team-mcp.json`. Falls back through common per-platform `uvx` install locations when it's missing from `PATH`. Auth is shared across all profiles via `%USERPROFILE%\.notebooklm-mcp-cli\`.
- **`mcp-servers/orchestrator-mcp/run_server.py`**: Hand-written MCP server coordinating orchestrator/divider/executor roles across profiles via local files in `orchestrator-state/`. Exposes 19 tools across task lifecycles, checkpoints, live status, shared memory, and job metrics.
- **`server/mcp_remote.py`**: High-concurrency Hosted Remote MCP Server with **23 unified tools** mounted directly at `/mcp` (SSE / Streamable HTTP), integrating SQLite WAL state, atomic leasing, automated pipeline handoffs, shared memory search, and durable team context.
- **`team-context.md`**: Static identity/context scaffold. Edit it directly with standing project context and durable preferences — callable directly in chat via orchestrator-mcp's `read_team_context` tool.
- **`team-memory.md`**: Shared team memory log distributed across profiles via `sync.ps1`. New orchestrator memory entries (`orchestrator-state/memory/*.json`) are automatically appended under date headers by `sync.ps1`.
- **`sync.ps1`**: Automated Git repository synchronization tool. Performs `git pull --rebase --autostash`, automatically syncs new `orchestrator-state/memory/` entries into `team-memory.md`, scans staged changes for potential credentials/secrets, generates conventional commit messages with churn stats, and pushes to origin. Supports `-Message` (`-m`) and `-PullOnly`.
- **`cooldown-reminder.ps1`**: Auto-invoked by `launch_user_n.ps1` after every non-`-WhatIf` login. Tracks each profile's `first_login_time` under a cross-process named mutex, anchors a 5-hour cooldown to it, and registers a local Windows toast alarm via BurntToast.
- **`usage-watchdog.ps1`**: Monitors live Claude Desktop usage by inspecting the system tray flyout ("Usage: NN%") via Windows UI Automation (`System.Windows.Automation`).
- **`reset_profiles.ps1`**: Wipes all profile storage, logs, session state, and the `claude://` registry override, then resets `profiles.json` to `{}`.
- **`bypass-all-profiles.ps1`**: Sets `preferences.bypassPermissionsGateByAccount` to `true` for every account UUID found across all profile configs.
- **`tests/launch_user_n.Tests.ps1`**: Pester specs for `launch_user_n.ps1`'s pure/mockable logic (path guard, profile table, MCP merge, placeholder expansion, TestHook contracts). Run via `pwsh -NoProfile -Command "Invoke-Pester -Path .\tests\launch_user_n.Tests.ps1"`.
- **`tests/orchestrator_mcp_test.py`**: pytest specs for local file-based `orchestrator-mcp/run_server.py`.
- **`tests/test_remote_mcp.py`**: pytest specs for the hosted remote MCP server (`server/mcp_remote.py`) and memory REST endpoints (`server/api/routes_memory.py`).
- **`tests/test_cloud_scheduler.py`**: pytest specs for server quota scheduler, capability-based task matching, cooldown window enforcement, and supervisor worker recovery.
- **`tests/test_pipeline_engine.py`**: pytest specs for SKU template decomposition, DAG dependency validation, and multi-stage task waterfall propagation.

## Usage

### Launching Claude Desktop Profiles

Double-click **`launch.bat`** in Windows File Explorer, or run via PowerShell:

```powershell
pwsh -File .\launch_user_n.ps1 -Account user1
pwsh -File .\launch_user_n.ps1 -Account user2
```

With no arguments, the script prompts once for a mode (Isolated or Concurrent), then walks the normal profile picker.

To launch a profile while suppressing the 5-hour cooldown toast alarm:

```powershell
pwsh -File .\launch_user_n.ps1 -Account user1 -NoCooldownAlarm
```

### Concurrent Mode (Multiple Windows, Multiple Monitors)

Launch two or more profiles side by side, each its own independent window — each keeps its own `--user-data-dir`, so nothing is swapped or mirrored:

```powershell
pwsh -File .\launch_user_n.ps1 -Mode Concurrent -Users user1,user2
```

Or one at a time:

```powershell
pwsh -File .\launch_user_n.ps1 -Concurrent -Account user1
pwsh -File .\launch_user_n.ps1 -Concurrent -Account user2
```

`claude://` sign-in is a single OS-wide handler shared by every window, routing to whichever instance last had focus — profiles don't need to be closed to run concurrently, but a profile that still needs sign-in should be given focus first (or run alone) so the callback routes to it, not to whichever other window is topmost. A profile that fails to launch (missing exe, unknown name) doesn't block the rest of the `-Users` list.

Preview what a profile switch would do without touching any files, the registry, or running processes:

```powershell
pwsh -File .\launch_user_n.ps1 -Account user1 -WhatIf
```

Every non-`-WhatIf` launch auto-runs `sync.ps1` as its last step (pull, auto-memory sync, commit, push), with a commit message describing the profile switch. `reset_profiles.ps1` does the same after clearing all profiles. `-WhatIf` skips this entirely — no git operations occur during a dry run.

### Running the Cloud Orchestration Backend (v2)

Start the cloud FastAPI server and PostgreSQL database stack:

```bash
cd server
docker compose up -d
```

Or start the backend locally:

```bash
uvicorn server.main:app --host 0.0.0.0 --port 8000 --reload
```

Submit a batch job using an SKU pipeline template:

```bash
curl -X POST http://localhost:8000/api/jobs \
  -H "Content-Type: application/json" \
  -d '{"template_name": "seo_content_batch", "parameters": {"topic": "Edge AI Architecture", "keywords": ["edge computing", "ai pipeline"]}}'
```

### Running Autonomous Worker Daemons (v2)

Launch a worker daemon configured with local or cloud LLM adapters:

```bash
# Start an Ollama local model worker
python client/worker_daemon.py --worker-id worker-ollama-1 --provider ollama --model qwen2.5-coder:7b --capabilities code,drafting

# Start a Gemini API worker
python client/worker_daemon.py --worker-id worker-gemini-1 --provider gemini --model gemini-2.5-flash --capabilities research,seo,qa

# Start a Groq worker (set GROQ_API_KEY first)
export GROQ_API_KEY="your_api_key"
export GROQ_MODEL="llama-3.1-8b-instant"
python client/worker_daemon.py --worker-id worker-groq-1 --provider groq

# Start a Claude Desktop proxy worker
python client/worker_daemon.py --worker-id worker-claude-1 --provider claude-desktop --account user1 --capabilities reasoning,synthesis
```

Common Groq model choices include:

- `llama-3.1-8b-instant` (default for the repo)
- `llama-3.3-70b-versatile` (quality fallback)
- `llama-3.1-70b-versatile`
- `mixtral-8x7b-32768`
- `gemma2-9b-it`
- `deepseek-r1-distill-llama-70b`

Set the exact one you want via `GROQ_MODEL` in your environment or by passing a model override in code if you instantiate `GroqAdapter` directly.

### Running Usage Watchdog

Monitor Claude Desktop tray usage and auto-publish memory checkpoints on threshold breach:

```powershell
# Continuous monitoring (polls every 120s, alerts at 80% usage)
pwsh -File .\usage-watchdog.ps1 -Account user1

# Custom threshold and polling interval
pwsh -File .\usage-watchdog.ps1 -Account user1 -Threshold 85 -IntervalSeconds 60

# Single poll (dry-run without publishing state)
pwsh -File .\usage-watchdog.ps1 -Account user1 -Once -WhatIf
```

### Syncing Git Repository

Run full sync (pull rebase, auto-memory append to `team-memory.md`, auto-commit changes, and push):

```powershell
pwsh -File .\sync.ps1
```

Supply a custom commit message:

```powershell
pwsh -File .\sync.ps1 -Message "docs: update readme with pwsh usage and appx resolution details"
```

Perform pull-only:

```powershell
pwsh -File .\sync.ps1 -PullOnly
```
