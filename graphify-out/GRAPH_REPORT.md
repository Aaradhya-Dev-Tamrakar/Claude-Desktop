# Graph Report - Claude-Desktop  (2026-09-02)

## Corpus Check
- 262 files · ~183,025 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 842 nodes · 1718 edges · 71 communities (44 shown, 19 thin omitted)
- Extraction: 96% EXTRACTED · 4% INFERRED · 0% AMBIGUOUS · INFERRED: 64 edges (avg confidence: 0.92)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `61b0fa0b`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- Connection
- main.py
- orchestrator_mcp_test.py
- Memory Log
- IApplicationView
- orchestrator-mcp/run_server.py
- test_remote_mcp.py
- IVirtualDesktop
- IntPtr
- launch_user_n.ps1
- Desktop
- BaseWorkerAdapter
- routes_memory.py
- ClaudeDesktopCDPAdapter
- ._eval_js
- cloud-orchestrator-mcp/run_server.py
- .GetDesktop
- .Main
- IApplicationViewCollection
- Usage
- VirtualDesktop11-24H2.cs
- schema.sql
- IVirtualDesktopPinnedApps
- Cross-Linking Hub
- MD2PDFApp
- ClaudeDesktopProxyAdapter
- GroqAdapter
- Handoff Protocol
- Job & Pipeline Production Schema (v2)
- QuotaAwareScheduler
- MD2PDFApp
- orchestrator-state schema
- APPLICATION_VIEW_COMPATIBILITY_POLICY
- convert_markdown_to_pdf
- orchestrator.md
- OllamaLocalAdapter
- usage-watchdog.ps1
- _find_uvx
- sync-mcp.ps1
- Size
- team-context.md
- Task Entity
- Worker Role: Formatter & Delivery Packaging
- Worker Role: Orchestrator / Dispatcher
- Worker Role: Quality Assurance (QA) & Fact-Checker
- Worker Role: Researcher / Attribute Extractor
- Worker Role: Copywriter / Drafting Specialist
- .execute_task
- mcp
- AGENTS.md
- Cloudflared Service
- sync.ps1
- Archive.org Skill
- Assume Reader Intelligence Skill
- PowerShell Sandbox Setup Skill
- Repo Conventions Skill
- MD2PDF MCP Requirements
- notebooklm-mcp-cli
- routes_jobs.py
- routes_tasks.py
- routes_workers.py
- get_db
- 2026-08-22

## God Nodes (most connected - your core abstractions)
1. `IApplicationView` - 64 edges
2. `Memory Log` - 55 edges
3. `Desktop` - 45 edges
4. `get_db_conn()` - 31 edges
5. `ClaudeDesktopCDPAdapter` - 29 edges
6. `IVirtualDesktop` - 25 edges
7. `IVirtualDesktopManagerInternal` - 24 edges
8. `_row_to_dict()` - 22 edges
9. `Program` - 19 edges
10. `BaseWorkerAdapter` - 18 edges

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
- **Token Efficiency Protocol** — orchestrator_state_handoff_protocol, claude_skills_cross_linking_hub, notebooklm_mcp [EXTRACTED 0.95]
- **Worker Pipeline Flow** — worker_prompts_orchestrator, worker_prompts_researcher, worker_prompts_writer, worker_prompts_seo_optimizer, worker_prompts_qa_reviewer, worker_prompts_formatter [EXTRACTED 1.00]

## Communities (71 total, 19 thin omitted)

### Community 0 - "Connection"
Cohesion: 0.14
Nodes (24): block_task(), claim_task(), create_task(), get_checkpoint(), get_task(), list_tasks(), _now_iso(), Connection (+16 more)

### Community 1 - "main.py"
Cohesion: 0.05
Nodes (43): FastAPI, HTTPAuthorizationCredentials, Verify that incoming request provides a valid API token via Bearer header or…, verify_api_key(), BaseModel, Settings, init_db(), Initialize database tables and indexes from schema.sql with automatic migration… (+35 more)

### Community 2 - "orchestrator_mcp_test.py"
Cohesion: 0.04
Nodes (18): _load_run_server(), fixture, Path, pytest specs for orchestrator-mcp's run_server.py. Unlike…, Import run_server.py fresh against a specific REPO_ROOT. run_server.py derives…, A throwaway git repo with orchestrator-mcp's run_server.py loaded against it,…, repo(), TestBlockedUnblock (+10 more)

### Community 3 - "Memory Log"
Cohesion: 0.04
Nodes (54): 2026-08-05, 2026-08-06, 2026-08-10, 2026-08-10, 2026-08-11, 2026-08-11, 2026-08-11, 2026-08-11 (+46 more)

### Community 5 - "orchestrator-mcp/run_server.py"
Cohesion: 0.23
Nodes (39): archive_memory(), _checkpoint_path(), claim_task(), create_job(), create_task(), decompose_task(), _ensure_dirs(), get_context_bundle() (+31 more)

### Community 6 - "test_remote_mcp.py"
Cohesion: 0.26
Nodes (36): Row, get_db_conn(), Obtain a direct async sqlite database connection., block_task(), claim_task(), create_task(), get_job(), get_job_metrics() (+28 more)

### Community 7 - "IVirtualDesktop"
Cohesion: 0.10
Nodes (3): PreserveSig, IVirtualDesktop, IVirtualDesktopManagerInternal

### Community 8 - "IntPtr"
Cohesion: 0.15
Nodes (5): Guid, IntPtr, StringBuilder, IVirtualDesktopManager, UInt32

### Community 9 - "launch_user_n.ps1"
Cohesion: 0.10
Nodes (20): Add-NewProfile(), Expand-TeamMcpPlaceholders(), Format-CardRow(), Get-DesktopBatchAllocation(), Get-EnrichedProfileRows(), Get-ValidatedProfilePath(), Get-WindowGridLayout(), Initialize-VirtualDesktopTool() (+12 more)

### Community 10 - "Desktop"
Cohesion: 0.15
Nodes (7): DllImport, Desktop, Count, Current, IsVisible, Left, Right

### Community 11 - "BaseWorkerAdapter"
Cohesion: 0.18
Nodes (9): ABC, BaseWorkerAdapter, Returns True if the backend AI model / profile is online and usable., Abstract interface for worker execution endpoints., GeminiFreeAdapter, Any, Adapter for Google AI Studio Free Tier (Gemini 2.5 / 3.0). Provides free tokens…, get_adapter() (+1 more)

### Community 12 - "routes_memory.py"
Cohesion: 0.18
Nodes (21): put, get_all_context(), get_context_by_key(), list_memory(), _now_iso(), push_memory(), Connection, get (+13 more)

### Community 13 - "ClaudeDesktopCDPAdapter"
Cohesion: 0.24
Nodes (15): ClaudeDesktopCDPAdapter, Adapter automating a locally running Claude Desktop Electron app via Chrome…, Check if Claude Desktop Electron process is exposing CDP port and has an active…, patch, asyncio, test_cdp_adapter_init(), test_cdp_cooldown_detection_returns_429(), test_cdp_eval_js_exception() (+7 more)

### Community 14 - "._eval_js"
Cohesion: 0.20
Nodes (10): Any, Automate Claude Desktop via CDP: 1. Connect to page 2. Check for rate limit /…, Scan DOM for 5-hour usage limit and cooldown warnings., Click new chat or reset conversation., Inject prompt into ProseMirror / contenteditable and click send safely without…, Poll until generation stop button disappears and text settles., Find the WebSocket debugger URL for the active Claude Desktop UI page., Send a JSON-RPC command over WebSocket and await result with timeout. (+2 more)

### Community 15 - "cloud-orchestrator-mcp/run_server.py"
Cohesion: 0.37
Nodes (17): block_task(), claim_task(), get_job(), get_system_health(), get_task(), get_worker(), list_jobs(), list_tasks() (+9 more)

### Community 16 - ".GetDesktop"
Cohesion: 0.19
Nodes (3): MarshalAs, DesktopManager, IServiceProvider10

### Community 19 - "Usage"
Cohesion: 0.17
Nodes (11): Claude Desktop Multi-Profile & Sync Utilities, Concurrent Mode (Multiple Windows, Multiple Monitors), Features, Files, Launching Claude Desktop Profiles, Repo Structure, Running Autonomous Worker Daemons (v2), Running the Cloud Orchestration Backend (v2) (+3 more)

### Community 20 - "VirtualDesktop11-24H2.cs"
Cohesion: 0.18
Nodes (8): VirtualDesktop, VDeskTool, APPLICATION_VIEW_CLOAK_TYPE, AVCT_DEFAULT, AVCT_NONE, AVCT_VIRTUAL_DESKTOP, Guids, Rect

### Community 21 - "schema.sql"
Cohesion: 0.47
Nodes (9): checkpoints, job_metrics, jobs, memory_entries, qa_reviews, task_attempts, tasks, team_context (+1 more)

### Community 23 - "Cross-Linking Hub"
Cohesion: 0.22
Nodes (8): Cross-Linking Hub, Application rules, Coursework notebooks (IV/I, exam sequence order), Hub, Leaf nodes, Pending, Query Protocol (Token Savings), Unlinked notebooks

### Community 25 - "ClaudeDesktopProxyAdapter"
Cohesion: 0.25
Nodes (5): ClaudeDesktopProxyAdapter, Any, Adapter representing a local Windows Claude Desktop profile session. Interfaces…, Execute task using Anthropic Claude API, CDP bridge, or structured prompt…, Stage-aware local processing engine producing structured deliverables.

### Community 26 - "GroqAdapter"
Cohesion: 0.28
Nodes (5): GroqAdapter, Any, Adapter for Groq-hosted LLMs via the OpenAI-compatible chat completions API., test_groq_adapter_missing_key_returns_error(), test_groq_adapter_uses_env_model_override()

### Community 27 - "Handoff Protocol"
Cohesion: 0.22
Nodes (6): graphify, Anti-Patterns (Wastes Tokens), Checkpoint Summary Format (max 500 chars), Handoff Protocol, Memory Entry Format, Session Bootstrap

### Community 28 - "Job & Pipeline Production Schema (v2)"
Cohesion: 0.22
Nodes (8): 1. Job Entity (`jobs` / `orchestrator-state/jobs/<job_id>.json`), 2. Extended Task Schema (`tasks`), 3. QA Review Schema (`qa_reviews`), 4. Worker Node Entity (`workers`), 5. Shared Memory & Team Context (`memory_entries`, `team_context`), Job & Pipeline Production Schema (v2), Memory Entry (`memory_entries`), Team Context (`team_context`)

### Community 29 - "QuotaAwareScheduler"
Cohesion: 0.28
Nodes (5): Connection, QuotaAwareScheduler, Find pending tasks (or expired leases) and auto-assign to best available…, Find the optimal worker ID to claim a given pending task or expired lease., Evaluates pending tasks against registered workers using: Score(W) = w1 *…

### Community 31 - "orchestrator-state schema"
Cohesion: 0.25
Nodes (8): Directory listing as the index, orchestrator-state/checkpoints/<task_id>.json, orchestrator-state/live-status/\<account\>.json, orchestrator-state/memory/\<account\>\_\_\<entry_id\>.json, orchestrator-state/memory/archive/, orchestrator-state schema, orchestrator-state/tasks/<task_id>.json, Token-Efficient Session Bootstrap

### Community 32 - "APPLICATION_VIEW_COMPATIBILITY_POLICY"
Cohesion: 0.25
Nodes (6): APPLICATION_VIEW_COMPATIBILITY_POLICY, AVCP_HIGH_SCALE_FACTOR, AVCP_NONE, AVCP_SMALL_SCREEN, AVCP_TABLET_SMALL_SCREEN, AVCP_VERY_SMALL_SCREEN

### Community 33 - "convert_markdown_to_pdf"
Cohesion: 0.38
Nodes (5): _check_deps(), convert_markdown_to_pdf(), Any, tool, _run_conversion()

### Community 34 - "orchestrator.md"
Cohesion: 0.29
Nodes (4): NotebookLM MCP, Directives:, Token Efficiency:, Worker Role: SEO & AEO Optimization Specialist

### Community 35 - "OllamaLocalAdapter"
Cohesion: 0.33
Nodes (3): OllamaLocalAdapter, Any, Adapter for local Ollama / LM Studio models (e.g. Qwen 2.5, Llama 3.3). $0…

### Community 36 - "usage-watchdog.ps1"
Cohesion: 0.60
Nodes (5): Get-ClaudeTrayUsagePercent(), Invoke-AutoCheckpoint(), Invoke-WatchdogPoll(), Set-CheckpointFiredThisCycle(), Test-CheckpointAlreadyFiredThisCycle()

### Community 37 - "_find_uvx"
Cohesion: 0.50
Nodes (4): _find_uvx(), main(), Find the uvx executable, checking common locations first., Find uvx and launch the NotebookLM MCP server.

### Community 41 - "team-context.md"
Cohesion: 0.50
Nodes (3): Orchestrator MCP Server, SPARK Project, Context

### Community 42 - "Task Entity"
Cohesion: 0.50
Nodes (4): Job Entity, QA Review Entity, Task Entity, Worker Node Entity

### Community 43 - "Worker Role: Formatter & Delivery Packaging"
Cohesion: 0.50
Nodes (3): Directives:, Token Efficiency:, Worker Role: Formatter & Delivery Packaging

### Community 44 - "Worker Role: Orchestrator / Dispatcher"
Cohesion: 0.50
Nodes (4): Responsibilities:, Rules:, Token Efficiency:, Worker Role: Orchestrator / Dispatcher

### Community 45 - "Worker Role: Quality Assurance (QA) & Fact-Checker"
Cohesion: 0.50
Nodes (3): Directives:, Token Efficiency:, Worker Role: Quality Assurance (QA) & Fact-Checker

### Community 46 - "Worker Role: Researcher / Attribute Extractor"
Cohesion: 0.50
Nodes (4): Research Protocol:, Responsibilities:, Strict Rules:, Worker Role: Researcher / Attribute Extractor

### Community 47 - "Worker Role: Copywriter / Drafting Specialist"
Cohesion: 0.50
Nodes (3): Directives:, Token Efficiency:, Worker Role: Copywriter / Drafting Specialist

### Community 49 - "mcp"
Cohesion: 0.67
Nodes (3): mcp, Orchestrator MCP Requirements, Server Requirements

### Community 66 - "routes_jobs.py"
Cohesion: 0.19
Nodes (18): create_job(), get_job(), get_job_metrics(), list_jobs(), _now_iso(), Connection, get, post (+10 more)

### Community 67 - "routes_tasks.py"
Cohesion: 0.34
Nodes (13): CheckpointResponse, CheckpointSubmit, BaseModel, QAReviewResponse, QAReviewSubmit, TaskBlockRequest, TaskClaimRequest, TaskClaimResponse (+5 more)

### Community 68 - "routes_workers.py"
Cohesion: 0.24
Nodes (14): get_worker(), list_workers(), _now_iso(), Connection, get, post, Register or update an AI worker node / profile., List all registered worker nodes. (+6 more)

### Community 69 - "get_db"
Cohesion: 0.67
Nodes (3): get_db(), Connection, Dependency for obtaining an async sqlite database connection in FastAPI routes.

## Knowledge Gaps
- **136 isolated node(s):** `memory_entries`, `team_context`, `VirtualDesktop`, `AVCT_NONE`, `AVCT_DEFAULT` (+131 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 338 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **19 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `ClaudeDesktopProxyAdapter` connect `ClaudeDesktopProxyAdapter` to `main.py`, `BaseWorkerAdapter`, `ClaudeDesktopCDPAdapter`?**
  _High betweenness centrality (0.027) - this node is a cross-community bridge._
- **Why does `IApplicationView` connect `IApplicationView` to `APPLICATION_VIEW_COMPATIBILITY_POLICY`, `IVirtualDesktop`, `IntPtr`, `Size`, `Desktop`, `IApplicationViewCollection`, `VirtualDesktop11-24H2.cs`, `IVirtualDesktopPinnedApps`?**
  _High betweenness centrality (0.023) - this node is a cross-community bridge._
- **Why does `ClaudeDesktopCDPAdapter` connect `ClaudeDesktopCDPAdapter` to `ClaudeDesktopProxyAdapter`, `BaseWorkerAdapter`, `._eval_js`?**
  _High betweenness centrality (0.022) - this node is a cross-community bridge._
- **What connects `memory_entries`, `team_context`, `VirtualDesktop` to the rest of the system?**
  _136 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Connection` be split into smaller, more focused modules?**
  _Cohesion score 0.14130434782608695 - nodes in this community are weakly interconnected._
- **Should `main.py` be split into smaller, more focused modules?**
  _Cohesion score 0.05201636469900643 - nodes in this community are weakly interconnected._
- **Should `orchestrator_mcp_test.py` be split into smaller, more focused modules?**
  _Cohesion score 0.0425531914893617 - nodes in this community are weakly interconnected._