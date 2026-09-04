# Graph Report - Claude-Desktop  (2026-09-04)

## Corpus Check
- 314 files · ~221,209 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 928 nodes · 1868 edges · 92 communities (54 shown, 20 thin omitted)
- Extraction: 96% EXTRACTED · 4% INFERRED · 0% AMBIGUOUS · INFERRED: 76 edges (avg confidence: 0.91)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `c935ff47`
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
- Connection
- .Main
- launch_user_n.ps1
- Desktop
- BaseWorkerAdapter
- routes_memory.py
- ClaudeDesktopCDPAdapter
- VirtualDesktop11-24H2.cs
- ._eval_js
- cloud-orchestrator-mcp/run_server.py
- routes_workers.py
- routes_jobs.py
- IntPtr
- main.py
- routes_tasks.py
- IApplicationViewCollection
- config.py
- init_db
- PipelineEngine
- SPARK Project
- Usage
- AsyncClient
- IVirtualDesktopPinnedApps
- GroqAdapter
- test_cloud_scheduler.py
- schema.sql
- Cross-Linking Hub
- ClaudeDesktopProxyAdapter
- Handoff Protocol
- convert_markdown_to_pdf
- Job & Pipeline Production Schema (v2)
- QuotaAwareScheduler
- Server Requirements
- orchestrator-state schema
- validate_security_settings
- sync-mcp.ps1
- cooldown-reminder.ps1
- orchestrator.md
- sync.ps1
- usage-watchdog.ps1
- GeminiFreeAdapter
- _find_uvx
- Task Entity
- Worker Role: Formatter & Delivery Packaging
- Worker Role: Orchestrator / Dispatcher
- Worker Role: Quality Assurance (QA) & Fact-Checker
- Worker Role: Researcher / Attribute Extractor
- Worker Role: Copywriter / Drafting Specialist
- .execute_task
- get_db
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
- .GetDesktop
- FastAPI
- APPLICATION_VIEW_COMPATIBILITY_POLICY
- Size

## God Nodes (most connected - your core abstractions)
1. `IApplicationView` - 64 edges
2. `Desktop` - 45 edges
3. `Memory Log` - 40 edges
4. `get_db_conn()` - 32 edges
5. `MD2PDFApp` - 30 edges
6. `ClaudeDesktopCDPAdapter` - 29 edges
7. `IVirtualDesktop` - 25 edges
8. `IVirtualDesktopManagerInternal` - 24 edges
9. `_row_to_dict()` - 22 edges
10. `Program` - 19 edges

## Surprising Connections (you probably didn't know these)
- `test_claude_proxy_delegation_to_cdp()` --uses--> `ClaudeDesktopProxyAdapter`  [INFERRED]
  tests/test_claude_cdp_adapter.py → client/adapters/claude_desktop_proxy.py
- `test_cdp_adapter_init()` --uses--> `ClaudeDesktopCDPAdapter`  [INFERRED]
  tests/test_claude_cdp_adapter.py → client/adapters/claude_desktop_cdp.py
- `test_cdp_cooldown_detection_returns_429()` --uses--> `ClaudeDesktopCDPAdapter`  [INFERRED]
  tests/test_claude_cdp_adapter.py → client/adapters/claude_desktop_cdp.py
- `test_cdp_eval_js_exception()` --uses--> `ClaudeDesktopCDPAdapter`  [INFERRED]
  tests/test_claude_cdp_adapter.py → client/adapters/claude_desktop_cdp.py
- `test_cdp_execute_task_flow_success()` --uses--> `ClaudeDesktopCDPAdapter`  [INFERRED]
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

## Communities (92 total, 20 thin omitted)

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
Cohesion: 0.10
Nodes (3): PreserveSig, IVirtualDesktop, IVirtualDesktopManagerInternal

### Community 5 - "test_remote_mcp.py"
Cohesion: 0.24
Nodes (38): Row, get_db_conn(), Obtain a direct async sqlite database connection., block_task(), claim_task(), create_task(), get_job(), get_job_metrics() (+30 more)

### Community 6 - "Memory Log"
Cohesion: 0.05
Nodes (39): 2026-08-05, 2026-08-06, 2026-08-10, 2026-08-11, 2026-08-13, 2026-08-15, 2026-08-21, 2026-08-23 (+31 more)

### Community 7 - "Connection"
Cohesion: 0.14
Nodes (24): block_task(), claim_task(), create_task(), get_checkpoint(), get_task(), list_tasks(), _now_iso(), Connection (+16 more)

### Community 9 - "launch_user_n.ps1"
Cohesion: 0.12
Nodes (26): Add-NewProfile(), Expand-TeamMcpPlaceholders(), Format-CardRow(), Format-VisibleRight(), Format-VisibleText(), Get-ConcurrentClaudeInstances(), Get-DesktopBatchAllocation(), Get-EnrichedProfileRows() (+18 more)

### Community 10 - "Desktop"
Cohesion: 0.16
Nodes (7): DllImport, Desktop, Count, Current, IsVisible, Left, Right

### Community 11 - "BaseWorkerAdapter"
Cohesion: 0.16
Nodes (11): ABC, BaseWorkerAdapter, Returns True if the backend AI model / profile is online and usable., Abstract interface for worker execution endpoints., OllamaLocalAdapter, Any, Adapter for local Ollama / LM Studio models (e.g. Qwen 2.5, Llama 3.3). $0…, get_adapter() (+3 more)

### Community 12 - "routes_memory.py"
Cohesion: 0.18
Nodes (21): put, get_all_context(), get_context_by_key(), list_memory(), _now_iso(), push_memory(), Connection, get (+13 more)

### Community 13 - "ClaudeDesktopCDPAdapter"
Cohesion: 0.24
Nodes (15): ClaudeDesktopCDPAdapter, Adapter automating a locally running Claude Desktop Electron app via Chrome…, Check if Claude Desktop Electron process is exposing CDP port and has an active…, patch, asyncio, test_cdp_adapter_init(), test_cdp_cooldown_detection_returns_429(), test_cdp_eval_js_exception() (+7 more)

### Community 14 - "VirtualDesktop11-24H2.cs"
Cohesion: 0.18
Nodes (8): VirtualDesktop, VDeskTool, APPLICATION_VIEW_CLOAK_TYPE, AVCT_DEFAULT, AVCT_NONE, AVCT_VIRTUAL_DESKTOP, Guids, Rect

### Community 15 - "._eval_js"
Cohesion: 0.20
Nodes (10): Any, Automate Claude Desktop via CDP: 1. Connect to page 2. Check for rate limit /…, Scan DOM for 5-hour usage limit and cooldown warnings., Click new chat or reset conversation., Inject prompt into ProseMirror / contenteditable and click send safely without…, Poll until generation stop button disappears and text settles., Find the WebSocket debugger URL for the active Claude Desktop UI page., Send a JSON-RPC command over WebSocket and await result with timeout. (+2 more)

### Community 16 - "cloud-orchestrator-mcp/run_server.py"
Cohesion: 0.37
Nodes (17): block_task(), claim_task(), get_job(), get_system_health(), get_task(), get_worker(), list_jobs(), list_tasks() (+9 more)

### Community 17 - "routes_workers.py"
Cohesion: 0.24
Nodes (14): get_worker(), list_workers(), _now_iso(), Connection, get, post, Register or update an AI worker node / profile., List all registered worker nodes. (+6 more)

### Community 18 - "routes_jobs.py"
Cohesion: 0.19
Nodes (18): create_job(), get_job(), get_job_metrics(), list_jobs(), _now_iso(), Connection, get, post (+10 more)

### Community 19 - "IntPtr"
Cohesion: 0.15
Nodes (5): Guid, IntPtr, StringBuilder, IVirtualDesktopManager, UInt32

### Community 20 - "main.py"
Cohesion: 0.26
Nodes (12): middleware, Request, log_request(), metrics_text(), record_request(), request_id(), health_check(), liveness_check() (+4 more)

### Community 21 - "routes_tasks.py"
Cohesion: 0.34
Nodes (13): CheckpointResponse, CheckpointSubmit, BaseModel, QAReviewResponse, QAReviewSubmit, TaskBlockRequest, TaskClaimRequest, TaskClaimResponse (+5 more)

### Community 24 - "init_db"
Cohesion: 0.15
Nodes (13): init_db(), Initialize database tables and indexes from schema.sql with automatic migration…, fixture, Path, setup_test_db(), fixture, Path, setup_test_db() (+5 more)

### Community 25 - "PipelineEngine"
Cohesion: 0.23
Nodes (8): _now_iso(), PipelineEngine, Connection, Checks whether all tasks for a job have reached terminal state (done/merged).…, Decomposes intake jobs into discrete, pipeline-staged tasks and manages stage…, Load SKU definition JSON from sku-templates directory., Takes a job and a list of parsed input items (e.g. from CSV/JSON). Creates…, When a task is verified (or passes QA), triggers generation of the next stage…

### Community 26 - "SPARK Project"
Cohesion: 0.18
Nodes (10): BiasAperture, BiasAperture Schema, EX751 Wireless Communications, gateway/receiver/wire_format.py, NotebookLM (NLM) MCP, Aaradhya Dev Tamrakar, SPARK Project, SPARK Tracker (+2 more)

### Community 27 - "Usage"
Cohesion: 0.15
Nodes (12): Benchmarking Efficiency, Claude Desktop Multi-Profile & Sync Utilities, Concurrent Mode (Multiple Windows, Multiple Monitors), Features, Files, Launching Claude Desktop Profiles, Repo Structure, Running Autonomous Worker Daemons (v2) (+4 more)

### Community 28 - "AsyncClient"
Cohesion: 0.22
Nodes (10): AsyncClient, Test that when multiple workers race to claim the same task simultaneously,…, Test that an active worker can extend its task lease before expiration., End-to-End Test: Intake a 3-item '100_product_descriptions' job through all 5…, test_concurrent_task_leasing_race_safety(), test_e2e_sku_pipeline_execution(), test_lease_renewal_heartbeat(), asyncio (+2 more)

### Community 30 - "GroqAdapter"
Cohesion: 0.27
Nodes (5): GroqAdapter, Any, Adapter for Groq-hosted LLMs via the OpenAI-compatible chat completions API., test_groq_adapter_missing_key_returns_error(), test_groq_adapter_uses_env_model_override()

### Community 31 - "test_cloud_scheduler.py"
Cohesion: 0.20
Nodes (8): Periodic self-healing supervisor loop: 1. Identifies workers with stale…, run_supervisor_cycle(), fixture, Path, setup_test_db(), test_supervisor_dead_worker_recovery(), Test that tasks with expired leases can be claimed by a new worker or…, test_expired_lease_reclamation_and_recovery()

### Community 32 - "schema.sql"
Cohesion: 0.47
Nodes (9): checkpoints, job_metrics, jobs, memory_entries, qa_reviews, task_attempts, tasks, team_context (+1 more)

### Community 33 - "Cross-Linking Hub"
Cohesion: 0.22
Nodes (8): Cross-Linking Hub, Application rules, Coursework notebooks (IV/I, exam sequence order), Hub, Leaf nodes, Pending, Query Protocol (Token Savings), Unlinked notebooks

### Community 34 - "ClaudeDesktopProxyAdapter"
Cohesion: 0.25
Nodes (5): ClaudeDesktopProxyAdapter, Any, Adapter representing a local Windows Claude Desktop profile session. Interfaces…, Execute task using Anthropic Claude API, CDP bridge, or structured prompt…, Stage-aware local processing engine producing structured deliverables.

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
Cohesion: 0.28
Nodes (5): Connection, QuotaAwareScheduler, Find pending tasks (or expired leases) and auto-assign to best available…, Find the optimal worker ID to claim a given pending task or expired lease., Evaluates pending tasks against registered workers using: Score(W) = w1 *…

### Community 39 - "Server Requirements"
Cohesion: 0.29
Nodes (8): Python CI Job, Server Requirements, aiosqlite, fastapi, mcp, pydantic, pytest, uvicorn

### Community 40 - "orchestrator-state schema"
Cohesion: 0.25
Nodes (8): Directory listing as the index, orchestrator-state/checkpoints/<task_id>.json, orchestrator-state/live-status/\<account\>.json, orchestrator-state/memory/\<account\>\_\_\<entry_id\>.json, orchestrator-state/memory/archive/, orchestrator-state schema, orchestrator-state/tasks/<task_id>.json, Token-Efficient Session Bootstrap

### Community 41 - "validate_security_settings"
Cohesion: 0.70
Nodes (4): validate_security_settings(), test_development_allows_empty_auth_key(), test_production_accepts_strong_auth_key(), test_production_rejects_missing_auth_key()

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

### Community 47 - "GeminiFreeAdapter"
Cohesion: 0.33
Nodes (3): GeminiFreeAdapter, Any, Adapter for Google AI Studio Free Tier (Gemini 2.5 / 3.0). Provides free tokens…

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

### Community 57 - "get_db"
Cohesion: 0.67
Nodes (3): get_db(), Connection, Dependency for obtaining an async sqlite database connection in FastAPI routes.

### Community 87 - ".GetDesktop"
Cohesion: 0.17
Nodes (3): MarshalAs, DesktopManager, IServiceProvider10

### Community 88 - "FastAPI"
Cohesion: 0.25
Nodes (7): FastAPI, HTTPAuthorizationCredentials, Verify that incoming request provides a valid API token via Bearer header or…, verify_api_key(), lifespan(), Background supervisor monitoring heartbeats, dead workers, and auto-scheduling…, run_supervisor_loop()

### Community 89 - "APPLICATION_VIEW_COMPATIBILITY_POLICY"
Cohesion: 0.25
Nodes (6): APPLICATION_VIEW_COMPATIBILITY_POLICY, AVCP_HIGH_SCALE_FACTOR, AVCP_NONE, AVCP_SMALL_SCREEN, AVCP_TABLET_SMALL_SCREEN, AVCP_VERY_SMALL_SCREEN

## Knowledge Gaps
- **132 isolated node(s):** `memory_entries`, `team_context`, `VirtualDesktop`, `AVCT_NONE`, `AVCT_DEFAULT` (+127 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 357 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **20 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `ClaudeDesktopProxyAdapter` connect `ClaudeDesktopProxyAdapter` to `BaseWorkerAdapter`, `AsyncClient`, `ClaudeDesktopCDPAdapter`, `config.py`?**
  _High betweenness centrality (0.025) - this node is a cross-community bridge._
- **Why does `ClaudeDesktopCDPAdapter` connect `ClaudeDesktopCDPAdapter` to `ClaudeDesktopProxyAdapter`, `BaseWorkerAdapter`, `._eval_js`?**
  _High betweenness centrality (0.020) - this node is a cross-community bridge._
- **Why does `IApplicationView` connect `IApplicationView` to `IVirtualDesktop`, `Desktop`, `VirtualDesktop11-24H2.cs`, `IntPtr`, `IApplicationViewCollection`, `APPLICATION_VIEW_COMPATIBILITY_POLICY`, `Size`, `IVirtualDesktopPinnedApps`?**
  _High betweenness centrality (0.019) - this node is a cross-community bridge._
- **What connects `memory_entries`, `team_context`, `VirtualDesktop` to the rest of the system?**
  _132 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `IApplicationView` be split into smaller, more focused modules?**
  _Cohesion score 0.04878048780487805 - nodes in this community are weakly interconnected._
- **Should `orchestrator_mcp_test.py` be split into smaller, more focused modules?**
  _Cohesion score 0.0425531914893617 - nodes in this community are weakly interconnected._
- **Should `MD2PDFApp` be split into smaller, more focused modules?**
  _Cohesion score 0.08139534883720931 - nodes in this community are weakly interconnected._