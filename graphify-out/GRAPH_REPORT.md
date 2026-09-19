# Graph Report - Claude-Desktop  (2026-09-19)

## Corpus Check
- 363 files · ~292,779 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1325 nodes · 2461 edges · 120 communities (73 shown, 21 thin omitted)
- Extraction: 96% EXTRACTED · 4% INFERRED · 0% AMBIGUOUS · INFERRED: 98 edges (avg confidence: 0.92)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `6616aba0`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- IApplicationView
- orchestrator_mcp_test.py
- MD2PDFApp
- orchestrator-mcp/run_server.py
- IVirtualDesktop
- test_remote_mcp.py
- Memory Log
- routes_tasks.py
- .Main
- launch_user_n.ps1
- Desktop
- BaseWorkerAdapter
- routes_memory.py
- WinPilotBridge
- VirtualDesktop11-24H2.cs
- FleetControlApp
- cloud-orchestrator-mcp/run_server.py
- routes_workers.py
- routes_jobs.py
- Guid
- test_e2e_pipeline.py
- schemas.py
- IApplicationViewCollection
- harvest_completed_jobs
- super-nlm-mcp/run_server.py
- pipeline_engine.py
- SPARK Project
- Usage
- IVirtualDesktopPinnedApps
- main.py
- fleet_supervisor.py
- Cross-Linking Hub
- init_db
- Handoff Protocol
- convert_markdown_to_pdf
- Job & Pipeline Production Schema (v2)
- QuotaAwareScheduler
- Server Requirements
- orchestrator-state schema
- config.py
- sync-mcp.ps1
- cooldown-reminder.ps1
- orchestrator.md
- sync.ps1
- usage-watchdog.ps1
- asyncio
- _find_uvx
- Task Entity
- Worker Role: Formatter & Delivery Packaging
- Worker Role: Orchestrator / Dispatcher
- Worker Role: Quality Assurance (QA) & Fact-Checker
- Worker Role: Researcher / Attribute Extractor
- Worker Role: Copywriter / Drafting Specialist
- test_health.py
- ClaudeDesktopCDPAdapter
- AGENTS.md
- Cloudflared Service
- mcp
- 2026-08-22
- sync.ps1
- Archive.org Skill
- Assume Reader Intelligence Skill
- PowerShell Sandbox Setup Skill
- Repo Conventions Skill
- PowerShell CI Job
- MD2PDF MCP Requirements
- notebooklm-mcp-cli
- Orchestrator MCP Server
- 2026-09-15_ANALYSE-REPO_CONVERSATION.md
- setup_test_db
- test_task_acquisition.py
- ._eval_js
- sync_manifest
- Turn 4
- 24. What I would change first
- CopilotHeadlessAdapter
- 32. My P0 fixes
- save_chat.py
- ClaudeDesktopProxyAdapter
- GroqAdapter
- Turn 1
- Turn 2
- Execution Protocol
- What I'd change given your stated objective
- Bottom line
- 1. The biggest bug: your scheduler and workers disagree about who owns task acquisition
- 23. The biggest conceptual weakness
- 31. Then simplify the orchestration architecture to this
- Your "bad architecture" starts looking like useful experimentation
- 10. Your tests give a false sense of security here
- 4. The security model is weaker than I originally thought
- The most interesting experiment you could run
- MCPAuthMiddleware
- .execute_task

## God Nodes (most connected - your core abstractions)
1. `IApplicationView` - 64 edges
2. `Desktop` - 45 edges
3. `ClaudeDesktopCDPAdapter` - 42 edges
4. `Memory Log` - 40 edges
5. `get_db_conn()` - 32 edges
6. `MD2PDFApp` - 30 edges
7. `IVirtualDesktop` - 25 edges
8. `BaseWorkerAdapter` - 24 edges
9. `IVirtualDesktopManagerInternal` - 24 edges
10. `FleetControlApp` - 23 edges

## Surprising Connections (you probably didn't know these)
- `test_claude_proxy_delegation_to_cdp()` --uses--> `ClaudeDesktopProxyAdapter`  [INFERRED]
  tests/test_claude_cdp_adapter.py → client/adapters/claude_desktop_proxy.py
- `test_invariant_b_strict_separation_of_real_and_simulation()` --uses--> `ClaudeDesktopProxyAdapter`  [INFERRED]
  tests/test_invariants_wsr_002.py → client/adapters/claude_desktop_proxy.py
- `test_invariant_b_strict_separation_of_real_and_simulation()` --uses--> `GeminiFreeAdapter`  [INFERRED]
  tests/test_invariants_wsr_002.py → client/adapters/gemini_free_adapter.py
- `test_invariant_b_strict_separation_of_real_and_simulation()` --uses--> `GroqAdapter`  [INFERRED]
  tests/test_invariants_wsr_002.py → client/adapters/groq_adapter.py
- `test_cdp_adapter_custom_model_and_thinking_init()` --uses--> `ClaudeDesktopCDPAdapter`  [INFERRED]
  tests/test_claude_cdp_adapter.py → client/adapters/claude_desktop_cdp.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **BiasAperture Audit Framework** — biasaperture_project, biasaperture_schema, nlm_mcp [EXTRACTED 0.85]
- **SPARK Development Flow** — spark_project, spark_tracker, gateway_receiver_wire_format, nlm_mcp [EXTRACTED 0.90]
- **Conversion Persistence Check** — outputs_md2pdf_persist_check_md, outputs_md2pdf_persist_check_pdf, outputs_md2pdf_gui_persist_check_pdf [EXTRACTED 0.95]
- **Token Efficiency Protocol** — orchestrator_state_handoff_protocol, claude_skills_cross_linking_hub, notebooklm_mcp [EXTRACTED 0.95]
- **CI Test Suite** — github_workflows_ci_python, github_workflows_ci_powershell [EXTRACTED 1.00]
- **Worker Pipeline Flow** — worker_prompts_orchestrator, worker_prompts_researcher, worker_prompts_writer, worker_prompts_seo_optimizer, worker_prompts_qa_reviewer, worker_prompts_formatter [EXTRACTED 1.00]

## Communities (120 total, 21 thin omitted)

### Community 0 - "IApplicationView"
Cohesion: 0.05
Nodes (3): IntPtr, IApplicationView, Size

### Community 1 - "orchestrator_mcp_test.py"
Cohesion: 0.04
Nodes (18): _load_run_server(), fixture, Path, pytest specs for orchestrator-mcp's run_server.py. Unlike…, Import run_server.py fresh against a specific REPO_ROOT. run_server.py derives…, A throwaway git repo with orchestrator-mcp's run_server.py loaded against it,…, repo(), TestBlockedUnblock (+10 more)

### Community 2 - "MD2PDFApp"
Cohesion: 0.08
Nodes (12): Frame, Tk, BatchItem, check_deps(), Config, main(), markdown_to_html(), MD2PDFApp (+4 more)

### Community 3 - "orchestrator-mcp/run_server.py"
Cohesion: 0.23
Nodes (39): archive_memory(), _checkpoint_path(), claim_task(), create_job(), create_task(), decompose_task(), _ensure_dirs(), get_context_bundle() (+31 more)

### Community 4 - "IVirtualDesktop"
Cohesion: 0.08
Nodes (4): PreserveSig, DesktopManager, IVirtualDesktop, IVirtualDesktopManagerInternal

### Community 5 - "test_remote_mcp.py"
Cohesion: 0.22
Nodes (42): Row, get_db_conn(), Obtain a direct async sqlite database connection., acquire_task(), block_task(), claim_task(), create_task(), get_job() (+34 more)

### Community 6 - "Memory Log"
Cohesion: 0.05
Nodes (39): 2026-08-05, 2026-08-06, 2026-08-10, 2026-08-11, 2026-08-13, 2026-08-15, 2026-08-21, 2026-08-23 (+31 more)

### Community 7 - "routes_tasks.py"
Cohesion: 0.15
Nodes (29): Response, acquire_task(), block_task(), claim_task(), create_task(), get_checkpoint(), get_task(), list_tasks() (+21 more)

### Community 8 - ".Main"
Cohesion: 0.18
Nodes (4): EnumDelegate, StringBuilder, Program, UInt32

### Community 9 - "launch_user_n.ps1"
Cohesion: 0.10
Nodes (31): Add-NewProfile(), Close-AllClaudeInstances(), Ensure-FleetVirtualDesktop(), Expand-TeamMcpPlaceholders(), Export-ActiveFleetState(), Format-CardRow(), Format-VisibleRight(), Format-VisibleText() (+23 more)

### Community 10 - "Desktop"
Cohesion: 0.15
Nodes (7): DllImport, Desktop, Count, Current, IsVisible, Left, Right

### Community 11 - "BaseWorkerAdapter"
Cohesion: 0.10
Nodes (19): ABC, BaseWorkerAdapter, Returns True if the backend AI model / profile is online and usable., Abstract interface for worker execution endpoints., Copilot Headless Adapter: Pure asynchronous HTTP adapter for GitHub Copilot…, GeminiFreeAdapter, Any, Adapter for Google AI Studio Free Tier (Gemini 2.5 / 3.0). Provides free tokens… (+11 more)

### Community 12 - "routes_memory.py"
Cohesion: 0.19
Nodes (19): put, get_all_context(), get_context_by_key(), list_memory(), _now_iso(), push_memory(), Connection, get (+11 more)

### Community 13 - "WinPilotBridge"
Cohesion: 0.11
Nodes (21): Any, Path, WinPilot Bridge: High-level Python bridge connecting Claude-Desktop…, The Revolving Turnstile: Executes the 1-by-1 physical dispatch sequence under…, Query recent dispatch history for a worker or entire fleet., Async bridge to WinPilot CLI with an in-memory clipboard history buffer., Execute a winpilot CLI command asynchronously., Brings target window to foreground, uncloaking from virtual desktops. (+13 more)

### Community 14 - "VirtualDesktop11-24H2.cs"
Cohesion: 0.11
Nodes (14): VirtualDesktop, VDeskTool, APPLICATION_VIEW_CLOAK_TYPE, AVCT_DEFAULT, AVCT_NONE, AVCT_VIRTUAL_DESKTOP, APPLICATION_VIEW_COMPATIBILITY_POLICY, AVCP_HIGH_SCALE_FACTOR (+6 more)

### Community 15 - "FleetControlApp"
Cohesion: 0.06
Nodes (22): ClaudeDesktopUIAAdapter, Automates prompt delivery to Claude Desktop on Windows via UI Automation /…, Verify the window handle is alive and visible., Bring window to foreground safely handling Windows focus locks and virtual…, Paste text into current focus and send Enter keypress., Activate the window and dispatch prompt., Direct prompt injection without task headers., _attach_default_desktop() (+14 more)

### Community 16 - "cloud-orchestrator-mcp/run_server.py"
Cohesion: 0.35
Nodes (18): block_task(), claim_task(), get_job(), get_system_health(), get_task(), get_worker(), list_jobs(), list_tasks() (+10 more)

### Community 17 - "routes_workers.py"
Cohesion: 0.14
Nodes (21): FastAPI, HTTPAuthorizationCredentials, get_worker(), list_workers(), _now_iso(), Connection, get, post (+13 more)

### Community 18 - "routes_jobs.py"
Cohesion: 0.19
Nodes (18): create_job(), get_job(), get_job_metrics(), list_jobs(), _now_iso(), Connection, get, post (+10 more)

### Community 19 - "Guid"
Cohesion: 0.14
Nodes (4): Guid, MarshalAs, IServiceProvider10, IVirtualDesktopManager

### Community 20 - "test_e2e_pipeline.py"
Cohesion: 0.10
Nodes (17): Periodic self-healing supervisor loop: 1. Identifies workers with stale…, run_supervisor_cycle(), Verify that Claude primary is preferred when available, but overflows to…, Verify that repetitive format stages favor Copilot headless, while QA favors…, test_cross_provider_tier_prioritization_and_overflow(), test_stage_affinity_routing(), test_supervisor_dead_worker_recovery(), Test that when multiple workers race to claim the same task simultaneously,… (+9 more)

### Community 21 - "schemas.py"
Cohesion: 0.25
Nodes (14): CheckpointResponse, CheckpointSubmit, ContextUpsert, MemoryCreate, BaseModel, QAReviewResponse, QAReviewSubmit, TaskAcquireRequest (+6 more)

### Community 23 - "harvest_completed_jobs"
Cohesion: 0.38
Nodes (6): harvest_completed_jobs(), AsyncClient, Trigger a Windows desktop toast notification via PowerShell., Check for completed jobs and compile deliverables., run_harvester_loop(), show_windows_toast()

### Community 25 - "pipeline_engine.py"
Cohesion: 0.22
Nodes (8): _now_iso(), PipelineEngine, Connection, Decomposes intake jobs into discrete, pipeline-staged tasks and manages stage…, Checks whether all tasks for a job have reached terminal state (done/merged).…, Load SKU definition JSON from sku-templates directory., Takes a job and a list of parsed input items (e.g. from CSV/JSON). Creates…, When a task is verified (or passes QA), triggers generation of the next stage…

### Community 26 - "SPARK Project"
Cohesion: 0.18
Nodes (10): BiasAperture, BiasAperture Schema, EX751 Wireless Communications, gateway/receiver/wire_format.py, NotebookLM (NLM) MCP, Aaradhya Dev Tamrakar, SPARK Project, SPARK Tracker (+2 more)

### Community 27 - "Usage"
Cohesion: 0.15
Nodes (12): Benchmarking Efficiency, Claude Desktop Multi-Profile & Sync Utilities, Concurrent Mode (Multiple Windows, Multiple Monitors), Features, Files, Launching Claude Desktop Profiles, Repo Structure, Running Autonomous Worker Daemons (v2) (+4 more)

### Community 31 - "main.py"
Cohesion: 0.21
Nodes (15): middleware, log_request(), metrics_text(), record_request(), request_id(), health_check(), lifespan(), liveness_check() (+7 more)

### Community 32 - "fleet_supervisor.py"
Cohesion: 0.14
Nodes (24): create_adapter(), get_system_telemetry(), get_winpilot_bridge(), main(), Any, AsyncClient, Event, Worker loop that drives any BaseWorkerAdapter through the orchestrator task… (+16 more)

### Community 33 - "Cross-Linking Hub"
Cohesion: 0.22
Nodes (8): Cross-Linking Hub, Application rules, Coursework notebooks (IV/I, exam sequence order), Hub, Leaf nodes, Pending, Query Protocol (Token Savings), Unlinked notebooks

### Community 34 - "init_db"
Cohesion: 0.12
Nodes (17): init_db(), Initialize database tables and indexes from schema.sql with automatic migration…, asyncio, fixture, setup_test_db(), test_auth_allowed_in_dev_mode_when_no_key_configured(), test_auth_enforced_when_api_key_configured(), fixture (+9 more)

### Community 35 - "Handoff Protocol"
Cohesion: 0.22
Nodes (6): graphify, Anti-Patterns (Wastes Tokens), Checkpoint Summary Format (max 500 chars), Handoff Protocol, Memory Entry Format, Session Bootstrap

### Community 36 - "convert_markdown_to_pdf"
Cohesion: 0.33
Nodes (7): _check_deps(), convert_markdown_to_pdf(), Any, tool, _read_source_content(), _resolve_output_path(), _run_conversion()

### Community 37 - "Job & Pipeline Production Schema (v2)"
Cohesion: 0.22
Nodes (8): 1. Job Entity (`jobs` / `orchestrator-state/jobs/<job_id>.json`), 2. Extended Task Schema (`tasks`), 3. QA Review Schema (`qa_reviews`), 4. Worker Node Entity (`workers`), 5. Shared Memory & Team Context (`memory_entries`, `team_context`), Job & Pipeline Production Schema (v2), Memory Entry (`memory_entries`), Team Context (`team_context`)

### Community 38 - "QuotaAwareScheduler"
Cohesion: 0.20
Nodes (8): Any, Connection, QuotaAwareScheduler, Pull-with-Scheduler-Arbitration (INV-WSR-002 Invariant A). Atomically inspects…, Find pending tasks (or expired leases) and auto-assign to best available…, Check if worker capabilities satisfy a task stage., Find the optimal worker ID to claim a given pending task or expired lease., Evaluates pending tasks against registered workers using: Score(W) = w1 *…

### Community 39 - "Server Requirements"
Cohesion: 0.29
Nodes (8): Python CI Job, Server Requirements, aiosqlite, fastapi, mcp, pydantic, pytest, uvicorn

### Community 40 - "orchestrator-state schema"
Cohesion: 0.25
Nodes (8): Directory listing as the index, orchestrator-state/checkpoints/<task_id>.json, orchestrator-state/live-status/\<account\>.json, orchestrator-state/memory/\<account\>\_\_\<entry_id\>.json, orchestrator-state/memory/archive/, orchestrator-state schema, orchestrator-state/tasks/<task_id>.json, Token-Efficient Session Bootstrap

### Community 41 - "config.py"
Cohesion: 0.39
Nodes (6): BaseModel, Settings, validate_security_settings(), test_development_allows_empty_auth_key(), test_production_accepts_strong_auth_key(), test_production_rejects_missing_auth_key()

### Community 42 - "sync-mcp.ps1"
Cohesion: 0.36
Nodes (5): Format-AsciiBorderRow(), Merge-McpServers(), Sync-ConfigToDir(), Write-JsonConfigSafely(), Write-McpBanner()

### Community 43 - "cooldown-reminder.ps1"
Cohesion: 0.38
Nodes (3): Format-VisibleRight(), Get-VisibleTextWidth(), Write-CooldownBanner()

### Community 44 - "orchestrator.md"
Cohesion: 0.29
Nodes (4): NotebookLM MCP, Directives, Token Efficiency, Worker Role: SEO & AEO Optimization Specialist

### Community 45 - "sync.ps1"
Cohesion: 0.43
Nodes (4): Sync-MemoryToTeamMemory(), Write-Notice(), Write-Status(), Write-Success()

### Community 46 - "usage-watchdog.ps1"
Cohesion: 0.48
Nodes (5): Get-ClaudeTrayUsagePercent(), Invoke-AutoCheckpoint(), Invoke-WatchdogPoll(), Set-CheckpointFiredThisCycle(), Test-CheckpointAlreadyFiredThisCycle()

### Community 47 - "asyncio"
Cohesion: 0.12
Nodes (17): asyncio, Invariant D: Checkpoint submission and DAG next-stage creation commit…, Invariant D / Fix 5: Passing QA review preserves deliverable in checkpoints…, Invariant B: Unhandled API / network failure MUST emit typed error, NEVER…, Invariant D / Fix 6: Failure during stage advancement rolls back checkpoint and…, Security hardening (G-4): claim_token must be None on read-only endpoints,…, The Cross-Worker Session Continuity Money Test (INV-WSR-002 Invariants A, B, C,…, Invariant C: Worker telemetry produces non-null empirical system metrics… (+9 more)

### Community 48 - "_find_uvx"
Cohesion: 0.50
Nodes (4): _find_uvx(), main(), Find the uvx executable, checking common locations first., Find uvx and launch the NotebookLM MCP server.

### Community 49 - "Task Entity"
Cohesion: 0.50
Nodes (4): Job Entity, QA Review Entity, Task Entity, Worker Node Entity

### Community 50 - "Worker Role: Formatter & Delivery Packaging"
Cohesion: 0.50
Nodes (3): Directives, Token Efficiency, Worker Role: Formatter & Delivery Packaging

### Community 51 - "Worker Role: Orchestrator / Dispatcher"
Cohesion: 0.50
Nodes (4): Responsibilities, Rules, Token Efficiency, Worker Role: Orchestrator / Dispatcher

### Community 52 - "Worker Role: Quality Assurance (QA) & Fact-Checker"
Cohesion: 0.50
Nodes (3): Directives, Token Efficiency, Worker Role: Quality Assurance (QA) & Fact-Checker

### Community 53 - "Worker Role: Researcher / Attribute Extractor"
Cohesion: 0.50
Nodes (4): Research Protocol, Responsibilities, Strict Rules, Worker Role: Researcher / Attribute Extractor

### Community 54 - "Worker Role: Copywriter / Drafting Specialist"
Cohesion: 0.50
Nodes (3): Directives, Token Efficiency, Worker Role: Copywriter / Drafting Specialist

### Community 55 - "test_health.py"
Cohesion: 0.33
Nodes (6): asyncio, fixture, Path, setup_test_db(), test_health_endpoints_and_request_correlation(), test_metrics_endpoint_exposes_request_counters()

### Community 57 - "ClaudeDesktopCDPAdapter"
Cohesion: 0.20
Nodes (22): ClaudeDesktopCDPAdapter, Adapter automating a locally running Claude Desktop Electron app via Chrome…, Check if Claude Desktop Electron process is exposing CDP port and has an active…, patch, asyncio, Verify that when winpilot_bridge is present, batch_setup_and_inject is called., Verify that if WinPilot detects cooldown, execute_task returns RATE_LIMIT_429., test_cdp_adapter_custom_model_and_thinking_init() (+14 more)

### Community 87 - "2026-09-15_ANALYSE-REPO_CONVERSATION.md"
Cohesion: 0.03
Nodes (64): 10. `INSERT OR REPLACE` is dangerous in your pipeline engine, 11. The profile system has become a real subsystem, 11. Your pipeline isn't really a general DAG engine yet, 12. QA is not yet actually controlling workflow quality, 12. There is also a portability problem, 13. `profiles.json` should probably not be treated as source configuration, 13. The `qa_hold` job status isn't connected tightly enough to the workflow, 14. Metrics are currently more aspirational than operational (+56 more)

### Community 88 - "setup_test_db"
Cohesion: 0.67
Nodes (3): fixture, Path, setup_test_db()

### Community 89 - "test_task_acquisition.py"
Cohesion: 0.40
Nodes (5): asyncio, fixture, setup_test_db(), test_acquire_matches_capabilities_and_leases_atomically(), test_acquire_returns_204_when_no_tasks()

### Community 90 - "._eval_js"
Cohesion: 0.14
Nodes (13): Any, Send a JSON-RPC command over WebSocket and await result with timeout., Evaluate a JavaScript expression in the page and return the unwrapped value., Automate Claude Desktop via CDP: 1. Connect to page 2. Check for rate limit /…, Scan DOM for 5-hour usage limit and cooldown warnings., Click new chat or reset conversation., Dismiss non-essential popups (update notes, cookie/terms banners)., Ensure correct model (Sonnet 5 vs Haiku 4.5) and Effort/Thinking mode are… (+5 more)

### Community 97 - "sync_manifest"
Cohesion: 0.16
Nodes (19): create_drive_file(), find_drive_file_by_name(), get_oauth_credentials(), main(), obtain_access_token(), Path, Request, Exchanges refresh token for a fresh Google OAuth2 access token with retry. (+11 more)

### Community 98 - "Turn 4"
Cohesion: 0.18
Nodes (11): A transcript exporter, And there's a very compelling research question hiding here, Assistant, It also fits the zero-cost constraint extremely well, My revised conclusion, One thing I would specifically watch in your new implementation, The really interesting possibility, Turn 4 (+3 more)

### Community 99 - "24. What I would change first"
Cohesion: 0.20
Nodes (10): 24. What I would change first, P0 — Fix security, P0 — Protect identity, P1 — Make state authoritative, P1 — Remove workstation-specific paths, P1 — Replace count-based IDs, P1 — Split the 2,400-line PowerShell launcher, P2 — Add resilience tests (+2 more)

### Community 100 - "CopilotHeadlessAdapter"
Cohesion: 0.16
Nodes (14): CopilotHeadlessAdapter, Any, Executes task prompt via Copilot Chat completions endpoint. Captures and…, Automates GitHub Copilot via direct REST API without requiring VS Code.…, Dynamically resolve token (checks env var if not hardcoded)., Health check returns True if token is present and valid session token can be…, Exchanges GitHub token for internal Copilot session token. Caches token until…, asyncio (+6 more)

### Community 101 - "32. My P0 fixes"
Cohesion: 0.22
Nodes (9): 32. My P0 fixes, P0.1 — Pick worker-pull or coordinator-push, P0.2 — Apply authentication globally, P0.3 — Separate authentication from worker identity, P0.4 — Remove automatic worker creation, P0.5 — Require claim tokens for completion, P0.6 — Make QA a real state gate, P0.7 — Kill `INSERT OR REPLACE` for lifecycle entities (+1 more)

### Community 102 - "save_chat.py"
Cohesion: 0.36
Nodes (8): clean_text(), format_markdown(), main(), parse_chatgpt_share(), Normalize text and remove citation markers / artifacts., Determines the dedicated subfolder for chat histories. - If user explicitly…, resolve_target_directory(), slugify()

### Community 103 - "ClaudeDesktopProxyAdapter"
Cohesion: 0.25
Nodes (5): ClaudeDesktopProxyAdapter, Any, Stage-aware local processing engine producing structured deliverables., Adapter representing a local Windows Claude Desktop profile session. Interfaces…, Execute task using Anthropic Claude API, CDP bridge, or explicit simulation…

### Community 104 - "GroqAdapter"
Cohesion: 0.28
Nodes (5): GroqAdapter, Any, Adapter for Groq-hosted LLMs via the OpenAI-compatible chat completions API., test_groq_adapter_missing_key_returns_error(), test_groq_adapter_uses_env_model_override()

### Community 105 - "Turn 1"
Cohesion: 0.25
Nodes (8): Analyse repo, Assistant, Assistant, Assistant, Assistant, Overall assessment, Turn 1, User

### Community 106 - "Turn 2"
Cohesion: 0.29
Nodes (7): Assistant, Assistant, Assistant, Final verdict, My revised verdict, Turn 2, User

### Community 107 - "Execution Protocol"
Cohesion: 0.29
Nodes (6): 1. Save to Current Working Directory / Repo, 2. Save to a Specific Folder (e.g. `docs/chat_history` or custom path), 3. Save to Brainstorm Knowledge Base, 4. Custom Filename / Output Path, Chat Archiver Skill, Execution Protocol

### Community 108 - "What I'd change given your stated objective"
Cohesion: 0.33
Nodes (6): 1. Fix the worker assignment protocol, 2. Build quota-aware scheduling properly, 3. Build context management, 4. Build provider fallback, 5. Add evaluation, What I'd change given your stated objective

### Community 109 - "Bottom line"
Cohesion: 0.40
Nodes (5): Assistant, Bottom line, Reframing the project, Turn 3, User

### Community 110 - "1. The biggest bug: your scheduler and workers disagree about who owns task acquisition"
Cohesion: 0.50
Nodes (4): 1. The biggest bug: your scheduler and workers disagree about who owns task acquisition, Model A — worker-pull, Model B — coordinator-push, You need to choose one ownership model

### Community 111 - "23. The biggest conceptual weakness"
Cohesion: 0.50
Nodes (4): 23. The biggest conceptual weakness, Product A, Product B, Product C

### Community 112 - "31. Then simplify the orchestration architecture to this"
Cohesion: 0.67
Nodes (3): 31. Then simplify the orchestration architecture to this, The scheduler should assign work., The worker should receive assigned work.

### Community 113 - "Your "bad architecture" starts looking like useful experimentation"
Cohesion: 0.67
Nodes (3): Mode 1 — Git-coordinated AI, Mode 2 — centralized live coordinator, Your "bad architecture" starts looking like useful experimentation

## Knowledge Gaps
- **255 isolated node(s):** `VirtualDesktop`, `AVCT_NONE`, `AVCT_DEFAULT`, `AVCT_VIRTUAL_DESKTOP`, `AVCP_NONE` (+250 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 586 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **21 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `BaseWorkerAdapter` connect `BaseWorkerAdapter` to `fleet_supervisor.py`, `CopilotHeadlessAdapter`, `ClaudeDesktopProxyAdapter`, `GroqAdapter`, `FleetControlApp`, `.execute_task`, `ClaudeDesktopCDPAdapter`?**
  _High betweenness centrality (0.045) - this node is a cross-community bridge._
- **Why does `ClaudeDesktopCDPAdapter` connect `ClaudeDesktopCDPAdapter` to `fleet_supervisor.py`, `ClaudeDesktopProxyAdapter`, `BaseWorkerAdapter`, `FleetControlApp`, `._eval_js`?**
  _High betweenness centrality (0.038) - this node is a cross-community bridge._
- **Why does `ClaudeDesktopUIAAdapter` connect `FleetControlApp` to `._eval_js`, `BaseWorkerAdapter`?**
  _High betweenness centrality (0.032) - this node is a cross-community bridge._
- **Are the 15 inferred relationships involving `ClaudeDesktopCDPAdapter` (e.g. with `ClaudeDesktopProxyAdapter` and `test_cdp_adapter_custom_model_and_thinking_init()`) actually correct?**
  _`ClaudeDesktopCDPAdapter` has 15 INFERRED edges - model-reasoned connections that need verification._
- **What connects `VirtualDesktop`, `AVCT_NONE`, `AVCT_DEFAULT` to the rest of the system?**
  _255 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `IApplicationView` be split into smaller, more focused modules?**
  _Cohesion score 0.05319148936170213 - nodes in this community are weakly interconnected._
- **Should `orchestrator_mcp_test.py` be split into smaller, more focused modules?**
  _Cohesion score 0.0425531914893617 - nodes in this community are weakly interconnected._