"""pytest specs for orchestrator-mcp's run_server.py.

Unlike tests/launch_user_n.Tests.ps1 (Pester, PowerShell), this is Python
testing Python — orchestrator-mcp is the first hand-written-logic Python
file in this repo (notebooklm-mcp/run_server.py is a thin uvx-shim with
no meaningful branches to test). Run:

    pip install pytest mcp --break-system-packages
    pytest tests/orchestrator_mcp_test.py -v

Each test gets its own throwaway git repo + orchestrator-state/ directory
via the `repo` fixture below, so tests never touch this actual repo's
state or git history, and tests can run in any order without interfering
with each other.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
import time
from pathlib import Path

import pytest

RUN_SERVER_PATH = Path(__file__).resolve().parent.parent / "mcp-servers" / "orchestrator-mcp" / "run_server.py"


def _load_run_server(repo_root: Path):
    """Import run_server.py fresh against a specific REPO_ROOT.

    run_server.py derives REPO_ROOT from its own file location
    (Path(__file__).resolve().parent.parent.parent), so to point it at a
    throwaway test repo instead of this actual repo, the module is loaded
    from a copy placed inside that test repo's own mcp-servers/orchestrator-mcp/
    — matching exactly how team-mcp.json's {{REPO_ROOT}} expansion would
    invoke the real file on a contributor's machine, rather than patching
    module globals after import.
    """
    dest_dir = repo_root / "mcp-servers" / "orchestrator-mcp"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / "run_server.py"
    dest.write_text(RUN_SERVER_PATH.read_text(encoding="utf-8"), encoding="utf-8")

    spec = importlib.util.spec_from_file_location(f"run_server_{id(repo_root)}", dest)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.REPO_ROOT == repo_root.resolve(), (
        f"REPO_ROOT resolution broke: {module.REPO_ROOT} != {repo_root.resolve()}"
    )
    return module


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """A throwaway git repo with orchestrator-mcp's run_server.py loaded
    against it, cwd'd into it for the duration of the test.
    """
    repo_root = tmp_path / "test-repo"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)

    subprocess.run(["git", "init", "--quiet"], cwd=repo_root, check=True)
    subprocess.run(["git", "config", "user.email", "test@test.local"], cwd=repo_root, check=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=repo_root, check=True)
    subprocess.run(["git", "checkout", "-b", "main-test", "--quiet"], cwd=repo_root, check=True)
    (repo_root / "README.md").write_text("test repo\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo_root, check=True)
    subprocess.run(["git", "commit", "-m", "baseline", "--quiet"], cwd=repo_root, check=True)
    (repo_root / "base.txt").write_text("baseline content\n", encoding="utf-8")
    subprocess.run(["git", "add", "base.txt"], cwd=repo_root, check=True)
    subprocess.run(["git", "commit", "-m", "add base.txt", "--quiet"], cwd=repo_root, check=True)

    rs = _load_run_server(repo_root)
    return rs, repo_root


class TestToolRegistration:
    def test_all_expected_tools_are_registered(self, repo):
        rs, _ = repo
        import asyncio

        async def get_names():
            tools = await rs.srv.list_tools()
            return sorted(t.name for t in tools)

        names = asyncio.run(get_names())
        expected = sorted(
            [
                "archive_memory",
                "create_task",
                "decompose_task",
                "claim_task",
                "release_task",
                "mark_blocked",
                "unblock_task",
                "push_live_status",
                "read_all_live_status",
                "push_memory_entry",
                "read_team_memory",
                "read_team_context",
                "get_context_bundle",
                "submit_checkpoint",
                "list_tasks",
                "merge_results",
                "create_job",
                "list_jobs",
                "submit_qa_review",
                "read_worker_roles",
                "get_job_metrics",
            ]
        )
        assert names == expected


class TestTextTaskLifecycle:
    def test_create_decompose_claim_checkpoint_merge(self, repo):
        rs, _ = repo

        parent = rs.create_task(spec="research topic A", kind="text", created_by="user1")
        subs = rs.decompose_task(
            parent_id=parent["id"],
            subtask_specs=["sub A1", "sub A2"],
            kind="text",
            created_by="user1",
        )
        assert len(subs) == 2
        assert all(s["parent_id"] == parent["id"] for s in subs)

        rs.claim_task(task_id=subs[0]["id"], account="user2")
        rs.claim_task(task_id=subs[1]["id"], account="user3")

        rs.submit_checkpoint(task_id=subs[0]["id"], account="user2", summary="A1 done", result_text="findings A1")
        rs.submit_checkpoint(task_id=subs[1]["id"], account="user3", summary="A2 done", result_text="findings A2")

        result = rs.merge_results(parent_id=parent["id"])
        assert len(result["text_results"]) == 2
        assert len(result["conflicts"]) == 0

        final = rs.list_tasks(parent_id=parent["id"])
        assert all(t["status"] == "merged" for t in final)


class TestCodeTaskLifecycle:
    def test_clean_merge(self, repo):
        rs, repo_root = repo

        task = rs.create_task(spec="add feature Y", kind="code", created_by="user1")
        branch = f"task/{task['id']}"
        rs.claim_task(task_id=task["id"], account="user4", branch_name=branch)

        subprocess.run(["git", "branch", branch], cwd=repo_root, check=True)
        subprocess.run(["git", "checkout", branch], cwd=repo_root, check=True)
        (repo_root / "feature_y.txt").write_text("feature Y\n", encoding="utf-8")
        subprocess.run(["git", "add", "feature_y.txt"], cwd=repo_root, check=True)
        subprocess.run(["git", "commit", "-m", "feature Y", "--quiet"], cwd=repo_root, check=True)
        sha = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=repo_root, capture_output=True, text=True
        ).stdout.strip()
        subprocess.run(["git", "checkout", "main-test"], cwd=repo_root, check=True)

        rs.submit_checkpoint(
            task_id=task["id"], account="user4", summary="feature Y done",
            branch_name=branch, commit_sha=sha,
        )

        result = rs.merge_results()
        assert len(result["merged"]) == 1
        assert len(result["conflicts"]) == 0
        assert (repo_root / "feature_y.txt").exists()

        final = rs._read_json(rs._task_path(task["id"]))
        assert final["status"] == "merged"

    def test_conflict_aborts_cleanly(self, repo):
        rs, repo_root = repo

        task = rs.create_task(spec="conflicting edit", kind="code", created_by="user1")
        branch = f"task/{task['id']}"
        rs.claim_task(task_id=task["id"], account="user5", branch_name=branch)

        subprocess.run(["git", "branch", branch], cwd=repo_root, check=True)
        subprocess.run(["git", "checkout", branch], cwd=repo_root, check=True)
        (repo_root / "base.txt").write_text("branch content\n", encoding="utf-8")
        subprocess.run(["git", "add", "base.txt"], cwd=repo_root, check=True)
        subprocess.run(["git", "commit", "-m", "branch change", "--quiet"], cwd=repo_root, check=True)
        sha = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=repo_root, capture_output=True, text=True
        ).stdout.strip()
        subprocess.run(["git", "checkout", "main-test"], cwd=repo_root, check=True)

        # main-test also edits base.txt, so the merge actually conflicts.
        (repo_root / "base.txt").write_text("main content\n", encoding="utf-8")
        subprocess.run(["git", "add", "base.txt"], cwd=repo_root, check=True)
        subprocess.run(["git", "commit", "-m", "main change", "--quiet"], cwd=repo_root, check=True)

        rs.submit_checkpoint(
            task_id=task["id"], account="user5", summary="conflicting change",
            branch_name=branch, commit_sha=sha,
        )

        result = rs.merge_results()
        assert len(result["conflicts"]) == 1
        assert result["conflicts"][0]["aborted_cleanly"] is True

        # The load-bearing assertion: merge_results must never leave the
        # repo mid-merge. git status showing "UU <file>" is the signature
        # of an unresolved conflict left on disk — this caught a real bug
        # during development (first version had no `git merge --abort`).
        status = subprocess.run(
            ["git", "status", "--porcelain"], cwd=repo_root, capture_output=True, text=True
        ).stdout
        assert "UU" not in status

        final = rs._read_json(rs._task_path(task["id"]))
        assert final["status"] == "done"  # not "merged" — the merge failed


class TestBlockedUnblock:
    def test_mark_blocked_preserves_ownership(self, repo):
        rs, _ = repo
        task = rs.create_task(spec="blocked test", kind="text", created_by="user1")
        rs.claim_task(task_id=task["id"], account="user6")

        blocked = rs.mark_blocked(task_id=task["id"], account="user6", reason="waiting on X")
        assert blocked["status"] == "blocked"
        assert blocked["blocked_reason"] == "waiting on X"
        assert blocked["owner_account"] == "user6"  # ownership preserved, unlike release_task

    def test_only_owner_can_unblock(self, repo):
        rs, _ = repo
        task = rs.create_task(spec="blocked test", kind="text", created_by="user1")
        rs.claim_task(task_id=task["id"], account="user6")
        rs.mark_blocked(task_id=task["id"], account="user6", reason="waiting on X")

        with pytest.raises(RuntimeError):
            rs.unblock_task(task_id=task["id"], account="user7")

        result = rs.unblock_task(task_id=task["id"], account="user6")
        assert result["status"] == "claimed"
        assert result["blocked_reason"] is None

    def test_unblock_non_blocked_task_raises(self, repo):
        rs, _ = repo
        task = rs.create_task(spec="not blocked", kind="text", created_by="user1")
        rs.claim_task(task_id=task["id"], account="user6")
        with pytest.raises(RuntimeError):
            rs.unblock_task(task_id=task["id"], account="user6")


class TestClaimRace:
    def test_double_claim_rejected(self, repo):
        rs, _ = repo
        task = rs.create_task(spec="race test", kind="text", created_by="user1")
        rs.claim_task(task_id=task["id"], account="user8")
        with pytest.raises(RuntimeError):
            rs.claim_task(task_id=task["id"], account="user9")

    def test_release_then_reclaim_succeeds(self, repo):
        rs, _ = repo
        task = rs.create_task(spec="release test", kind="text", created_by="user1")
        rs.claim_task(task_id=task["id"], account="user8")
        rs.release_task(task_id=task["id"], account="user8")
        reclaimed = rs.claim_task(task_id=task["id"], account="user9")
        assert reclaimed["owner_account"] == "user9"

    def test_non_owner_cannot_release(self, repo):
        rs, _ = repo
        task = rs.create_task(spec="release test", kind="text", created_by="user1")
        rs.claim_task(task_id=task["id"], account="user8")
        with pytest.raises(RuntimeError):
            rs.release_task(task_id=task["id"], account="user9")


class TestLiveStatus:
    def test_independent_files_per_account(self, repo):
        rs, _ = repo
        rs.push_live_status(account="user8", current_task_id=None, note="working")
        rs.push_live_status(account="user6", current_task_id=None, note="idle")
        all_status = rs.read_all_live_status()
        assert len(all_status) == 2
        accounts = {s["account"] for s in all_status}
        assert accounts == {"user8", "user6"}

    def test_overwrite_is_last_write_wins(self, repo):
        rs, _ = repo
        rs.push_live_status(account="user8", current_task_id=None, note="first note")
        rs.push_live_status(account="user8", current_task_id=None, note="second note")
        all_status = rs.read_all_live_status()
        assert len(all_status) == 1  # not 2 — overwrites, no history
        assert all_status[0]["note"] == "second note"


class TestTeamMemory:
    def test_push_then_read_round_trip(self, repo):
        rs, _ = repo
        rs.push_memory_entry(account="user1", text="first fact", tags=["SPARK"], ttl_days=14, priority="high")
        res = rs.read_team_memory()
        entries = res["entries"]
        assert len(entries) == 1
        assert entries[0]["account"] == "user1"
        assert entries[0]["text"] == "first fact"
        assert entries[0]["tags"] == ["SPARK"]
        assert entries[0]["ttl_days"] == 14
        assert entries[0]["priority"] == "high"
        assert res["total_available"] == 1
        assert res["truncated"] is False

    def test_multiple_accounts_all_returned_sorted(self, repo):
        rs, _ = repo
        rs.push_memory_entry(account="user1", text="first fact")
        time.sleep(1.1)
        rs.push_memory_entry(account="user2", text="second fact")
        time.sleep(1.1)
        rs.push_memory_entry(account="user1", text="third fact")
        res = rs.read_team_memory()
        entries = res["entries"]
        assert len(entries) == 3
        assert [e["text"] for e in entries] == ["first fact", "second fact", "third fact"]
        assert [e["pushed_at"] for e in entries] == sorted(e["pushed_at"] for e in entries)

    def test_since_filter_excludes_earlier_entries(self, repo):
        rs, _ = repo
        e1 = rs.push_memory_entry(account="user1", text="first fact")
        time.sleep(1.1)
        e2 = rs.push_memory_entry(account="user2", text="second fact")
        time.sleep(1.1)
        e3 = rs.push_memory_entry(account="user1", text="third fact")

        since_e2 = rs.read_team_memory(since=e2["pushed_at"])["entries"]
        assert [e["text"] for e in since_e2] == ["second fact", "third fact"]

        since_e3 = rs.read_team_memory(since=e3["pushed_at"])["entries"]
        assert [e["text"] for e in since_e3] == ["third fact"]

    def test_limit_and_search_and_project_filter(self, repo):
        rs, _ = repo
        rs.push_memory_entry(account="user1", text="SPARK fall detection model", tags=["SPARK"])
        rs.push_memory_entry(account="user2", text="BiasAperture fairness metric", tags=["BiasAperture"])
        rs.push_memory_entry(account="user3", text="SPARK gateway wire format", tags=["SPARK"])

        # Search filter
        spark_res = rs.read_team_memory(search="wire")
        assert len(spark_res["entries"]) == 1
        assert spark_res["entries"][0]["account"] == "user3"

        # Project tag filter
        spark_tags = rs.read_team_memory(project="SPARK")
        assert len(spark_tags["entries"]) == 2

        # Limit filter
        limited = rs.read_team_memory(limit=1)
        assert len(limited["entries"]) == 1
        assert limited["total_available"] == 3
        assert limited["truncated"] is True

    def test_same_account_repeat_push_no_collision(self, repo):
        rs, _ = repo
        e1 = rs.push_memory_entry(account="user1", text="note A")
        e2 = rs.push_memory_entry(account="user1", text="note B")
        res = rs.read_team_memory()
        assert len(res["entries"]) == 2
        assert {e["text"] for e in res["entries"]} == {"note A", "note B"}

    def test_empty_text_rejected(self, repo):
        rs, _ = repo
        with pytest.raises(ValueError):
            rs.push_memory_entry(account="user1", text="")
        with pytest.raises(ValueError):
            rs.push_memory_entry(account="user1", text="   ")

    def test_invalid_account_rejected(self, repo):
        rs, _ = repo
        with pytest.raises(ValueError):
            rs.push_memory_entry(account="../../etc/passwd", text="x")


class TestContextBundleAndArchiving:
    def test_get_context_bundle(self, repo):
        rs, repo_root = repo
        (repo_root / "team-context.md").write_text("# Project Context\nRules here.", encoding="utf-8")
        rs.push_memory_entry(account="user1", text="active memory note")
        rs.push_live_status(account="user2", current_task_id=None, note="idle")

        task = rs.create_task(spec="active task for user1", kind="text", created_by="user1")
        rs.claim_task(task_id=task["id"], account="user1")

        bundle = rs.get_context_bundle(account="user1")
        assert bundle["account"] == "user1"
        assert "Rules here." in bundle["team_context"]
        assert len(bundle["recent_memory"]) >= 1
        assert len(bundle["my_tasks"]) == 1
        assert bundle["my_tasks"][0]["id"] == task["id"]
        assert any(w["account"] == "user2" for w in bundle["active_workers"])

    def test_archive_memory(self, repo):
        rs, _ = repo
        rs.push_memory_entry(account="user1", text="old note")
        time.sleep(1.1)
        now_cutoff = rs._now_iso()
        time.sleep(1.1)
        rs.push_memory_entry(account="user1", text="new note")

        # Dry run preview
        preview = rs.archive_memory(before=now_cutoff, dry_run=True)
        assert preview["archived_count"] == 1
        assert preview["dry_run"] is True
        assert len(rs.read_team_memory(limit=10)["entries"]) == 2

        # Actual archive
        done = rs.archive_memory(before=now_cutoff, dry_run=False)
        assert done["archived_count"] == 1
        assert done["dry_run"] is False

        # Active memory now only contains the new note
        active = rs.read_team_memory(limit=10)["entries"]
        assert len(active) == 1
        assert active[0]["text"] == "new note"


class TestTeamContext:
    def test_read_team_context_missing(self, repo):
        rs, repo_root = repo
        ctx_file = repo_root / "team-context.md"
        if ctx_file.exists():
            ctx_file.unlink()
        res = rs.read_team_context()
        assert res == {"exists": False, "content": ""}

    def test_read_team_context_present(self, repo):
        rs, repo_root = repo
        ctx_file = repo_root / "team-context.md"
        ctx_file.write_text("# Project Context\nStanding rules.", encoding="utf-8")
        res = rs.read_team_context()
        assert res["exists"] is True
        assert res["content"] == "# Project Context\nStanding rules."


class TestInputValidation:
    def test_invalid_account_name_rejected(self, repo):
        rs, _ = repo
        task = rs.create_task(spec="x", kind="text", created_by="user1")
        with pytest.raises(ValueError):
            rs.claim_task(task_id=task["id"], account="../../etc/passwd")

    def test_invalid_task_id_rejected(self, repo):
        rs, _ = repo
        with pytest.raises(ValueError):
            rs.claim_task(task_id="../../etc/passwd", account="user1")

    def test_code_task_requires_branch_name_on_claim(self, repo):
        rs, _ = repo
        task = rs.create_task(spec="code task", kind="code", created_by="user1")
        with pytest.raises(ValueError):
            rs.claim_task(task_id=task["id"], account="user1")  # no branch_name

    def test_unknown_parent_id_rejected(self, repo):
        rs, _ = repo
        with pytest.raises(ValueError):
            rs.create_task(spec="x", kind="text", created_by="user1", parent_id="task_9999-01-01_999")


class TestJobProductionLifecycle:
    def test_create_and_list_jobs(self, repo):
        rs, _ = repo
        job = rs.create_job(
            sku="100_product_descriptions",
            client="Test Client",
            input_uri="data/input.csv",
            quality_rules=["No hallucinations", "Length <= 150"],
            created_by="user1"
        )
        assert job["id"].startswith("job_")
        assert job["sku"] == "100_product_descriptions"
        assert job["status"] == "intake"
        
        all_jobs = rs.list_jobs()
        assert len(all_jobs) >= 1
        assert any(j["id"] == job["id"] for j in all_jobs)

    def test_submit_qa_review_lifecycle(self, repo):
        rs, _ = repo
        task = rs.create_task(spec="Draft product copy", kind="text", created_by="user1")
        rs.claim_task(task_id=task["id"], account="user2")
        rs.submit_checkpoint(task_id=task["id"], account="user2", summary="Draft finished", result_text="High quality copy")
        
        # Test QA pass
        review = rs.submit_qa_review(
            task_id=task["id"],
            reviewer_account="user6",
            verdict="pass",
            checks_passed={"no_hallucinations": True, "length_ok": True}
        )
        assert review["verdict"] == "pass"
        
        # Verify task is marked merged
        tasks = rs.list_tasks(status="merged")
        assert any(t["id"] == task["id"] for t in tasks)