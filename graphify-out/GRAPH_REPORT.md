# Graph Report - Claude-Desktop  (2026-08-29)

## Corpus Check
- 247 files · ~159,026 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 495 nodes · 902 edges · 44 communities (36 shown, 8 thin omitted)
- Extraction: 85% EXTRACTED · 15% INFERRED · 0% AMBIGUOUS · INFERRED: 137 edges (avg confidence: 0.52)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `c51c62f7`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 3|Community 3]]
- [[_COMMUNITY_Community 4|Community 4]]
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
- [[_COMMUNITY_Community 17|Community 17]]
- [[_COMMUNITY_Community 18|Community 18]]
- [[_COMMUNITY_Community 19|Community 19]]
- [[_COMMUNITY_Community 20|Community 20]]
- [[_COMMUNITY_Community 22|Community 22]]
- [[_COMMUNITY_Community 24|Community 24]]
- [[_COMMUNITY_Community 26|Community 26]]
- [[_COMMUNITY_Community 29|Community 29]]
- [[_COMMUNITY_Community 30|Community 30]]
- [[_COMMUNITY_Community 31|Community 31]]
- [[_COMMUNITY_Community 32|Community 32]]
- [[_COMMUNITY_Community 33|Community 33]]
- [[_COMMUNITY_Community 34|Community 34]]
- [[_COMMUNITY_Community 35|Community 35]]
- [[_COMMUNITY_Community 36|Community 36]]
- [[_COMMUNITY_Community 37|Community 37]]
- [[_COMMUNITY_Community 38|Community 38]]
- [[_COMMUNITY_Community 39|Community 39]]
- [[_COMMUNITY_Community 40|Community 40]]
- [[_COMMUNITY_Community 41|Community 41]]
- [[_COMMUNITY_Community 42|Community 42]]
- [[_COMMUNITY_Community 43|Community 43]]

## God Nodes (most connected - your core abstractions)
1. `Memory Log` - 55 edges
2. `ClaudeDesktopCDPAdapter` - 32 edges
3. `BaseWorkerAdapter` - 24 edges
4. `Connection` - 21 edges
5. `ClaudeDesktopProxyAdapter` - 17 edges
6. `_ensure_dirs()` - 15 edges
7. `_read_json()` - 15 edges
8. `_write_json()` - 14 edges
9. `TaskResponse` - 14 edges
10. `GroqAdapter` - 13 edges

## Surprising Connections (you probably didn't know these)
- `Path` --uses--> `ClaudeDesktopProxyAdapter`  [INFERRED]
  tests/test_e2e_pipeline.py → client/adapters/claude_desktop_proxy.py
- `Orchestrator / Dispatcher` --references--> `Job Entity`  [INFERRED]
  worker-prompts/orchestrator.md → orchestrator-state/JOB_SCHEMA.md
- `Any` --uses--> `BaseWorkerAdapter`  [INFERRED]
  client/adapters/groq_adapter.py → client/adapters/base_adapter.py
- `Any` --uses--> `BaseWorkerAdapter`  [INFERRED]
  client/adapters/ollama_local_adapter.py → client/adapters/base_adapter.py
- `test_cdp_adapter_init()` --calls--> `ClaudeDesktopCDPAdapter`  [EXTRACTED]
  tests/test_claude_cdp_adapter.py → client/adapters/claude_desktop_cdp.py

## Import Cycles
- 1-file cycle: `server/main.py -> server/main.py`

## Communities (44 total, 8 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.16
Nodes (9): GeminiFreeAdapter, Adapter for Google AI Studio Free Tier (Gemini 2.5 / 3.0).     Provides free tok, OllamaLocalAdapter, Adapter for local Ollama / LM Studio models (e.g. Qwen 2.5, Llama 3.3).     $0 i, BaseWorkerAdapter, Any, get_adapter(), main_loop() (+1 more)

### Community 1 - "Community 1"
Cohesion: 0.18
Nodes (42): block_task(), claim_task(), create_task(), get_checkpoint(), get_task(), list_tasks(), _now_iso(), Get single task details. (+34 more)

### Community 2 - "Community 2"
Cohesion: 0.05
Nodes (16): _load_run_server(), Path, pytest specs for orchestrator-mcp's run_server.py.  Unlike tests/launch_user_n.T, Import run_server.py fresh against a specific REPO_ROOT.      run_server.py deri, A throwaway git repo with orchestrator-mcp's run_server.py loaded     against it, repo(), TestBlockedUnblock, TestClaimRace (+8 more)

### Community 3 - "Community 3"
Cohesion: 0.22
Nodes (36): Any, Path, _checkpoint_path(), claim_task(), create_job(), create_task(), decompose_task(), _ensure_dirs() (+28 more)

### Community 4 - "Community 4"
Cohesion: 0.20
Nodes (10): Automate Claude Desktop via CDP:         1. Connect to page         2. Check for, Scan DOM for 5-hour usage limit and cooldown warnings., Click new chat or reset conversation., Inject prompt into ProseMirror / contenteditable and click send safely without i, Poll until generation stop button disappears and text settles., Find the WebSocket debugger URL for the active Claude Desktop UI page., Send a JSON-RPC command over WebSocket and await result with timeout., Evaluate a JavaScript expression in the page and return the unwrapped value. (+2 more)

### Community 5 - "Community 5"
Cohesion: 0.09
Nodes (23): init_db(), Initialize database tables and indexes from schema.sql with automatic migration, Periodic self-healing supervisor loop:     1. Identifies workers with stale hear, run_supervisor_cycle(), FastAPI, lifespan(), Background supervisor monitoring heartbeats and dead workers., run_supervisor_loop() (+15 more)

### Community 6 - "Community 6"
Cohesion: 0.19
Nodes (18): get_worker(), list_workers(), _now_iso(), Register or update an AI worker node / profile., List all registered worker nodes., Retrieve details for a specific worker., Process heartbeat from a worker, updating usage, cooldown, and status., register_worker() (+10 more)

### Community 7 - "Community 7"
Cohesion: 0.24
Nodes (18): create_job(), get_job(), get_job_metrics(), list_jobs(), _now_iso(), Update job status or deadline., Retrieve throughput, rejection rate, and task statistics for a job., Create a new client job / production batch. (+10 more)

### Community 8 - "Community 8"
Cohesion: 0.32
Nodes (16): block_task(), claim_task(), get_job(), get_system_health(), get_task(), get_worker(), list_jobs(), list_tasks() (+8 more)

### Community 9 - "Community 9"
Cohesion: 0.22
Nodes (8): _now_iso(), PipelineEngine, Checks whether all tasks for a job have reached terminal state (done/merged)., Decomposes intake jobs into discrete, pipeline-staged tasks and manages     stag, Load SKU definition JSON from sku-templates directory., Takes a job and a list of parsed input items (e.g. from CSV/JSON).         Creat, When a task is verified (or passes QA), triggers generation of the next stage ta, Connection

### Community 10 - "Community 10"
Cohesion: 0.30
Nodes (11): Add-NewProfile(), Expand-TeamMcpPlaceholders(), Get-ValidatedProfilePath(), Invoke-ProfileLaunch(), Merge-McpServers(), New-Border(), New-Row(), Resolve-SingleAccount() (+3 more)

### Community 11 - "Community 11"
Cohesion: 0.22
Nodes (10): Job Entity, QA Review Schema, Task Entity, Worker Node Entity, Formatter & Delivery Packaging, Orchestrator / Dispatcher, Quality Assurance (QA) & Fact-Checker, Researcher / Attribute Extractor (+2 more)

### Community 12 - "Community 12"
Cohesion: 0.28
Nodes (5): QuotaAwareScheduler, Find pending tasks (or expired leases) and auto-assign to best available workers, Find the optimal worker ID to claim a given pending task or expired lease., Evaluates pending tasks against registered workers using:     Score(W) = w1 * Pr, Connection

### Community 13 - "Community 13"
Cohesion: 0.22
Nodes (3): Orchestrator MCP Server, Context, SPARK project

### Community 14 - "Community 14"
Cohesion: 0.40
Nodes (5): notebooklm-mcp-cli, _find_uvx(), main(), Find the uvx executable, checking common locations first., Find uvx and launch the NotebookLM MCP server.

### Community 15 - "Community 15"
Cohesion: 0.60
Nodes (5): Get-ClaudeTrayUsagePercent(), Invoke-AutoCheckpoint(), Invoke-WatchdogPoll(), Set-CheckpointFiredThisCycle(), Test-CheckpointAlreadyFiredThisCycle()

### Community 17 - "Community 17"
Cohesion: 0.20
Nodes (9): BiasAperture Project, Application rules, Coursework notebooks (IV/I, exam sequence order), Cross-Linking Hub, Hub, Leaf nodes, Pending, Unlinked notebooks (+1 more)

### Community 18 - "Community 18"
Cohesion: 0.67
Nodes (3): mcp, Orchestrator MCP Requirements, Server Requirements

### Community 24 - "Community 24"
Cohesion: 0.04
Nodes (54): 2026-08-05, 2026-08-06, 2026-08-10, 2026-08-10, 2026-08-11, 2026-08-11, 2026-08-11, 2026-08-11 (+46 more)

### Community 29 - "Community 29"
Cohesion: 0.16
Nodes (15): ClaudeDesktopCDPAdapter, Adapter automating a locally running Claude Desktop Electron app     via Chrome, Check if Claude Desktop Electron process is exposing CDP port and has an active, ClaudeDesktopProxyAdapter, Adapter representing a local Windows Claude Desktop profile session.     Interfa, test_cdp_adapter_init(), test_cdp_cooldown_detection_returns_429(), test_cdp_eval_js_exception() (+7 more)

### Community 30 - "Community 30"
Cohesion: 0.15
Nodes (7): ABC, BaseWorkerAdapter, Executes work specified in `spec`.         Returns dictionary:         {, Returns True if the backend AI model / profile is online and usable., Abstract interface for worker execution endpoints., Any, Any

### Community 31 - "Community 31"
Cohesion: 0.17
Nodes (11): Claude Desktop Multi-Profile & Sync Utilities, Concurrent Mode (Multiple Windows, Multiple Monitors), Features, Files, Launching Claude Desktop Profiles, Repo Structure, Running Autonomous Worker Daemons (v2), Running the Cloud Orchestration Backend (v2) (+3 more)

### Community 32 - "Community 32"
Cohesion: 0.24
Nodes (5): GroqAdapter, Adapter for Groq-hosted LLMs via the OpenAI-compatible chat completions API., Any, test_groq_adapter_missing_key_returns_error(), test_groq_adapter_uses_env_model_override()

### Community 33 - "Community 33"
Cohesion: 0.29
Nodes (6): Directory listing as the index, orchestrator-state/checkpoints/<task_id>.json, orchestrator-state/live-status/\<account\>.json, orchestrator-state/memory/\<account\>\_\_\<entry_id\>.json, orchestrator-state schema, orchestrator-state/tasks/<task_id>.json

### Community 34 - "Community 34"
Cohesion: 0.33
Nodes (3): Execute task using Anthropic Claude API, CDP bridge, or structured prompt transf, Stage-aware local processing engine producing structured deliverables., Any

### Community 35 - "Community 35"
Cohesion: 0.33
Nodes (5): 1. Job Entity (`jobs` / `orchestrator-state/jobs/<job_id>.json`), 2. Extended Task Schema (`tasks`), 3. QA Review Schema (`qa_reviews`), 4. Worker Node Entity (`workers`), Job & Pipeline Production Schema (v2)

### Community 36 - "Community 36"
Cohesion: 0.50
Nodes (3): Responsibilities:, Rules:, Worker Role: Orchestrator / Dispatcher

### Community 37 - "Community 37"
Cohesion: 0.50
Nodes (3): Output Verdict:, Verification Checklist:, Worker Role: Quality Assurance (QA) & Fact-Checker

### Community 38 - "Community 38"
Cohesion: 0.50
Nodes (3): Responsibilities:, Strict Rules:, Worker Role: Researcher / Attribute Extractor

### Community 39 - "Community 39"
Cohesion: 0.50
Nodes (3): Responsibilities:, Strict Rules:, Worker Role: Copywriter / Drafting Specialist

## Knowledge Gaps
- **107 isolated node(s):** `Any`, `TaskStatus`, `Connection`, `Path`, `Path` (+102 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **8 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `ClaudeDesktopProxyAdapter` connect `Community 29` to `Community 0`, `Community 34`, `Community 5`, `Community 30`?**
  _High betweenness centrality (0.084) - this node is a cross-community bridge._
- **Why does `FastAPI` connect `Community 5` to `Community 1`, `Community 6`, `Community 7`?**
  _High betweenness centrality (0.076) - this node is a cross-community bridge._
- **Why does `ClaudeDesktopCDPAdapter` connect `Community 29` to `Community 0`, `Community 34`, `Community 4`, `Community 30`?**
  _High betweenness centrality (0.039) - this node is a cross-community bridge._
- **Are the 4 inferred relationships involving `ClaudeDesktopCDPAdapter` (e.g. with `BaseWorkerAdapter` and `ClaudeDesktopProxyAdapter`) actually correct?**
  _`ClaudeDesktopCDPAdapter` has 4 INFERRED edges - model-reasoned connections that need verification._
- **Are the 12 inferred relationships involving `BaseWorkerAdapter` (e.g. with `ClaudeDesktopCDPAdapter` and `ClaudeDesktopProxyAdapter`) actually correct?**
  _`BaseWorkerAdapter` has 12 INFERRED edges - model-reasoned connections that need verification._
- **Are the 11 inferred relationships involving `Connection` (e.g. with `CheckpointResponse` and `CheckpointSubmit`) actually correct?**
  _`Connection` has 11 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Any`, `Abstract interface for worker execution endpoints.`, `Executes work specified in `spec`.         Returns dictionary:         {` to the rest of the system?**
  _170 weakly-connected nodes found - possible documentation gaps or missing edges._