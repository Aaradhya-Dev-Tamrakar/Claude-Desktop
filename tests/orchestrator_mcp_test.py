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
                "create_task",
                "decompose_task",
                "claim_task",
                "release_task",
                "mark_blocked",
                "unblock_task",
                "push_live_status",
                "read_all_live_status",
                "submit_checkpoint",
                "list_tasks",
                "merge_results",
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