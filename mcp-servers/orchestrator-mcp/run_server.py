#!/usr/bin/env python3
"""orchestrator-mcp: file-based multi-account task coordination.

Unlike notebooklm-mcp/run_server.py (a uvx-shim launcher for a published
PyPI CLI), this is a hand-written MCP server — the first of its kind in
this repo. It requires the `mcp` package installed locally (`pip install
mcp` or `pip install mcp --break-system-packages` on Windows/Debian-style
Python installs); there is no uvx fallback here because there is no
published package to shell out to.

State lives entirely in plain JSON files under orchestrator-state/ at the
repo root (see orchestrator-state/SCHEMA.md for the full file contract).
There is no daemon, no lock file, and no network transport: every write
this server makes is a local file write, and getting that write to another
account's machine is sync.ps1's job, same as everything else in this repo.
"Real-time" here means "as fresh as the last sync.ps1 pull," not literally
instant — see SCHEMA.md's opening paragraph for why every entity is its
own file rather than a shared file multiple accounts edit.

Invoked via team-mcp.json:
    "command": "python3", "args": ["{{REPO_ROOT}}\\mcp-servers\\orchestrator-mcp\\run_server.py"]
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Literal

from mcp.server.mcpserver import MCPServer

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
STATE_ROOT = REPO_ROOT / "orchestrator-state"
TASKS_DIR = STATE_ROOT / "tasks"
LIVE_STATUS_DIR = STATE_ROOT / "live-status"
CHECKPOINTS_DIR = STATE_ROOT / "checkpoints"
MEMORY_DIR = STATE_ROOT / "memory"
MEMORY_ARCHIVE_DIR = MEMORY_DIR / "archive"
JOBS_DIR = STATE_ROOT / "jobs"
QA_REVIEWS_DIR = STATE_ROOT / "qa-reviews"
WORKER_ROLES_PATH = STATE_ROOT / "worker_roles.json"
TEAM_CONTEXT_PATH = REPO_ROOT / "team-context.md"

_TASK_ID_RE = re.compile(r"^task_\d{4}-\d{2}-\d{2}_\d{3}$")
_ACCOUNT_RE = re.compile(r"^[A-Za-z0-9_.\-]{1,64}$")
_MEMORY_FILENAME_RE = re.compile(r"^[A-Za-z0-9_.\-]{1,64}$")

TaskStatus = Literal["pending", "claimed", "blocked", "done", "merged"]
TaskKind = Literal["code", "text"]


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _ensure_dirs() -> None:
    for d in (TASKS_DIR, LIVE_STATUS_DIR, CHECKPOINTS_DIR, MEMORY_DIR, MEMORY_ARCHIVE_DIR, JOBS_DIR, QA_REVIEWS_DIR):
        d.mkdir(parents=True, exist_ok=True)


def _validate_account(account: str) -> None:
    # Guards against path traversal via a crafted account name reaching
    # LIVE_STATUS_DIR / f"{account}.json" — same class of concern as
    # launch_user_n.ps1's Test-ProfilePathWithinBase, applied here to a
    # filename fragment instead of a full path.
    if not _ACCOUNT_RE.match(account):
        raise ValueError(
            f"invalid account name {account!r}: must match {_ACCOUNT_RE.pattern}"
        )


def _validate_task_id(task_id: str) -> None:
    if not _TASK_ID_RE.match(task_id):
        raise ValueError(
            f"invalid task_id {task_id!r}: must match {_TASK_ID_RE.pattern}"
        )


def _task_path(task_id: str) -> Path:
    _validate_task_id(task_id)
    return TASKS_DIR / f"{task_id}.json"


def _checkpoint_path(task_id: str) -> Path:
    _validate_task_id(task_id)
    return CHECKPOINTS_DIR / f"{task_id}.json"


def _live_status_path(account: str) -> Path:
    _validate_account(account)
    return LIVE_STATUS_DIR / f"{account}.json"


def _memory_entry_path(account: str, entry_id: str) -> Path:
    # One file per (account, entry_id) pair — never a shared file two
    # accounts write to, same constraint as tasks/live-status (see
    # SCHEMA.md). entry_id is a timestamp + a short random suffix (see
    # push_memory_entry), not a per-account sequence counter, so two
    # accounts pushing in the same millisecond still land in different
    # files with no read-modify-write on either side.
    _validate_account(account)
    if not _MEMORY_FILENAME_RE.match(entry_id):
        raise ValueError(
            f"invalid entry_id {entry_id!r}: must match {_MEMORY_FILENAME_RE.pattern}"
        )
    return MEMORY_DIR / f"{account}__{entry_id}.json"


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _write_json(path: Path, data: dict[str, Any]) -> None:
    # Write to a temp file then rename, so a crash mid-write never leaves
    # a half-written JSON file for the next sync.ps1 pull to pick up.
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    tmp.replace(path)


def _next_task_id() -> str:
    # Directory listing is the index (see SCHEMA.md's closing section) —
    # sequence number is "count of today's tasks so far + 1", scanned
    # fresh each call rather than tracked in a separate counter file that
    # would itself become a shared-write hazard.
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    prefix = f"task_{today}_"
    existing = sorted(
        p.stem for p in TASKS_DIR.glob(f"{prefix}*.json") if p.stem.startswith(prefix)
    )
    seq = 1
    if existing:
        last_seq = int(existing[-1].removeprefix(prefix))
        seq = last_seq + 1
    return f"{prefix}{seq:03d}"


srv = MCPServer(
    name="orchestrator-mcp",
    description=(
        "File-based task coordination for orchestrator/divider/executor "
        "roles across multiple Claude Desktop profiles. State is JSON "
        "under orchestrator-state/, synced by sync.ps1 — see "
        "orchestrator-state/SCHEMA.md for the file contract."
    ),
)


@srv.tool(
    name="create_task",
    description=(
        "Create a new top-level task (parent_id=null) or a subtask under an "
        "existing task (used by decompose_task's caller). Returns the new "
        "task_id. Role: orchestrator or divider."
    ),
)
def create_task(
    spec: str,
    kind: TaskKind,
    created_by: str,
    parent_id: str | None = None,
) -> dict[str, Any]:
    _ensure_dirs()
    _validate_account(created_by)
    if kind not in ("code", "text"):
        raise ValueError(f"kind must be 'code' or 'text', got {kind!r}")
    if parent_id is not None:
        _validate_task_id(parent_id)
        if not _task_path(parent_id).exists():
            raise ValueError(f"parent_id {parent_id!r} does not exist")

    task_id = _next_task_id()
    now = _now_iso()
    task = {
        "id": task_id,
        "parent_id": parent_id,
        "kind": kind,
        "spec": spec,
        "status": "pending",
        "owner_account": None,
        "branch_name": None,
        "blocked_reason": None,
        "created_by": created_by,
        "created_at": now,
        "updated_at": now,
    }
    path = _task_path(task_id)
    if path.exists():
        # _next_task_id() scans the directory fresh each call, so this
        # should be unreachable outside a pathological same-millisecond
        # race on one machine — fail loudly rather than silently
        # overwrite an existing task.
        raise RuntimeError(f"task_id collision: {task_id} already exists")
    _write_json(path, task)
    return task


@srv.tool(
    name="decompose_task",
    description=(
        "Split an existing task into N subtasks in one call — thin wrapper "
        "around repeated create_task with parent_id set to this task, for "
        "the divider role's static-skeleton-then-dynamic-split workflow. "
        "Does not change the parent task's own status."
    ),
)
def decompose_task(
    parent_id: str,
    subtask_specs: list[str],
    kind: TaskKind,
    created_by: str,
) -> list[dict[str, Any]]:
    _ensure_dirs()
    _validate_task_id(parent_id)
    if not _task_path(parent_id).exists():
        raise ValueError(f"parent_id {parent_id!r} does not exist")
    if not subtask_specs:
        raise ValueError("subtask_specs must be non-empty")

    return [
        create_task(spec=s, kind=kind, created_by=created_by, parent_id=parent_id)
        for s in subtask_specs
    ]


@srv.tool(
    name="claim_task",
    description=(
        "Claim a pending task for the calling account. Re-reads the task "
        "file immediately before writing to narrow the claim-race window "
        "(see SCHEMA.md) — fails with an error if another account already "
        "claimed it since the caller last listed tasks. Role: executor."
    ),
)
def claim_task(task_id: str, account: str, branch_name: str | None = None) -> dict[str, Any]:
    _validate_account(account)
    path = _task_path(task_id)
    task = _read_json(path)
    if task is None:
        raise ValueError(f"task_id {task_id!r} does not exist")

    # Re-read-then-check-then-write, immediately before the write, to
    # close the race window as tightly as a single Python process can —
    # see SCHEMA.md's "Claim race" note for what this does and does not
    # protect against.
    task = _read_json(path)
    if task["status"] != "pending" or task["owner_account"] is not None:
        raise RuntimeError(
            f"task_id {task_id!r} is not claimable: status={task['status']!r}, "
            f"owner_account={task['owner_account']!r} "
            "(already claimed — pull the latest state and pick another task)"
        )

    if task["kind"] == "code" and not branch_name:
        raise ValueError("branch_name is required when claiming a kind='code' task")

    task["status"] = "claimed"
    task["owner_account"] = account
    if task["kind"] == "code":
        task["branch_name"] = branch_name
    task["updated_at"] = _now_iso()
    _write_json(path, task)
    return task


@srv.tool(
    name="release_task",
    description=(
        "Release a claimed task back to pending (owner_account=null), e.g. "
        "when an account is stopping mid-task and another should be able "
        "to pick it up. Only the current owner can release it. Role: executor."
    ),
)
def release_task(task_id: str, account: str) -> dict[str, Any]:
    _validate_account(account)
    path = _task_path(task_id)
    task = _read_json(path)
    if task is None:
        raise ValueError(f"task_id {task_id!r} does not exist")
    if task["owner_account"] != account:
        raise RuntimeError(
            f"task_id {task_id!r} is owned by {task['owner_account']!r}, not {account!r}"
        )
    task["status"] = "pending"
    task["owner_account"] = None
    task["updated_at"] = _now_iso()
    _write_json(path, task)
    return task


@srv.tool(
    name="mark_blocked",
    description=(
        "Mark a claimed task 'blocked' — e.g. waiting on another task, "
        "an external dependency, or a decision from the orchestrator. "
        "Unlike release_task, ownership and branch_name are preserved: "
        "this is a status flag on work still in progress, not a release "
        "back to the pool. Only the current owner can set it. Role: executor."
    ),
)
def mark_blocked(task_id: str, account: str, reason: str) -> dict[str, Any]:
    _validate_account(account)
    path = _task_path(task_id)
    task = _read_json(path)
    if task is None:
        raise ValueError(f"task_id {task_id!r} does not exist")
    if task["owner_account"] != account:
        raise RuntimeError(
            f"task_id {task_id!r} is owned by {task['owner_account']!r}, not {account!r}"
        )
    task["status"] = "blocked"
    task["blocked_reason"] = reason
    task["updated_at"] = _now_iso()
    _write_json(path, task)
    return task


@srv.tool(
    name="unblock_task",
    description=(
        "Move a 'blocked' task back to 'claimed', clearing blocked_reason. "
        "Only the current owner can unblock it — if the blocking condition "
        "means someone else should pick it up instead, use release_task "
        "after unblocking. Role: executor."
    ),
)
def unblock_task(task_id: str, account: str) -> dict[str, Any]:
    _validate_account(account)
    path = _task_path(task_id)
    task = _read_json(path)
    if task is None:
        raise ValueError(f"task_id {task_id!r} does not exist")
    if task["owner_account"] != account:
        raise RuntimeError(
            f"task_id {task_id!r} is owned by {task['owner_account']!r}, not {account!r}"
        )
    if task["status"] != "blocked":
        raise RuntimeError(f"task_id {task_id!r} is not blocked (status={task['status']!r})")
    task["status"] = "claimed"
    task["blocked_reason"] = None
    task["updated_at"] = _now_iso()
    _write_json(path, task)
    return task


@srv.tool(
    name="push_live_status",
    description=(
        "Overwrite the calling account's live-status file — cheap, frequent, "
        "no history (last-write-wins by design, see SCHEMA.md). Call this "
        "often; it's the lightweight real-time layer, not the context handoff. "
        "Role: executor (or orchestrator/divider reporting their own status)."
    ),
)
def push_live_status(
    account: str,
    current_task_id: str | None,
    note: str,
) -> dict[str, Any]:
    _ensure_dirs()
    _validate_account(account)
    if current_task_id is not None:
        _validate_task_id(current_task_id)
    status = {
        "account": account,
        "current_task_id": current_task_id,
        "heartbeat_at": _now_iso(),
        "note": note,
    }
    _write_json(_live_status_path(account), status)
    return status


@srv.tool(
    name="read_all_live_status",
    description=(
        "Read every account's current live-status file. Role: orchestrator "
        "(checking on executors) or anyone wanting a snapshot of who's doing "
        "what right now."
    ),
)
def read_all_live_status() -> list[dict[str, Any]]:
    _ensure_dirs()
    out = []
    for path in sorted(LIVE_STATUS_DIR.glob("*.json")):
        data = _read_json(path)
        if data is not None:
            out.append(data)
    return out


@srv.tool(
    name="push_memory_entry",
    description=(
        "Append a team-memory entry (an account's note/context worth other "
        "accounts seeing). Writes a new file under orchestrator-state/memory/ "
        "— never edits an existing entry, so there is no shared-file write "
        "race (see SCHEMA.md). This is the MCP-native replacement for "
        "manually pasting team-memory.md into a profile's chat: any account "
        "can push a note here and any other account picks it up on next "
        "sync.ps1 pull via read_team_memory. Role: any."
    ),
)
def push_memory_entry(account: str, text: str) -> dict[str, Any]:
    _ensure_dirs()
    _validate_account(account)
    if not text or not text.strip():
        raise ValueError("text must be non-empty")

    now = _now_iso()
    # Timestamp-derived entry_id, collision-checked against the directory
    # (same "scan fresh, don't trust a counter file" approach as
    # _next_task_id) rather than a random suffix, so entries sort
    # chronologically by filename with no separate index.
    base = now.replace(":", "").replace("-", "")
    entry_id = base
    suffix = 2
    while _memory_entry_path(account, entry_id).exists():
        entry_id = f"{base}_{suffix}"
        suffix += 1

    entry = {
        "account": account,
        "text": text,
        "pushed_at": now,
    }
    _write_json(_memory_entry_path(account, entry_id), entry)
    return entry


@srv.tool(
    name="read_team_memory",
    description=(
        "Read team-memory entries, sorted chronologically by pushed_at. "
        "Defaults to the last 20 entries to save tokens — pass limit=null "
        "for all entries (expensive). Supports filtering by since (ISO 8601 "
        "UTC), account, substring search, and project tag. Auto-skips "
        "expired entries (ttl_days). Returns {entries, total_available, "
        "truncated}. Role: any."
    ),
)
def read_team_memory(
    since: str | None = None,
    limit: int | None = 20,
    account: str | None = None,
    search: str | None = None,
    project: str | None = None,
) -> dict[str, Any]:
    _ensure_dirs()
    now_str = _now_iso()
    out = []
    for path in sorted(MEMORY_DIR.glob("*.json")):
        entry = _read_json(path)
        if entry is None:
            continue
        # Time filter
        if since is not None and entry["pushed_at"] < since:
            continue
        # TTL expiry filter (backward compat: missing ttl_days = permanent)
        ttl = entry.get("ttl_days")
        if ttl is not None:
            pushed = entry["pushed_at"]
            try:
                pushed_dt = datetime.strptime(pushed, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                if datetime.now(timezone.utc) > pushed_dt + timedelta(days=ttl):
                    continue
            except (ValueError, TypeError):
                pass  # Malformed date — include rather than silently drop
        # Account filter
        if account is not None and entry.get("account") != account:
            continue
        # Project/tag filter (backward compat: missing tags = [])
        if project is not None:
            tags = entry.get("tags", [])
            if project.lower() not in [t.lower() for t in tags]:
                continue
        # Substring search
        if search is not None and search.lower() not in entry.get("text", "").lower():
            continue
        out.append(entry)
    out.sort(key=lambda e: e.get("priority") == "pinned", reverse=True)
    out.sort(key=lambda e: e["pushed_at"])
    # Pinned entries first, then chronological
    pinned = [e for e in out if e.get("priority") == "pinned"]
    unpinned = [e for e in out if e.get("priority") != "pinned"]
    unpinned.sort(key=lambda e: e["pushed_at"])
    combined = pinned + unpinned
    total = len(combined)
    if limit is not None:
        combined = combined[-limit:]  # Last N entries (most recent)
    return {"entries": combined, "total_available": total, "truncated": total > len(combined)}


@srv.tool(
    name="read_team_context",
    description=(
        "Read team-context.md (the static identity/context scaffold) from "
        "the repo root. Chat-callable replacement for the old auto-copy-to-"
        "clipboard-on-launch step (removed): call this instead of pasting "
        "the file manually as a first message. The file itself is still "
        "hand-edited (no push tool for it, unlike push_memory_entry — it's "
        "meant to be static), so this only ever reflects whatever's "
        "currently checked in. Returns exists=False if the file hasn't been "
        "checked in yet. Role: any."
    ),
)
def read_team_context() -> dict[str, Any]:
    if not TEAM_CONTEXT_PATH.exists():
        return {"exists": False, "content": ""}
    return {
        "exists": True,
        "content": TEAM_CONTEXT_PATH.read_text(encoding="utf-8"),
    }


@srv.tool(
    name="submit_checkpoint",
    description=(
        "Record the full context handoff for a task — the actual merge "
        "input, distinct from push_live_status. For kind='code' tasks, pass "
        "branch_name + commit_sha. For kind='text' tasks, pass result_text. "
        "Marks the task 'done'. Overwrites any prior checkpoint for this "
        "task_id (no checkpoint history — see SCHEMA.md). Role: executor."
    ),
)
def submit_checkpoint(
    task_id: str,
    account: str,
    summary: str,
    branch_name: str | None = None,
    commit_sha: str | None = None,
    result_text: str | None = None,
) -> dict[str, Any]:
    _ensure_dirs()
    _validate_account(account)
    task_path = _task_path(task_id)
    task = _read_json(task_path)
    if task is None:
        raise ValueError(f"task_id {task_id!r} does not exist")
    if task["owner_account"] != account:
        raise RuntimeError(
            f"task_id {task_id!r} is owned by {task['owner_account']!r}, not {account!r} "
            "— only the current owner can submit its checkpoint"
        )

    kind = task["kind"]
    if kind == "code":
        if not branch_name or not commit_sha:
            raise ValueError("kind='code' checkpoints require branch_name and commit_sha")
        result_text = None
    elif kind == "text":
        if not result_text:
            raise ValueError("kind='text' checkpoints require result_text")
        branch_name = None
        commit_sha = None
    else:
        raise RuntimeError(f"task {task_id!r} has unrecognized kind {kind!r}")

    checkpoint = {
        "task_id": task_id,
        "kind": kind,
        "summary": summary,
        "branch_name": branch_name,
        "commit_sha": commit_sha,
        "result_text": result_text,
        "submitted_by": account,
        "submitted_at": _now_iso(),
    }
    _write_json(_checkpoint_path(task_id), checkpoint)

    task["status"] = "done"
    task["updated_at"] = _now_iso()
    _write_json(task_path, task)
    return checkpoint


@srv.tool(
    name="list_tasks",
    description=(
        "List tasks, optionally filtered by status and/or parent_id. "
        "Pass fields (e.g. ['id','status','spec']) for compact output — "
        "omit for full task objects. exclude_terminal=true skips done/merged "
        "tasks. limit caps result count (default 50). Role: any."
    ),
)
def list_tasks(
    status: TaskStatus | None = None,
    parent_id: str | None = None,
    fields: list[str] | None = None,
    exclude_terminal: bool = False,
    limit: int | None = 50,
) -> list[dict[str, Any]]:
    _ensure_dirs()
    terminal = {"done", "merged"}
    out = []
    for path in sorted(TASKS_DIR.glob("*.json")):
        task = _read_json(path)
        if task is None:
            continue
        if status is not None and task["status"] != status:
            continue
        if parent_id is not None and task["parent_id"] != parent_id:
            continue
        if exclude_terminal and task["status"] in terminal:
            continue
        if fields is not None:
            task = {k: task[k] for k in fields if k in task}
        out.append(task)
        if limit is not None and len(out) >= limit:
            break
    return out


@srv.tool(
    name="merge_results",
    description=(
        "Gather checkpoints for every child of parent_id (or every "
        "'done' task with no children, if parent_id is null) and merge "
        "them. kind='text' children: returns their result_text + summaries "
        "for the orchestrator's own LLM call to synthesize — this tool "
        "gathers, it does not synthesize (synthesis is not scriptable, see "
        "SCHEMA.md). kind='code' children: runs `git merge --no-ff "
        "<branch_name>` for each, in checkpoint order, stopping on the "
        "first conflict and running `git merge --abort` so the repo is "
        "left in a known-good state (never mid-merge) rather than "
        "guessing a resolution. Marks successfully merged tasks 'merged'. "
        "Role: orchestrator."
    ),
)
def merge_results(parent_id: str | None = None) -> dict[str, Any]:
    _ensure_dirs()
    if parent_id is not None:
        _validate_task_id(parent_id)
        if not _task_path(parent_id).exists():
            raise ValueError(f"parent_id {parent_id!r} does not exist")
        children = list_tasks(status="done", parent_id=parent_id)
    else:
        children = [
            t for t in list_tasks(status="done") if t["parent_id"] is None
        ]

    if not children:
        return {"merged": [], "text_results": [], "conflicts": []}

    text_results: list[dict[str, Any]] = []
    code_merged: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []

    for task in children:
        checkpoint = _read_json(_checkpoint_path(task["id"]))
        if checkpoint is None:
            conflicts.append(
                {
                    "task_id": task["id"],
                    "reason": "status is 'done' but no checkpoint file exists",
                }
            )
            continue

        if task["kind"] == "text":
            text_results.append(
                {
                    "task_id": task["id"],
                    "summary": checkpoint["summary"],
                    "result_text": checkpoint["result_text"],
                }
            )
            _mark_merged(task)
            continue

        # kind == "code": stop on the first conflict rather than leaving
        # the repo mid-merge for later tasks to trip over — matches
        # sync.ps1's own philosophy of failing loud instead of guessing.
        branch = checkpoint["branch_name"]
        result = subprocess.run(
            ["git", "merge", "--no-ff", branch, "-m", f"merge: {task['id']} ({checkpoint['summary'][:60]})"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            # Leave the repo in a known-good state rather than mid-merge
            # (git status showing "UU <file>") for whatever runs next —
            # merge_results reports the conflict, it doesn't leave a mess
            # for the caller to trip over if they don't check the return
            # value. The conflicting branch/commit is still fully recorded
            # in the checkpoint file for whoever resolves it by hand.
            abort = subprocess.run(
                ["git", "merge", "--abort"],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
            )
            conflicts.append(
                {
                    "task_id": task["id"],
                    "branch_name": branch,
                    "reason": "git merge failed",
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "aborted_cleanly": abort.returncode == 0,
                }
            )
            break
        code_merged.append({"task_id": task["id"], "branch_name": branch})
        _mark_merged(task)

    return {
        "merged": code_merged,
        "text_results": text_results,
        "conflicts": conflicts,
    }


def _mark_merged(task: dict[str, Any]) -> None:
    task["status"] = "merged"
    task["updated_at"] = _now_iso()
    _write_json(_task_path(task["id"]), task)


@srv.tool(
    name="create_job",
    description="Create a client production job (parent entity for pipeline-staged tasks). Role: orchestrator.",
)
def create_job(
    sku: str,
    client: str,
    input_uri: str,
    pipeline: list[str] | None = None,
    quality_rules: list[str] | None = None,
    created_by: str = "orchestrator",
) -> dict[str, Any]:
    _ensure_dirs()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    existing = list(JOBS_DIR.glob(f"job_{today}_*.json"))
    job_id = f"job_{today}_{len(existing) + 1:03d}"
    now = _now_iso()
    
    job_data = {
        "id": job_id,
        "sku": sku,
        "client": client,
        "input_uri": input_uri,
        "status": "intake",
        "pipeline": pipeline or ["research", "draft", "seo_optimize", "qa", "format"],
        "quality_rules": quality_rules or [],
        "created_by": created_by,
        "created_at": now,
        "updated_at": now,
    }
    _write_json(JOBS_DIR / f"{job_id}.json", job_data)
    return job_data


@srv.tool(
    name="list_jobs",
    description="List client production jobs, optionally filtered by status.",
)
def list_jobs(status: str | None = None) -> list[dict[str, Any]]:
    _ensure_dirs()
    jobs = []
    for p in sorted(JOBS_DIR.glob("job_*.json")):
        j = _read_json(p)
        if status is None or j.get("status") == status:
            jobs.append(j)
    return jobs


@srv.tool(
    name="submit_qa_review",
    description="Submit a QA verification pass/fail/revision review for a task. Role: QA reviewer.",
)
def submit_qa_review(
    task_id: str,
    reviewer_account: str,
    verdict: Literal["pass", "fail", "revision_needed"],
    checks_passed: dict[str, bool] | None = None,
    rejection_reason: str | None = None,
) -> dict[str, Any]:
    _ensure_dirs()
    _validate_task_id(task_id)
    _validate_account(reviewer_account)
    
    task_file = _task_path(task_id)
    if not task_file.exists():
        raise ValueError(f"Task '{task_id}' does not exist")
    
    now = _now_iso()
    review_data = {
        "task_id": task_id,
        "reviewer_account": reviewer_account,
        "verdict": verdict,
        "checks_passed": checks_passed or {},
        "rejection_reason": rejection_reason,
        "reviewed_at": now,
    }
    
    review_file = QA_REVIEWS_DIR / f"{task_id}_review_{now.replace(':', '').replace('-', '')}.json"
    _write_json(review_file, review_data)
    
    # Update task state based on verdict
    task = _read_json(task_file)
    if verdict in ("fail", "revision_needed"):
        task["status"] = "pending"
        task["owner_account"] = None
        task["updated_at"] = now
        _write_json(task_file, task)
    elif verdict == "pass":
        task["status"] = "merged"
        task["updated_at"] = now
        _write_json(task_file, task)
        
    return review_data


@srv.tool(
    name="read_worker_roles",
    description="Read the worker role capability registry and system prompt mappings.",
)
def read_worker_roles() -> dict[str, Any]:
    if WORKER_ROLES_PATH.exists():
        return _read_json(WORKER_ROLES_PATH)
    return {}


@srv.tool(
    name="get_job_metrics",
    description="Retrieve live progress and quality metrics for a production job.",
)
def get_job_metrics(job_id: str) -> dict[str, Any]:
    _ensure_dirs()
    job_file = JOBS_DIR / f"{job_id}.json"
    if not job_file.exists():
        raise ValueError(f"Job '{job_id}' not found")
        
    tasks = [t for t in list_tasks() if t.get("job_id") == job_id]
    total = len(tasks)
    completed = sum(1 for t in tasks if t.get("status") in ("done", "merged"))
    pending = sum(1 for t in tasks if t.get("status") == "pending")
    in_progress = sum(1 for t in tasks if t.get("status") == "claimed")
    
    reviews = list(QA_REVIEWS_DIR.glob(f"task_*_{job_id}_*.json"))
    
    return {
        "job_id": job_id,
        "total_tasks": total,
        "completed_tasks": completed,
        "pending_tasks": pending,
        "in_progress_tasks": in_progress,
        "total_reviews": len(reviews),
    }


def main() -> None:
    _ensure_dirs()
    try:
        srv.run(transport="stdio")
    except KeyboardInterrupt:
        sys.exit(130)


if __name__ == "__main__":
    main()