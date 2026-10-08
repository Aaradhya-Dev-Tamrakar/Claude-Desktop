#!/usr/bin/env python3
"""
CI/CD Self-Healing, Schema Integrity & Secret Scan Engine
Part of Claude-Desktop Orchestration Ecosystem

Responsibilities:
1. Audit and heal orchestrator-state/ entities (tasks, checkpoints, reviews, scratchpads).
2. Scan codebase and git diff for accidental credentials or secret patterns.
3. Validate repository invariants (.gitignore tracking, AGENTS.md, zero-CDP contract).
4. Dynamically publish audit summary to GitHub Actions Step Summary ($GITHUB_STEP_SUMMARY).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
STATE_DIR = REPO_ROOT / "orchestrator-state"

SECRET_PATTERNS = [
    (r"AKIA" + r"[0-9A-Z]{16}", "AWS Access Key"),
    (r"sk-" + r"[a-zA-Z0-9]{20,}", "OpenAI API Key"),
    (r"sk-ant-" + r"[a-zA-Z0-9\-]{20,}", "Anthropic API Key"),
    (r"ghp_" + r"[a-zA-Z0-9]{36}", "GitHub Personal Access Token"),
    (r"github_pat_" + r"[a-zA-Z0-9_]{20,}", "GitHub Fine-Grained Token"),
    (r"AIza" + r"[0-9A-Za-z\-_]{35}", "Google API Key"),
    (r"xox" + r"[baprs]-[0-9a-zA-Z\-]{10,}", "Slack Token"),
    (r"-----BEGIN " + r"(?:RSA|EC|OPENSSH|PGP|DSA)? ?PRIVATE " + r"KEY-----", "Private Key Header"),
    (r"(?i)(?:api[_-]?key|sec" + r"ret|pass" + r"word|to" + r"ken|pass" + r"wd)\s*[:=]\s*['\"][^'\"\s]{8,}['\"]", "Hardcoded Credential Assignment"),
]

IGNORED_SECRET_FILES = {
    "scripts/ci_self_healing.py",
    "sync.ps1",
    "sync.bat",
    "tests/test_remote_mcp.py",
    "tests/test_auth_enforcement.py",
    "tests/test_security_config.py",
    "tests/orchestrator_mcp_test.py",
}


def ensure_state_directories() -> List[str]:
    """Ensure all required orchestrator-state subdirectories exist with .gitkeep."""
    subdirs = ["tasks", "checkpoints", "qa-reviews", "live-status", "scratchpads", "memory"]
    healed: List[str] = []
    for sub in subdirs:
        folder = STATE_DIR / sub
        if not folder.exists():
            folder.mkdir(parents=True, exist_ok=True)
            healed.append(f"Created missing directory: orchestrator-state/{sub}")
        gitkeep = folder / ".gitkeep"
        if not gitkeep.exists() and not any(folder.iterdir()):
            gitkeep.touch()
            healed.append(f"Created .gitkeep in orchestrator-state/{sub}")
    return healed


def audit_and_heal_json_files(auto_heal: bool = True) -> Tuple[int, int, List[str], List[str]]:
    """
    Validate and optionally normalize JSON formatting in orchestrator-state.
    Returns (scanned_count, healed_count, errors, log_entries).
    """
    scanned = 0
    healed = 0
    errors: List[str] = []
    logs: List[str] = []

    if not STATE_DIR.exists():
        return scanned, healed, errors, logs

    for path in STATE_DIR.rglob("*.json"):
        scanned += 1
        try:
            content = path.read_text(encoding="utf-8")
            data = json.loads(content)

            if auto_heal:
                normalized = json.dumps(data, indent=2, sort_keys=True) + "\n"
                if content != normalized:
                    path.write_text(normalized, encoding="utf-8")
                    healed += 1
                    logs.append(f"Healed JSON formatting: {path.relative_to(REPO_ROOT)}")
        except Exception as e:
            errors.append(f"Malformed JSON in {path.relative_to(REPO_ROOT)}: {e}")

    return scanned, healed, errors, logs


def audit_scratchpads(auto_heal: bool = True) -> Tuple[int, int, List[str]]:
    """Audit and ensure default shared scratchpad exists with valid structure."""
    scratchpad_dir = STATE_DIR / "scratchpads"
    shared = scratchpad_dir / "shared_scratchpad.md"
    healed = 0
    logs: List[str] = []

    if not shared.exists() and auto_heal:
        default_content = (
            "# 📋 Shared Multi-Account Scratchpad\n\n"
            "> **Scratchpad ID:** `shared`  \n"
            "> **Initialized By:** `system`  \n"
            "> **Created At:** `2026-10-08T00:00:00Z`  \n"
            "> **Mode:** Fast Multi Claude Desktop Collaboration\n\n"
            "---\n\n"
            "## 1. Specification & Objectives\n\n"
            "Central scratchpad for decoupled multi-account coordination.\n\n"
            "---\n\n"
            "## 2. Shared Work Log & Handoffs\n\n"
            "*(Instances append notes, findings, decisions, and handoff summaries below)*\n"
        )
        scratchpad_dir.mkdir(parents=True, exist_ok=True)
        shared.write_text(default_content, encoding="utf-8")
        healed += 1
        logs.append("Created missing default shared scratchpad: orchestrator-state/scratchpads/shared_scratchpad.md")

    return 1 if shared.exists() else 0, healed, logs


def scan_for_secrets() -> List[str]:
    """Scan tracked and staged repository files for accidental credentials."""
    findings: List[str] = []
    
    # Check text files up to 2MB
    text_extensions = {".py", ".json", ".md", ".yml", ".yaml", ".ps1", ".bat", ".sh", ".txt"}
    
    for path in REPO_ROOT.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(REPO_ROOT).as_posix()
        
        # Skip git directory, venv, and known pattern definitions
        if rel.startswith(".git/") or rel.startswith(".venv/") or rel.startswith("node_modules/"):
            continue
        if rel in IGNORED_SECRET_FILES or path.suffix not in text_extensions:
            continue
        if path.stat().st_size > 2 * 1024 * 1024:
            continue

        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
            for line_no, line in enumerate(content.splitlines(), start=1):
                # Skip commented out example patterns or test fixtures
                if "AKIAIOSFODNN7EXAMPLE" in line or "dummy_token" in line or "test_key" in line:
                    continue
                for pattern, desc in SECRET_PATTERNS:
                    if re.search(pattern, line):
                        # Filter out false positives in comments or type annotations
                        if "pattern" in line.lower() or "regex" in line.lower():
                            continue
                        findings.append(f"{rel}:{line_no} [{desc}] -> {line.strip()[:60]}...")
        except Exception:
            continue

    return findings


def verify_repo_invariants() -> List[str]:
    """Verify core repository invariants."""
    violations: List[str] = []

    # Invariant 1: AGENTS.md exists and is substantive
    agents_md = REPO_ROOT / "AGENTS.md"
    if not agents_md.exists() or agents_md.stat().st_size < 500:
        violations.append("Invariant Violation: AGENTS.md is missing or truncated.")

    # Invariant 2: GEMINI.md exists and points to AGENTS.md
    gemini_md = REPO_ROOT / "GEMINI.md"
    if not gemini_md.exists():
        violations.append("Invariant Violation: GEMINI.md is missing.")
    elif "AGENTS.md" not in gemini_md.read_text(encoding="utf-8"):
        violations.append("Invariant Violation: GEMINI.md must reference AGENTS.md.")

    # Invariant 3: .gitignore does not ignore GEMINI.md
    gitignore = REPO_ROOT / ".gitignore"
    if gitignore.exists():
        content = gitignore.read_text(encoding="utf-8")
        for line in content.splitlines():
            line = line.strip()
            if line == "GEMINI.md" or line == "/GEMINI.md":
                violations.append("Invariant Violation: .gitignore is actively ignoring GEMINI.md.")

    return violations


def write_step_summary(
    state_scanned: int,
    state_healed: int,
    state_errors: List[str],
    secret_findings: List[str],
    invariant_violations: List[str],
    heal_logs: List[str],
) -> None:
    """Publish a dynamic Markdown summary to GitHub Actions Step Summary."""
    summary_path = os.getenv("GITHUB_STEP_SUMMARY")
    if not summary_path:
        return

    is_clean = not state_errors and not secret_findings and not invariant_violations
    status_badge = "✅ **ALL AUDIT GATES PASSED**" if is_clean else "❌ **AUDIT GATES FAILED**"

    lines = [
        f"## 🛡️ CI/CD Self-Healing & Integrity Audit",
        f"",
        f"{status_badge}",
        f"",
        f"| Metric / Gate | Result | Status |",
        f"| :--- | :--- | :--- |",
        f"| **Orchestrator State JSONs** | `{state_scanned}` scanned, `{state_healed}` auto-healed | {'✅ Pass' if not state_errors else '❌ Fail'} |",
        f"| **Secret Scan (OWASP / Leak)** | `{len(secret_findings)}` findings | {'✅ Clean' if not secret_findings else '❌ Detected'} |",
        f"| **Repository Invariants** | `{len(invariant_violations)}` violations | {'✅ Verified' if not invariant_violations else '❌ Violated'} |",
        f"",
    ]

    if heal_logs:
        lines.append("### 🩹 Self-Healing Action Log")
        for entry in heal_logs:
            lines.append(f"- {entry}")
        lines.append("")

    if state_errors:
        lines.append("### ⚠️ State Validation Errors")
        for err in state_errors:
            lines.append(f"- `{err}`")
        lines.append("")

    if secret_findings:
        lines.append("### 🚨 Credential Findings")
        for item in secret_findings:
            lines.append(f"- `{item}`")
        lines.append("")

    if invariant_violations:
        lines.append("### 📐 Invariant Violations")
        for inv in invariant_violations:
            lines.append(f"- `{inv}`")
        lines.append("")

    with open(summary_path, "a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="CI/CD Self-Healing, Schema Integrity & Secret Scan Engine")
    parser.add_argument("--heal", action="store_true", default=True, help="Auto-heal minor discrepancies")
    parser.add_argument("--check-only", action="store_true", help="Report only without modifying files")
    args = parser.parse_args()

    auto_heal = not args.check_only and args.heal

    print("======================================================================")
    print("  CI/CD SELF-HEALING & INTEGRITY AUDIT ENGINE")
    print(f"  Target: {REPO_ROOT}")
    print(f"  Mode: {'Self-Healing (--heal)' if auto_heal else 'Audit Only (--check-only)'}")
    print("======================================================================")

    # 1. State Directories & JSON files
    dir_logs = ensure_state_directories() if auto_heal else []
    scanned_json, healed_json, json_errors, json_logs = audit_and_heal_json_files(auto_heal)
    scratch_scanned, scratch_healed, scratch_logs = audit_scratchpads(auto_heal)

    all_heal_logs = dir_logs + json_logs + scratch_logs

    # 2. Secret Scan
    secret_findings = scan_for_secrets()

    # 3. Repository Invariants
    invariant_violations = verify_repo_invariants()

    # 4. Summary Output
    print(f"\n[Audit Summary]")
    print(f"  - Orchestrator State Files Scanned : {scanned_json}")
    print(f"  - Files Auto-Healed / Normalized   : {healed_json + scratch_healed + len(dir_logs)}")
    print(f"  - JSON Parse Errors                : {len(json_errors)}")
    print(f"  - Secret Leak Findings             : {len(secret_findings)}")
    print(f"  - Invariant Violations             : {len(invariant_violations)}")

    if all_heal_logs:
        print(f"\n[Self-Healing Actions Applied]")
        for log in all_heal_logs:
            print(f"  [+] {log}")

    if json_errors:
        print(f"\n[JSON Errors]")
        for err in json_errors:
            print(f"  [-] {err}")

    if secret_findings:
        print(f"\n[Secret Findings]")
        for item in secret_findings:
            print(f"  [!] {item}")

    if invariant_violations:
        print(f"\n[Invariant Violations]")
        for inv in invariant_violations:
            print(f"  [!] {inv}")

    # 5. Write to GITHUB_STEP_SUMMARY
    write_step_summary(
        state_scanned=scanned_json,
        state_healed=healed_json + scratch_healed + len(dir_logs),
        state_errors=json_errors,
        secret_findings=secret_findings,
        invariant_violations=invariant_violations,
        heal_logs=all_heal_logs,
    )

    is_clean = not json_errors and not secret_findings and not invariant_violations
    if is_clean:
        print("\n======================================================================")
        print("  ALL CI/CD AUDIT GATES PASSED (100% HEALTHY)")
        print("======================================================================\n")
        return 0
    else:
        print("\n======================================================================")
        print("  CI/CD AUDIT DETECTED VIOLATIONS")
        print("======================================================================\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
