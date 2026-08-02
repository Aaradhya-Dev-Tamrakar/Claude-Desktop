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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from mcp.server.mcpserver import MCPServer

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
STATE_ROOT = REPO_ROOT / "orchestrator-state"
TASKS_DIR = STATE_ROOT / "tasks"
LIVE_STATUS_DIR = STATE_ROOT / "live-status"
CHECKPOINTS_DIR = STATE_ROOT / "checkpoints"

_TASK_ID_RE = re.compile(r"^task_\d{4}-\d{2}-\d{2}_\d{3}$")
_ACCOUNT_RE = re.compile(r"^[A-Za-z0-9_.\-]{1,64}$")

TaskStatus = Literal["pending", "claimed", "blocked", "done", "merged"]
TaskKind = Literal["code", "text"]


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _ensure_dirs() -> None:
    for d in (TASKS_DIR, LIVE_STATUS_DIR, CHECKPOINTS_DIR):
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
        "The directory listing of orchestrator-state/tasks/ is the index — "
        "there is no separate counter/index file (see SCHEMA.md). "
        "Role: any."
    ),
)
def list_tasks(
    status: TaskStatus | None = None,
    parent_id: str | None = None,
) -> list[dict[str, Any]]:
    _ensure_dirs()
    out = []
    for path in sorted(TASKS_DIR.glob("*.json")):
        task = _read_json(path)
        if task is None:
            continue
        if status is not None and task["status"] != status:
            continue
        if parent_id is not None and task["parent_id"] != parent_id:
            continue
        out.append(task)
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


def main() -> None:
    _ensure_dirs()
    try:
        srv.run(transport="stdio")
    except KeyboardInterrupt:
        sys.exit(130)


if __name__ == "__main__":
    main()