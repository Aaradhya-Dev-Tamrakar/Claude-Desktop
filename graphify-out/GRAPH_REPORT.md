# Graph Report - Claude-Desktop  (2026-08-31)

## Corpus Check
- 253 files · ~179,672 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 783 nodes · 1625 edges · 55 communities (42 shown, 13 thin omitted)
- Extraction: 91% EXTRACTED · 9% INFERRED · 0% AMBIGUOUS · INFERRED: 148 edges (avg confidence: 0.52)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `968246a5`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 3|Community 3]]
- [[_COMMUNITY_Community 5|Community 5]]
- [[_COMMUNITY_Community 6|Community 6]]
- [[_COMMUNITY_Community 7|Community 7]]
- [[_COMMUNITY_Community 8|Community 8]]
- [[_COMMUNITY_Community 9|Community 9]]
- [[_COMMUNITY_Community 10|Community 10]]
- [[_COMMUNITY_Community 11|Community 11]]
- [[_COMMUNITY_Community 12|Community 12]]
- [[_COMMUNITY_Community 13|Community 13]]
- [[_COMMUNITY_Community 14|Community 14]]
- [[_COMMUNITY_Community 15|Community 15]]
- [[_COMMUNITY_Community 16|Community 16]]
- [[_COMMUNITY_Community 17|Community 17]]
- [[_COMMUNITY_Community 18|Community 18]]
- [[_COMMUNITY_Community 19|Community 19]]
- [[_COMMUNITY_Community 20|Community 20]]
- [[_COMMUNITY_Community 21|Community 21]]
- [[_COMMUNITY_Community 22|Community 22]]
- [[_COMMUNITY_Community 23|Community 23]]
- [[_COMMUNITY_Community 24|Community 24]]
- [[_COMMUNITY_Community 25|Community 25]]
- [[_COMMUNITY_Community 26|Community 26]]
- [[_COMMUNITY_Community 27|Community 27]]
- [[_COMMUNITY_Community 28|Community 28]]
- [[_COMMUNITY_Community 29|Community 29]]
- [[_COMMUNITY_Community 30|Community 30]]
- [[_COMMUNITY_Community 31|Community 31]]
- [[_COMMUNITY_Community 32|Community 32]]
- [[_COMMUNITY_Community 33|Community 33]]
- [[_COMMUNITY_Community 34|Community 34]]
- [[_COMMUNITY_Community 35|Community 35]]
- [[_COMMUNITY_Community 36|Community 36]]
- [[_COMMUNITY_Community 37|Community 37]]
- [[_COMMUNITY_Community 39|Community 39]]
- [[_COMMUNITY_Community 42|Community 42]]
- [[_COMMUNITY_Community 43|Community 43]]
- [[_COMMUNITY_Community 44|Community 44]]
- [[_COMMUNITY_Community 45|Community 45]]
- [[_COMMUNITY_Community 46|Community 46]]
- [[_COMMUNITY_Community 47|Community 47]]
- [[_COMMUNITY_Community 48|Community 48]]
- [[_COMMUNITY_Community 49|Community 49]]
- [[_COMMUNITY_Community 51|Community 51]]
- [[_COMMUNITY_Community 52|Community 52]]
- [[_COMMUNITY_Community 53|Community 53]]
- [[_COMMUNITY_Community 54|Community 54]]
- [[_COMMUNITY_Community 55|Community 55]]
- [[_COMMUNITY_Community 56|Community 56]]

## God Nodes (most connected - your core abstractions)
1. `IApplicationView` - 64 edges
2. `Memory Log` - 55 edges
3. `IntPtr` - 43 edges
4. `Desktop` - 42 edges
5. `ClaudeDesktopCDPAdapter` - 32 edges
6. `get_db_conn()` - 31 edges
7. `IVirtualDesktop` - 25 edges
8. `BaseWorkerAdapter` - 24 edges
9. `IVirtualDesktopManagerInternal` - 24 edges
10. `Program` - 23 edges

## Surprising Connections (you probably didn't know these)
- `Path` --uses--> `ClaudeDesktopProxyAdapter`  [INFERRED]
  tests/test_e2e_pipeline.py → client/adapters/claude_desktop_proxy.py
- `Any` --uses--> `BaseWorkerAdapter`  [INFERRED]
  client/adapters/groq_adapter.py → client/adapters/base_adapter.py
- `Any` --uses--> `BaseWorkerAdapter`  [INFERRED]
  client/adapters/ollama_local_adapter.py → client/adapters/base_adapter.py
- `test_cdp_adapter_init()` --calls--> `ClaudeDesktopCDPAdapter`  [EXTRACTED]
  tests/test_claude_cdp_adapter.py → client/adapters/claude_desktop_cdp.py
- `test_cdp_cooldown_detection_returns_429()` --calls--> `ClaudeDesktopCDPAdapter`  [EXTRACTED]
  tests/test_claude_cdp_adapter.py → client/adapters/claude_desktop_cdp.py

## Import Cycles
- 1-file cycle: `server/main.py -> server/main.py`

## Communities (55 total, 13 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.18
Nodes (42): block_task(), claim_task(), create_task(), get_checkpoint(), get_task(), list_tasks(), _now_iso(), Get single task details. (+34 more)

### Community 1 - "Community 1"
Cohesion: 0.04
Nodes (17): _load_run_server(), Path, pytest specs for orchestrator-mcp's run_server.py.  Unlike tests/launch_user_n.T, Import run_server.py fresh against a specific REPO_ROOT.      run_server.py deri, A throwaway git repo with orchestrator-mcp's run_server.py loaded     against it, repo(), TestBlockedUnblock, TestClaimRace (+9 more)

### Community 2 - "Community 2"
Cohesion: 0.04
Nodes (53): 2026-08-05, 2026-08-06, 2026-08-10, 2026-08-10, 2026-08-11, 2026-08-11, 2026-08-11, 2026-08-11 (+45 more)

### Community 3 - "Community 3"
Cohesion: 0.08
Nodes (59): get_db(), get_db_conn(), init_db(), Dependency for obtaining an async sqlite database connection in FastAPI routes., Initialize database tables and indexes from schema.sql with automatic migration, Obtain a direct async sqlite database connection., Periodic self-healing supervisor loop:     1. Identifies workers with stale hear, run_supervisor_cycle() (+51 more)

### Community 5 - "Community 5"
Cohesion: 0.22
Nodes (38): Any, Path, archive_memory(), _checkpoint_path(), claim_task(), create_job(), create_task(), decompose_task() (+30 more)

### Community 6 - "Community 6"
Cohesion: 0.10
Nodes (20): Add-NewProfile(), Arrange-ClaudeWindows(), Ensure-LocalOrchestratorServer(), Ensure-VirtualDesktopTool(), Expand-TeamMcpPlaceholders(), Format-CardRow(), Get-DesktopBatchAllocation(), Get-EnrichedProfileRows() (+12 more)

### Community 7 - "Community 7"
Cohesion: 0.22
Nodes (20): get_all_context(), get_context_by_key(), list_memory(), _now_iso(), push_memory(), Retrieve a single context value by key., Set or update a persistent team context key-value entry., Push a shared team memory entry to the central database. (+12 more)

### Community 8 - "Community 8"
Cohesion: 0.16
Nodes (15): ClaudeDesktopCDPAdapter, Adapter automating a locally running Claude Desktop Electron app     via Chrome, Check if Claude Desktop Electron process is exposing CDP port and has an active, ClaudeDesktopProxyAdapter, Adapter representing a local Windows Claude Desktop profile session.     Interfa, test_cdp_adapter_init(), test_cdp_cooldown_detection_returns_429(), test_cdp_eval_js_exception() (+7 more)

### Community 9 - "Community 9"
Cohesion: 0.24
Nodes (18): create_job(), get_job(), get_job_metrics(), list_jobs(), _now_iso(), Update job status or deadline., Retrieve throughput, rejection rate, and task statistics for a job., Create a new client job / production batch. (+10 more)

### Community 10 - "Community 10"
Cohesion: 0.20
Nodes (10): Automate Claude Desktop via CDP:         1. Connect to page         2. Check for, Scan DOM for 5-hour usage limit and cooldown warnings., Click new chat or reset conversation., Inject prompt into ProseMirror / contenteditable and click send safely without i, Poll until generation stop button disappears and text settles., Find the WebSocket debugger URL for the active Claude Desktop UI page., Send a JSON-RPC command over WebSocket and await result with timeout., Evaluate a JavaScript expression in the page and return the unwrapped value. (+2 more)

### Community 11 - "Community 11"
Cohesion: 0.16
Nodes (9): GeminiFreeAdapter, Adapter for Google AI Studio Free Tier (Gemini 2.5 / 3.0).     Provides free tok, OllamaLocalAdapter, Adapter for local Ollama / LM Studio models (e.g. Qwen 2.5, Llama 3.3).     $0 i, BaseWorkerAdapter, Any, get_adapter(), main_loop() (+1 more)

### Community 12 - "Community 12"
Cohesion: 0.32
Nodes (16): block_task(), claim_task(), get_job(), get_system_health(), get_task(), get_worker(), list_jobs(), list_tasks() (+8 more)

### Community 13 - "Community 13"
Cohesion: 0.18
Nodes (19): get_worker(), list_workers(), _now_iso(), Register or update an AI worker node / profile., List all registered worker nodes., Retrieve details for a specific worker., Process heartbeat from a worker, updating usage, cooldown, and status., register_worker() (+11 more)

### Community 14 - "Community 14"
Cohesion: 0.15
Nodes (7): ABC, BaseWorkerAdapter, Executes work specified in `spec`.         Returns dictionary:         {, Returns True if the backend AI model / profile is online and usable., Abstract interface for worker execution endpoints., Any, Any

### Community 15 - "Community 15"
Cohesion: 0.22
Nodes (8): _now_iso(), PipelineEngine, Checks whether all tasks for a job have reached terminal state (done/merged)., Decomposes intake jobs into discrete, pipeline-staged tasks and manages     stag, Load SKU definition JSON from sku-templates directory., Takes a job and a list of parsed input items (e.g. from CSV/JSON).         Creat, When a task is verified (or passes QA), triggers generation of the next stage ta, Connection

### Community 16 - "Community 16"
Cohesion: 0.14
Nodes (12): Application rules, Coursework notebooks (IV/I, exam sequence order), Cross-Linking Hub, Hub, Leaf nodes, Pending, Query Protocol (Token Savings), Unlinked notebooks (+4 more)

### Community 17 - "Community 17"
Cohesion: 0.17
Nodes (11): Claude Desktop Multi-Profile & Sync Utilities, Concurrent Mode (Multiple Windows, Multiple Monitors), Features, Files, Launching Claude Desktop Profiles, Repo Structure, Running Autonomous Worker Daemons (v2), Running the Cloud Orchestration Backend (v2) (+3 more)

### Community 18 - "Community 18"
Cohesion: 0.24
Nodes (5): GroqAdapter, Adapter for Groq-hosted LLMs via the OpenAI-compatible chat completions API., Any, test_groq_adapter_missing_key_returns_error(), test_groq_adapter_uses_env_model_override()

### Community 19 - "Community 19"
Cohesion: 0.28
Nodes (5): QuotaAwareScheduler, Find pending tasks (or expired leases) and auto-assign to best available workers, Find the optimal worker ID to claim a given pending task or expired lease., Evaluates pending tasks against registered workers using:     Score(W) = w1 * Pr, Connection

### Community 20 - "Community 20"
Cohesion: 0.22
Nodes (8): 1. Job Entity (`jobs` / `orchestrator-state/jobs/<job_id>.json`), 2. Extended Task Schema (`tasks`), 3. QA Review Schema (`qa_reviews`), 4. Worker Node Entity (`workers`), 5. Shared Memory & Team Context (`memory_entries`, `team_context`), Job & Pipeline Production Schema (v2), Memory Entry (`memory_entries`), Team Context (`team_context`)

### Community 21 - "Community 21"
Cohesion: 0.22
Nodes (8): Directory listing as the index, orchestrator-state/checkpoints/<task_id>.json, orchestrator-state/live-status/\<account\>.json, orchestrator-state/memory/\<account\>\_\_\<entry_id\>.json, orchestrator-state/memory/archive/, orchestrator-state schema, orchestrator-state/tasks/<task_id>.json, Token-Efficient Session Bootstrap

### Community 22 - "Community 22"
Cohesion: 0.33
Nodes (3): Execute task using Anthropic Claude API, CDP bridge, or structured prompt transf, Stage-aware local processing engine producing structured deliverables., Any

### Community 23 - "Community 23"
Cohesion: 0.40
Nodes (5): notebooklm-mcp-cli, _find_uvx(), main(), Find the uvx executable, checking common locations first., Find uvx and launch the NotebookLM MCP server.

### Community 24 - "Community 24"
Cohesion: 0.60
Nodes (5): Get-ClaudeTrayUsagePercent(), Invoke-AutoCheckpoint(), Invoke-WatchdogPoll(), Set-CheckpointFiredThisCycle(), Test-CheckpointAlreadyFiredThisCycle()

### Community 25 - "Community 25"
Cohesion: 0.33
Nodes (6): Formatter & Delivery Packaging, Orchestrator / Dispatcher, Quality Assurance (QA) & Fact-Checker, Researcher / Attribute Extractor, SEO & AEO Optimization Specialist, Copywriter / Drafting Specialist

### Community 26 - "Community 26"
Cohesion: 0.40
Nodes (5): server/mcp_remote.py, server/core/pipeline_engine.py, server/core/scheduler.py, server/main.py, client/worker_daemon.py

### Community 27 - "Community 27"
Cohesion: 0.50
Nodes (4): Job Entity, QA Review Entity, Task Entity, Worker Node Entity

### Community 28 - "Community 28"
Cohesion: 0.40
Nodes (4): Responsibilities:, Rules:, Token Efficiency:, Worker Role: Orchestrator / Dispatcher

### Community 29 - "Community 29"
Cohesion: 0.50
Nodes (3): Directives:, Token Efficiency:, Worker Role: Quality Assurance (QA) & Fact-Checker

### Community 30 - "Community 30"
Cohesion: 0.40
Nodes (4): Research Protocol:, Responsibilities:, Strict Rules:, Worker Role: Researcher / Attribute Extractor

### Community 31 - "Community 31"
Cohesion: 0.50
Nodes (3): Directives:, Token Efficiency:, Worker Role: Copywriter / Drafting Specialist

### Community 32 - "Community 32"
Cohesion: 0.67
Nodes (3): mcp, Orchestrator MCP Requirements, Server Requirements

### Community 33 - "Community 33"
Cohesion: 0.50
Nodes (3): Directives:, Token Efficiency:, Worker Role: Formatter & Delivery Packaging

### Community 34 - "Community 34"
Cohesion: 0.50
Nodes (3): Directives:, Token Efficiency:, Worker Role: SEO & AEO Optimization Specialist

### Community 42 - "Community 42"
Cohesion: 0.67
Nodes (3): 2026-08-22, 2026-08-22, Local Git Workflow & Auto-Sync (`sync.ps1`)

### Community 44 - "Community 44"
Cohesion: 0.10
Nodes (3): PreserveSig, IVirtualDesktop, IVirtualDesktopManagerInternal

### Community 46 - "Community 46"
Cohesion: 0.15
Nodes (7): bool, EnumDelegate, int, string, StringBuilder, Program, uint

### Community 48 - "Community 48"
Cohesion: 0.11
Nodes (9): Guid, MarshalAs, DesktopManager, Guids, IObjectArray, IServiceProvider10, IVirtualDesktopManager, VDeskTool (+1 more)

### Community 52 - "Community 52"
Cohesion: 0.33
Nodes (5): Anti-Patterns (Wastes Tokens), Checkpoint Summary Format (max 500 chars), Handoff Protocol, Memory Entry Format, Session Bootstrap

## Knowledge Gaps
- **133 isolated node(s):** `Any`, `TaskStatus`, `HTTPAuthorizationCredentials`, `Row`, `Path` (+128 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **13 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `ClaudeDesktopProxyAdapter` connect `Community 8` to `Community 3`, `Community 11`, `Community 14`, `Community 22`?**
  _High betweenness centrality (0.051) - this node is a cross-community bridge._
- **Why does `FastAPI` connect `Community 13` to `Community 0`, `Community 9`, `Community 3`, `Community 7`?**
  _High betweenness centrality (0.043) - this node is a cross-community bridge._
- **Why does `IApplicationView` connect `Community 43` to `Community 44`, `Community 45`, `Community 48`, `Community 49`, `Community 53`, `Community 54`, `Community 55`, `Community 56`?**
  _High betweenness centrality (0.027) - this node is a cross-community bridge._
- **Are the 4 inferred relationships involving `ClaudeDesktopCDPAdapter` (e.g. with `BaseWorkerAdapter` and `ClaudeDesktopProxyAdapter`) actually correct?**
  _`ClaudeDesktopCDPAdapter` has 4 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Any`, `Abstract interface for worker execution endpoints.`, `Executes work specified in `spec`.         Returns dictionary:         {` to the rest of the system?**
  _205 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Community 1` be split into smaller, more focused modules?**
  _Cohesion score 0.043478260869565216 - nodes in this community are weakly interconnected._
- **Should `Community 2` be split into smaller, more focused modules?**
  _Cohesion score 0.03773584905660377 - nodes in this community are weakly interconnected._