#!/usr/bin/env python3
"""
End-to-End Task Lifecycle Validation:
Verifies the complete decentralized file coordination loop:
1. create_task() creates a pending code task in orchestrator-state/tasks/.
2. CopilotQueueWorker detects, claims, executes, and writes checkpoint to orchestrator-state/checkpoints/.
3. QA review evaluates the checkpoint:
   - Tests 'revision_needed' reset loop (status -> 'pending', owner_account -> None).
   - Tests second pickup and execution by worker.
   - Tests final 'pass' verdict advancing status to 'merged'.
4. Single-call session bootstrap (get_context_bundle) returns context, tasks, workers, and scratchpad.
5. Shared scratchpad collaboration logging (append_scratchpad & read_scratchpad).
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import sys
from pathlib import Path

# Paths
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT.parent / "Fleet-Orchestrator"))

RUN_SERVER_PATH = REPO_ROOT / "mcp-servers" / "orchestrator-mcp" / "run_server.py"
spec = importlib.util.spec_from_file_location("orchestrator_mcp", RUN_SERVER_PATH)
rs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rs)

from tools.copilot_queue_worker import CopilotQueueWorker


async def run_e2e_validation():
    print("=" * 70)
    print("  E2E TASK LIFECYCLE & ZERO-CDP COORDINATION VALIDATION")
    print(f"  State Directory: {rs.STATE_ROOT}")
    print("=" * 70)

    # 1. Create a new code task via orchestrator-mcp
    print("\n[Step 1] Creating new code task via orchestrator-mcp create_task()...")
    spec = "Implement decoupled stdio file-contract validation test suite"
    task = rs.create_task(
        spec=spec,
        kind="code",
        created_by="adevtmr",
    )
    task_id = task["id"]
    print(f"  [+] Created task: {task_id}")
    assert task["status"] == "pending", f"Expected pending, got {task['status']}"
    assert task["kind"] == "code"
    assert task["created_by"] == "adevtmr"

    task_file = rs._task_path(task_id)
    assert task_file.exists(), f"Task file {task_file} does not exist"

    # 2. Worker pickup and execution via CopilotQueueWorker targeting task_id
    print(f"\n[Step 2] Launching CopilotQueueWorker to pick up and process {task_id}...")
    worker = CopilotQueueWorker(state_dir=rs.STATE_ROOT, dry_run=True)
    processed = await worker.process_one_task(target_task_id=task_id)
    assert processed, f"CopilotQueueWorker failed to process task {task_id}"

    # Reload task from disk
    task_after_worker = rs._read_json(task_file)
    print(f"  [+] Task status after worker run: {task_after_worker['status']}")
    print(f"  [+] Owner account: {task_after_worker.get('owner_account')}")
    assert task_after_worker["status"] == "done", f"Expected status 'done', got {task_after_worker['status']}"
    assert task_after_worker["owner_account"] is not None

    checkpoint_file = rs._checkpoint_path(task_id)
    assert checkpoint_file.exists(), f"Checkpoint {checkpoint_file} does not exist"
    checkpoint = rs._read_json(checkpoint_file)
    print(f"  [+] Checkpoint summary: {checkpoint['summary']}")
    print(f"  [+] Checkpoint branch: {checkpoint.get('branch_name')}")
    print(f"  [+] Checkpoint SHA: {checkpoint.get('commit_sha')}")
    assert checkpoint["task_id"] == task_id
    assert checkpoint["commit_sha"] is not None

    # 3. Test Adversarial QA Review: First rejection / revision loop
    print(f"\n[Step 3] Submitting QA review with verdict='revision_needed' for {task_id}...")
    rev_result = rs.submit_qa_review(
        task_id=task_id,
        reviewer_account="adt_ieee",
        verdict="revision_needed",
        checks_passed={"no_hallucinations": True, "tests_clean": False},
        rejection_reason="Test coverage requires additional edge-case assertion",
    )
    print(f"  [+] Review submitted: verdict={rev_result['verdict']}")
    task_after_rejection = rs._read_json(task_file)
    print(f"  [+] Task status after revision_needed: {task_after_rejection['status']}")
    assert task_after_rejection["status"] == "pending", "Task should be reset to 'pending' on revision_needed"
    assert task_after_rejection["owner_account"] is None, "Owner should be cleared on revision_needed"

    # 4. Worker re-claims and re-executes task
    print(f"\n[Step 4] Worker re-claims and re-completes task {task_id}...")
    reprocessed = await worker.process_one_task(target_task_id=task_id)
    assert reprocessed, f"Worker failed to reprocess revised task {task_id}"
    task_recompleted = rs._read_json(task_file)
    assert task_recompleted["status"] == "done"
    print(f"  [+] Task re-completed: status={task_recompleted['status']}")

    # 5. Final QA Review: Pass verdict
    print(f"\n[Step 5] Submitting final QA review with verdict='pass' for {task_id}...")
    pass_result = rs.submit_qa_review(
        task_id=task_id,
        reviewer_account="adt_ieee",
        verdict="pass",
        checks_passed={"no_hallucinations": True, "tests_clean": True, "schema_valid": True},
    )
    print(f"  [+] Review verdict: {pass_result['verdict']}")
    final_task = rs._read_json(task_file)
    print(f"  [+] Final task status: {final_task['status']}")
    assert final_task["status"] == "merged", f"Expected 'merged', got {final_task['status']}"

    # 6. Test Single-Call Session Bootstrap (get_context_bundle)
    print("\n[Step 6] Testing single-call session bootstrap (get_context_bundle)...")
    bundle = rs.get_context_bundle(
        account="adevtmr",
        memory_limit=5,
        memory_hours=24,
        scratchpad_id="shared",
    )
    print(f"  [+] Account: {bundle['account']}")
    print(f"  [+] Pending tasks count: {bundle['pending_tasks_count']}")
    print(f"  [+] Recent memory entries returned: {len(bundle['recent_memory'])}")
    print(f"  [+] Active workers: {len(bundle['active_workers'])}")
    print(f"  [+] Scratchpad exists: {bundle['scratchpad']['exists']}")
    assert bundle["account"] == "adevtmr"
    assert "team_context" in bundle
    assert "scratchpad" in bundle

    # 7. Test Shared Scratchpad Logging
    print("\n[Step 7] Testing shared scratchpad logging...")
    append_res = rs.append_scratchpad(
        scratchpad_id="shared",
        author="adt_ieee",
        heading="E2E Lifecycle Certified",
        content=f"Task {task_id} successfully verified across complete cycle: pending -> claimed -> done -> revision_needed -> done -> merged.",
    )
    print(f"  [+] Appended scratchpad entry: {append_res['status']} ({append_res['appended_chars']} chars)")
    scratchpad_state = rs.read_scratchpad("shared")
    assert f"Task {task_id} successfully verified" in scratchpad_state["content"]

    print("\n" + "=" * 70)
    print(f"  ALL 7 LIFECYCLE CHECKS PASSED FOR TASK: {task_id}")
    print("=" * 70)
    return task_id


if __name__ == "__main__":
    asyncio.run(run_e2e_validation())
