# Job & Pipeline Production Schema (v2)

This document formalizes the production layer additions (Jobs, Pipeline Stages, Worker Registry, Checkpoints, QA Reviews, and Metrics) governing both cloud and local operations.

---

## 1. Job Entity (`jobs` / `orchestrator-state/jobs/<job_id>.json`)

Represents a client work order or batch of deliverables.

```json
{
  "id": "job_2026-08-29_001",
  "sku": "100_product_descriptions",
  "client": "acme_retail",
  "input_uri": "data/client_inputs/job_2026-08-29_001/catalog.csv",
  "status": "intake | decomposing | running | qa_hold | completed | failed",
  "pipeline": ["research", "draft", "seo_optimize", "qa", "format"],
  "quality_rules": [
    "No invented specifications or compatibility claims",
    "Brand name must match input exactly",
    "Description length 80-150 words"
  ],
  "deadline": "2026-09-05T00:00:00Z",
  "created_at": "2026-08-29T10:00:00Z",
  "updated_at": "2026-08-29T10:00:00Z"
}
```

---

## 2. Extended Task Schema (`tasks`)

Each task is an atomic work unit belonging to a stage in a job's pipeline.

```json
{
  "id": "task_2026-08-29_001",
  "job_id": "job_2026-08-29_001",
  "parent_id": null,
  "stage": "draft",
  "stage_order": 2,
  "kind": "text",
  "spec": "Detailed instructions for this stage including prior stage output",
  "status": "pending | claimed | blocked | done | merged | failed",
  "priority": 5,
  "owner_worker_id": "node_win_user3",
  "claimed_at": "2026-08-29T10:15:00Z",
  "completed_at": "2026-08-29T10:17:30Z",
  "blocked_reason": null,
  "created_at": "2026-08-29T10:00:00Z",
  "updated_at": "2026-08-29T10:17:30Z"
}
```

---

## 3. QA Review Schema (`qa_reviews`)

Stores structured verification results from QA workers before stage advancement.

```json
{
  "id": 1,
  "task_id": "task_2026-08-29_001",
  "job_id": "job_2026-08-29_001",
  "reviewer_worker_id": "node_win_user6",
  "verdict": "pass | fail | revision_needed",
  "rejection_reason": "Specification for battery life was hallucinated (source says 10h, output says 20h)",
  "checks_passed": {
    "no_hallucinations": false,
    "word_count": true,
    "brand_consistency": true
  },
  "reviewed_at": "2026-08-29T10:20:00Z"
}
```

---

## 4. Worker Node Entity (`workers`)

Represents execution endpoints (Claude Desktop profiles, Gemini Free API, Ollama Local models).

```json
{
  "id": "node_win_user3",
  "provider": "claude_desktop",
  "node_id": "aaradhya-win-pc",
  "nickname": "xavier",
  "status": "idle | busy | cooldown | offline",
  "capabilities": ["writing", "drafting", "copywriting"],
  "quota_limit_per_window": 50,
  "quota_used_current": 12,
  "cooldown_window_minutes": 300,
  "cooldown_until": null,
  "last_heartbeat": "2026-08-29T10:22:00Z",
  "registered_at": "2026-08-29T08:00:00Z"
}
```

---

## 5. Shared Memory & Team Context (`memory_entries`, `team_context`)

Provides persistent database-backed cross-profile shared memory and durable team context.

### Memory Entry (`memory_entries`)
```json
{
  "id": 1,
  "author": "user1",
  "category": "architecture",
  "content": "Deployed remote MCP server with 23 tools over SSE at /mcp",
  "metadata": {"source": "manual", "environment": "production"},
  "created_at": "2026-08-31T08:00:00Z"
}
```

### Team Context (`team_context`)
```json
{
  "key": "standing_instructions",
  "value": "All workers must follow single-responsibility role prompts.",
  "updated_by": "admin",
  "updated_at": "2026-08-31T08:00:00Z"
}
```
