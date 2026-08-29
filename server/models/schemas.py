from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel, Field

# Literals
JobStatus = Literal["intake", "decomposing", "running", "qa_hold", "completed", "failed"]
TaskStatus = Literal["pending", "claimed", "blocked", "done", "merged", "failed"]
TaskKind = Literal["text", "code"]
WorkerStatus = Literal["idle", "busy", "cooldown", "offline"]
QAVerdict = Literal["pass", "fail", "revision_needed"]

# ----------------- JOBS -----------------
class JobCreate(BaseModel):
    id: str | None = None
    sku: str
    client: str
    input_uri: str
    pipeline: list[str] = Field(default_factory=lambda: ["research", "draft", "seo_optimize", "qa", "format"])
    quality_rules: list[str] = Field(default_factory=list)
    deadline: datetime | None = None

class JobResponse(BaseModel):
    id: str
    sku: str
    client: str
    input_uri: str
    status: JobStatus
    pipeline: list[str]
    quality_rules: list[str]
    deadline: datetime | None
    created_at: str
    updated_at: str

class JobUpdate(BaseModel):
    status: JobStatus | None = None
    deadline: datetime | None = None

# ----------------- TASKS -----------------
class TaskCreate(BaseModel):
    id: str | None = None
    job_id: str | None = None
    parent_id: str | None = None
    stage: str
    stage_order: int = 1
    kind: TaskKind = "text"
    spec: str
    priority: int = 5

class TaskResponse(BaseModel):
    id: str
    job_id: str | None
    parent_id: str | None
    stage: str
    stage_order: int
    kind: TaskKind
    spec: str
    status: TaskStatus
    priority: int
    owner_worker_id: str | None
    claimed_at: str | None
    lease_expires_at: str | None = None
    claim_token: str | None = None
    completed_at: str | None
    blocked_reason: str | None
    created_at: str
    updated_at: str

class TaskClaimRequest(BaseModel):
    worker_id: str
    lease_seconds: int = 300
    branch_name: str | None = None

class TaskClaimResponse(BaseModel):
    task: TaskResponse
    claim_token: str
    lease_expires_at: str

class TaskLeaseRenewRequest(BaseModel):
    worker_id: str
    claim_token: str | None = None
    lease_seconds: int = 300

class TaskReleaseRequest(BaseModel):
    worker_id: str
    claim_token: str | None = None

class TaskBlockRequest(BaseModel):
    worker_id: str
    reason: str


# ----------------- WORKERS -----------------
class WorkerRegister(BaseModel):
    id: str
    provider: str
    node_id: str
    nickname: str
    capabilities: list[str]
    quota_limit_per_window: int = 50
    cooldown_window_minutes: int = 300

class WorkerHeartbeat(BaseModel):
    current_task_id: str | None = None
    note: str | None = None
    usage_percent: int | None = None
    trigger_cooldown: bool = False

class WorkerResponse(BaseModel):
    id: str
    provider: str
    node_id: str
    nickname: str
    status: WorkerStatus
    capabilities: list[str]
    quota_limit_per_window: int
    quota_used_current: int
    cooldown_window_minutes: int
    cooldown_until: str | None
    last_heartbeat: str | None
    registered_at: str

# ----------------- CHECKPOINTS -----------------
class CheckpointSubmit(BaseModel):
    task_id: str
    job_id: str | None = None
    kind: TaskKind
    summary: str
    result_text: str | None = None
    branch_name: str | None = None
    commit_sha: str | None = None
    submitted_by: str
    claim_token: str | None = None


class CheckpointResponse(BaseModel):
    task_id: str
    job_id: str | None
    kind: TaskKind
    summary: str
    result_text: str | None
    branch_name: str | None
    commit_sha: str | None
    submitted_by: str
    submitted_at: str

# ----------------- QA REVIEWS -----------------
class QAReviewSubmit(BaseModel):
    task_id: str
    job_id: str | None = None
    reviewer_worker_id: str
    verdict: QAVerdict
    rejection_reason: str | None = None
    checks_passed: dict[str, bool] = Field(default_factory=dict)

class QAReviewResponse(BaseModel):
    id: int
    task_id: str
    job_id: str | None
    reviewer_worker_id: str
    verdict: QAVerdict
    rejection_reason: str | None
    checks_passed: dict[str, bool]
    reviewed_at: str

# ----------------- METRICS -----------------
class JobMetricsResponse(BaseModel):
    job_id: str
    total_tasks: int
    completed_tasks: int
    rejected_tasks: int
    total_revisions: int
    ai_calls_count: int
    human_intervention_minutes: float
    throughput_tasks_per_hour: float
    started_at: str | None
    finished_at: str | None
