#!/usr/bin/env python3
"""
Live Multi-Account Scratchpad Handshake Verification:
Exercises the complete decoupled multi-account coordination flow without browser automation:
1. Account 1 (user1 - Lead/Architect):
   - Initializes scratchpad via init_scratchpad().
   - Creates task via create_task().
   - Appends architectural requirements and delegation handoff via append_scratchpad().
2. Account 2 (user2 - Builder/Coder):
   - Bootstraps context in 1 call via get_context_bundle().
   - Ingests scratchpad content from user1.
   - Claims task via claim_task().
   - Executes implementation, appends progress via append_scratchpad().
   - Submits checkpoint via submit_checkpoint().
3. Account 3 (user6 - Adversarial QA Reviewer):
   - Bootstraps context via get_context_bundle().
   - Audits deliverable against task specification and scratchpad log.
   - Submits QA review via submit_qa_review() with verdict='pass'.
   - Appends final sign-off note via append_scratchpad().
4. Verification:
   - Confirms zero data loss, exact chronological integrity, and state transition to 'merged'.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

# Ensure stdout handles UTF-8 on Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

RUN_SERVER_PATH = REPO_ROOT / "mcp-servers" / "orchestrator-mcp" / "run_server.py"
spec = importlib.util.spec_from_file_location("orchestrator_mcp", RUN_SERVER_PATH)
rs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rs)


def run_multi_account_handshake():
    print("=" * 75)
    print("  LIVE MULTI-ACCOUNT SCRATCHPAD HANDSHAKE VERIFICATION")
    print(f"  Target: {rs.STATE_ROOT}")
    print("=" * 75)

    # -------------------------------------------------------------------------
    # STAGE 1: Profile 1 (user1 - Lead / Architect)
    # -------------------------------------------------------------------------
    print("\n[Stage 1] Profile 1 (user1: Lead / Architect)")
    init_res = rs.init_scratchpad(
        scratchpad_id="shared",
        title="Decoupled Multi-Account Coordination Sprint",
        spec="Verify end-to-end multi-account scratchpad collaboration protocol without browser automation.",
        author="user1",
    )
    print(f"  [user1] Initialized shared scratchpad at: {init_res['path']}")

    task = rs.create_task(
        spec="Implement and verify zero-CDP multi-account scratchpad coordination",
        kind="code",
        created_by="user1",
    )
    task_id = task["id"]
    print(f"  [user1] Created task: {task_id} (status: {task['status']}, kind: {task['kind']})")

    append_arch = rs.append_scratchpad(
        scratchpad_id="shared",
        author="user1",
        heading="Architecture & Delegation Directive",
        content=(
            f"Created {task_id} for Builder/Coder implementation.\n"
            f"- Task ID: `{task_id}`\n"
            f"- Requirements: Validate zero-daemon file contract in orchestrator-state/.\n"
            f"- Assigned to: `user2` for implementation."
        ),
    )
    print(f"  [user1] Appended architecture directive ({append_arch['appended_chars']} chars)")

    # -------------------------------------------------------------------------
    # STAGE 2: Profile 2 (user2 - Builder / Coder)
    # -------------------------------------------------------------------------
    print("\n[Stage 2] Profile 2 (user2: Builder / Coder)")
    bundle_user2 = rs.get_context_bundle(
        account="user2",
        memory_limit=5,
        memory_hours=24,
        scratchpad_id="shared",
    )
    print(f"  [user2] Bootstrapped context in single call.")
    assert bundle_user2["scratchpad"]["exists"] is True, "Scratchpad must exist in bundle"
    scratchpad_content = bundle_user2["scratchpad"]["content"]
    assert task_id in scratchpad_content, f"Task {task_id} must appear in scratchpad content"
    print(f"  [user2] Read scratchpad: verified task {task_id} directive from user1.")

    claimed_task = rs.claim_task(
        task_id=task_id,
        account="user2",
        branch_name="feat/scratchpad-handshake",
    )
    print(f"  [user2] Claimed {task_id} (status: {claimed_task['status']}, owner: {claimed_task['owner_account']})")
    assert claimed_task["status"] == "claimed"
    assert claimed_task["owner_account"] == "user2"

    append_impl = rs.append_scratchpad(
        scratchpad_id="shared",
        author="user2",
        heading="Implementation Progress & Deliverable",
        content=(
            f"Implemented and validated {task_id} on branch `feat/scratchpad-handshake`.\n"
            f"- File contracts verified across `tasks/`, `checkpoints/`, `live-status/`, and `scratchpads/`.\n"
            f"- All local tests green (34/34 specs passing).\n"
            f"- Submitting checkpoint for QA review."
        ),
    )
    print(f"  [user2] Logged implementation progress to scratchpad ({append_impl['appended_chars']} chars)")

    checkpoint = rs.submit_checkpoint(
        task_id=task_id,
        account="user2",
        summary="Verified decoupled multi-account scratchpad coordination contract",
        branch_name="feat/scratchpad-handshake",
        commit_sha="8060f35",
        compact=True,
    )
    task_done = rs._read_json(rs._task_path(task_id))
    print(f"  [user2] Checkpoint submitted (task status: {task_done['status']})")
    assert task_done["status"] == "done"
    assert checkpoint["task_id"] == task_id

    # -------------------------------------------------------------------------
    # STAGE 3: Profile 3 (user6 - Adversarial QA Reviewer)
    # -------------------------------------------------------------------------
    print("\n[Stage 3] Profile 3 (user6: Adversarial QA Reviewer)")
    bundle_user6 = rs.get_context_bundle(
        account="user6",
        memory_limit=5,
        memory_hours=24,
        scratchpad_id="shared",
    )
    print(f"  [user6] Bootstrapped context in single call.")
    assert "user1: Architecture & Delegation Directive" in bundle_user6["scratchpad"]["content"]
    assert "user2: Implementation Progress & Deliverable" in bundle_user6["scratchpad"]["content"]
    print(f"  [user6] Ingested scratchpad history from both user1 and user2.")

    # Review deliverable
    qa_review = rs.submit_qa_review(
        task_id=task_id,
        reviewer_account="user6",
        verdict="pass",
        checks_passed={
            "no_hallucinations": True,
            "deterministic_tests_pass": True,
            "scratchpad_handshake_clean": True,
        },
    )
    print(f"  [user6] Submitted QA review: verdict={qa_review['verdict']}")
    assert qa_review["verdict"] == "pass"

    # Check task moved to merged
    task_final = rs._read_json(rs._task_path(task_id))
    print(f"  [user6] Task {task_id} transitioned to: {task_final['status']}")
    assert task_final["status"] == "merged"

    append_qa = rs.append_scratchpad(
        scratchpad_id="shared",
        author="user6",
        heading="QA Certification & Sign-off",
        content=(
            f"Adversarial QA review complete for {task_id}.\n"
            f"- Verdict: PASS (all checks satisfied).\n"
            f"- Task status transitioned to `merged`.\n"
            f"- Multi-account handshake certified."
        ),
    )
    print(f"  [user6] Appended QA sign-off to scratchpad ({append_qa['appended_chars']} chars)")

    # -------------------------------------------------------------------------
    # STAGE 4: Final Scratchpad State Audit
    # -------------------------------------------------------------------------
    print("\n[Stage 4] Final Scratchpad State Audit")
    final_scratchpad = rs.read_scratchpad("shared")
    print("-" * 75)
    print(final_scratchpad["content"])
    print("-" * 75)

    assert "user1" in final_scratchpad["content"]
    assert "user2" in final_scratchpad["content"]
    assert "user6" in final_scratchpad["content"]
    assert "QA Certification & Sign-off" in final_scratchpad["content"]

    print("\n" + "=" * 75)
    print("  MULTI-ACCOUNT HANDSHAKE VERIFIED WITH 100% SUCCESS")
    print("=" * 75)


if __name__ == "__main__":
    run_multi_account_handshake()
