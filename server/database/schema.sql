-- Enable WAL mode and foreign key constraints
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- 1. JOBS TABLE (Client Work Orders / Deliverable Units)
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,                       -- e.g. "job_2026-08-29_001"
    sku TEXT NOT NULL,                         -- e.g. "100_product_descriptions"
    client TEXT NOT NULL,
    input_uri TEXT NOT NULL,                   -- local path or object storage URI
    status TEXT NOT NULL DEFAULT 'intake',     -- 'intake', 'decomposing', 'running', 'qa_hold', 'completed', 'failed'
    pipeline JSON NOT NULL,                    -- Array of stage names: ["research", "draft", "seo_optimize", "qa", "format"]
    quality_rules JSON NOT NULL,               -- Array of string rules / checklist
    deadline DATETIME,
    created_at DATETIME DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at DATETIME DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

-- 2. WORKERS TABLE (Registered Execution Endpoints)
CREATE TABLE IF NOT EXISTS workers (
    id TEXT PRIMARY KEY,                       -- e.g. "node_win_user1", "groq_worker_01"
    provider TEXT NOT NULL,                    -- 'claude_desktop', 'groq', 'ollama_local', 'gemini_free'
    node_id TEXT NOT NULL,                     -- e.g. "aaradhya-win-pc", "oracle-cloud-a1"
    nickname TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'offline',    -- 'idle', 'busy', 'cooldown', 'offline'
    capabilities JSON NOT NULL,                -- Array of capabilities: ["writing", "research", "code", "qa", "seo"]
    quota_limit_per_window INTEGER NOT NULL,   -- e.g. 50 tasks / window
    quota_used_current INTEGER DEFAULT 0,
    cooldown_window_minutes INTEGER DEFAULT 300, -- e.g. 300 min (5 hours for Claude Free)
    cooldown_until DATETIME,
    last_heartbeat DATETIME,
    registered_at DATETIME DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

-- 3. TASKS TABLE (Atomic Units of Work)
CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,                       -- e.g. "task_2026-08-29_001"
    job_id TEXT REFERENCES jobs(id) ON DELETE CASCADE,
    parent_id TEXT REFERENCES tasks(id) ON DELETE CASCADE,
    stage TEXT NOT NULL,                       -- "research", "draft", "qa", etc.
    stage_order INTEGER NOT NULL DEFAULT 1,
    kind TEXT NOT NULL CHECK(kind IN ('text', 'code')),
    spec TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',    -- 'pending', 'claimed', 'blocked', 'done', 'merged', 'failed'
    priority INTEGER NOT NULL DEFAULT 5,       -- 1 (highest) to 10 (lowest)
    owner_worker_id TEXT REFERENCES workers(id) ON DELETE SET NULL,
    claimed_at DATETIME,
    lease_expires_at DATETIME,
    claim_token TEXT,
    completed_at DATETIME,
    blocked_reason TEXT,
    created_at DATETIME DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    updated_at DATETIME DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

-- 4. ATTEMPTS & AUDIT LOGS
CREATE TABLE IF NOT EXISTS task_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    worker_id TEXT NOT NULL REFERENCES workers(id) ON DELETE CASCADE,
    attempt_number INTEGER NOT NULL,
    status TEXT NOT NULL,                      -- 'running', 'succeeded', 'failed', 'timeout'
    error_message TEXT,
    started_at DATETIME DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    finished_at DATETIME
);

-- 5. CHECKPOINTS (Stage Deliverable Records)
CREATE TABLE IF NOT EXISTS checkpoints (
    task_id TEXT PRIMARY KEY REFERENCES tasks(id) ON DELETE CASCADE,
    job_id TEXT REFERENCES jobs(id) ON DELETE CASCADE,
    kind TEXT NOT NULL,
    summary TEXT NOT NULL,
    result_text TEXT,                          -- Formatted copy / JSON / memo for text tasks
    branch_name TEXT,                          -- Git branch for code tasks
    commit_sha TEXT,                           -- Git SHA for code tasks
    submitted_by TEXT NOT NULL REFERENCES workers(id) ON DELETE CASCADE,
    submitted_at DATETIME DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

-- 6. QA REVIEWS & VERIFICATION
CREATE TABLE IF NOT EXISTS qa_reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    job_id TEXT REFERENCES jobs(id) ON DELETE CASCADE,
    reviewer_worker_id TEXT NOT NULL REFERENCES workers(id) ON DELETE CASCADE,
    verdict TEXT NOT NULL CHECK(verdict IN ('pass', 'fail', 'revision_needed')),
    rejection_reason TEXT,
    checks_passed JSON NOT NULL,               -- e.g. {"no_hallucinations": true, "word_count": true}
    reviewed_at DATETIME DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

-- 7. METRICS & TELEMETRY
CREATE TABLE IF NOT EXISTS job_metrics (
    job_id TEXT PRIMARY KEY REFERENCES jobs(id) ON DELETE CASCADE,
    total_tasks INTEGER DEFAULT 0,
    completed_tasks INTEGER DEFAULT 0,
    rejected_tasks INTEGER DEFAULT 0,
    total_revisions INTEGER DEFAULT 0,
    ai_calls_count INTEGER DEFAULT 0,
    human_intervention_minutes REAL DEFAULT 0.0,
    throughput_tasks_per_hour REAL DEFAULT 0.0,
    started_at DATETIME,
    finished_at DATETIME
);

-- Indexes for ultra-fast query and queue operations
CREATE INDEX IF NOT EXISTS idx_tasks_status_stage ON tasks(status, stage, priority);
CREATE INDEX IF NOT EXISTS idx_tasks_job_id ON tasks(job_id);
CREATE INDEX IF NOT EXISTS idx_tasks_owner ON tasks(owner_worker_id);
CREATE INDEX IF NOT EXISTS idx_workers_status ON workers(status, cooldown_until);
CREATE INDEX IF NOT EXISTS idx_checkpoints_job_id ON checkpoints(job_id);
CREATE INDEX IF NOT EXISTS idx_qa_reviews_task_id ON qa_reviews(task_id);
