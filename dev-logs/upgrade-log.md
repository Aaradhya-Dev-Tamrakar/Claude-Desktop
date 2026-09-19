# Repository Upgrade Log

Date: 2026-09-03

## Completed Upgrades

### MCP Configuration

- Paused `site-mcp`.
- Paused `cloud-orchestrator-mcp`.
- Preserved both definitions under `_disabled_mcpServers` for later reactivation.
- Removed stale active registrations from all 26 current Claude profile/native configurations.
- Preserved local `orchestrator-mcp`, NotebookLM, and md2pdf MCP integrations.

Files:

- `team-mcp.json`
- `team-claude-config.json`
- `sync-mcp.ps1`
- `launch_user_n.ps1`

### Configuration Safety

- Added atomic JSON configuration writes using temporary files.
- Added `.bak` backups before replacing existing Claude configuration files.
- Added temporary-file cleanup after successful or failed writes.
- Added regression coverage for backup and replacement behavior.

Files:

- `sync-mcp.ps1`
- `launch_user_n.ps1`
- `tests/launch_user_n.Tests.ps1`

### Security and Reproducibility

- Removed the known default API authentication key fallback.
- Added production startup validation requiring `API_AUTH_KEY` with at least 32 characters.
- Added configurable `ENVIRONMENT` and `CORS_ORIGINS` settings.
- Restricted default CORS origins to local development addresses.
- Pinned backend and test dependency versions from the working virtual environment.
- Added GitHub Actions CI for Python and PowerShell tests.
- Added security configuration regression tests.

Files:

- `server/core/config.py`
- `server/main.py`
- `server/requirements.txt`
- `.env.example`
- `.github/workflows/ci.yml`
- `tests/test_security_config.py`

### Worker Reliability

- Added periodic task lease renewal while a worker executes a task.
- Added configurable `LEASE_SECONDS` and `LEASE_RENEWAL_SECONDS` settings.
- Added exponential reconnect backoff up to 60 seconds.
- Made worker registration failures fail fast.
- Added explicit checkpoint response validation.

File:

- `client/worker_daemon.py`

### Pipeline Resilience

- Added configurable `MAX_TASK_ATTEMPTS`, defaulting to 3.
- Moves tasks to `failed` after the attempt limit is exceeded.
- Marks released task attempts as `failed` instead of leaving them `running`.
- Made duplicate checkpoint submissions from the same worker idempotent.
- Prevents duplicate completion side effects such as quota increments and pipeline advancement.
- Added regression tests for retries, releases, and duplicate checkpoints.

Files:

- `server/core/config.py`
- `server/api/routes_tasks.py`
- `tests/test_remote_mcp.py`

### Operational Visibility

- Added request correlation through `X-Request-ID`.
- Added structured JSON HTTP request logs.
- Added Prometheus-compatible `/metrics` output.
- Added `/health/live` liveness checks.
- Added `/health/ready` database readiness checks.
- Added focused health, metrics, and correlation tests.

Files:

- `server/core/observability.py`
- `server/main.py`
- `tests/test_health.py`

### PowerShell Diagnostics

- Renamed helper functions to approved PowerShell verb names:
  - `Pad-VisibleRight` to `Format-VisibleRight`
  - `Truncate-VisibleText` to `Format-VisibleText`
- Updated the cooldown reminder helper consistently.
- Adjusted `-WhatIf` behavior so an already-running profile still renders the planned launch card.
- Confirmed the saved launcher parses cleanly.

Files:

- `launch_user_n.ps1`
- `cooldown-reminder.ps1`

## Validation Results

- Python test suite: 61 passed.
- PowerShell Pester suite: 49 passed.
- Worker daemon and server route compilation passed.
- PowerShell parser validation passed.
- `git diff --check` passed.
- All 26 Claude configurations were verified to have no active `site-mcp` or `cloud-orchestrator-mcp` entries while retaining local `orchestrator-mcp`.

## Optional Future Work

- Add a profile management command set for list, clone, backup, restore, and remove.
- Add config drift detection and explicit rollback commands.
- Add a dashboard for workers, queue depth, quotas, task failures, and pipeline progress.
- Resolve the SQLite versus PostgreSQL deployment/documentation difference.
- Add deeper CI checks for Docker startup, dependency vulnerability scanning, and type checking.
- Add task cancellation, dead-letter inspection, and administrative retry controls.

---

Date: 2026-09-19

## Completed Upgrades: Invariant Calibration & Worker Completeness (`INV-WSR-002`)

### P0: REST API & Remote MCP Auth Enforcement
- Attached `verify_api_key` dependency to all FastAPI APIRouters (`/jobs`, `/tasks`, `/workers`, `/memory`).
- Validates bearer authorization / `X-API-Key` headers when `API_AUTH_KEY` is configured or in production environment.
- Added comprehensive authentication test coverage.

### P1: Closed-Loop Worker Dispatch (Invariant A)
- Implemented `POST /tasks/acquire` endpoint and `QuotaAwareScheduler.acquire_task_for_worker`.
- Replaced uncoordinated pending task polling in `client/worker_daemon.py` and `client/fleet_supervisor.py` with atomic single-step matching, leasing, and dispatch.

### P2: Real vs. Simulation Isolation (Invariant B)
- Enforced strict typed error propagation (`RATE_LIMIT_429`, `AUTH_ERROR`, `HTTP_5xx`, `NETWORK_ERROR`) on adapter failures.
- Prohibited fallback to synthetic success mocks when provider/network exceptions occur.

### P3: Empirical Quota & Resource Telemetry (Invariant C)
- Replaced hardcoded `usage_percent: 10` heartbeats with live OS performance metrics (`cpu_percent`, `memory_percent` via `psutil`).
- Extended `WorkerHeartbeat` schema to ingest structured system and rate limit telemetry.

### P4: Atomic DAG Stage Advancement (Invariant D)
- Refactored `PipelineEngine.advance_task_to_next_stage` and `check_and_finalize_job` to support transactional integration (`auto_commit=False`).
- Wrapped checkpoint insertion, task completion, attempt logging, worker quota updates, successor task creation, and job finalization inside single atomic transactions.

### Verification Results
- Full Python test suite: **93/93 passed**.
- Graphify AST knowledge graph updated: 1,316 nodes, 2,446 edges, 116 communities.

