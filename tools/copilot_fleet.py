#!/usr/bin/env python3
"""
Copilot Fleet Controller CLI:
Discovers pooled accounts from .env.fleet, provides live status auditing,
credit allocation tracking, and concurrent task dispatch across isolated workers.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path
from typing import Any
import httpx

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from client.adapters.copilot_cli_adapter import CopilotCLIAdapter


def load_env_fleet(env_path: Path | None = None) -> dict[str, str]:
    """Parses .env.fleet file into key-value pairs."""
    path = env_path or (PROJECT_ROOT / ".env.fleet")
    if not path.exists():
        # Fallback to .env.fleet in parent or current working directory
        cwd_fleet = Path(".env.fleet")
        if cwd_fleet.exists():
            path = cwd_fleet
        else:
            return {}

    values = {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip('"').strip("'")
                values[k] = v
                os.environ[k] = v
    return values


def discover_accounts(env_vars: dict[str, str]) -> list[dict[str, Any]]:
    """Discovers configured accounts from environment variables."""
    accounts = []
    i = 1
    while True:
        token_key = f"COPILOT_ACCOUNT_{i}_TOKEN"
        name_key = f"COPILOT_ACCOUNT_{i}_NAME"
        credits_key = f"COPILOT_ACCOUNT_{i}_MONTHLY_CREDITS"

        token = env_vars.get(token_key, os.getenv(token_key, "")).strip()
        name = env_vars.get(name_key, os.getenv(name_key, f"account_{i}")).strip()
        credits_str = env_vars.get(credits_key, os.getenv(credits_key, "200")).strip()

        if not token and not name_key in env_vars and not name_key in os.environ:
            if i > 2:
                break

        monthly_credits = int(credits_str) if credits_str.isdigit() else 200
        has_token = bool(token and not token.startswith("github_pat_REPLACE"))

        accounts.append({
            "index": i,
            "worker_id": f"copilot-w{i}",
            "name": name,
            "token": token if has_token else "",
            "has_token": has_token,
            "monthly_credits": monthly_credits,
            "state_dir": Path.home() / ".copilot-workers" / f"worker_{i}_{name}",
        })
        i += 1

    return accounts


async def cmd_status(args: argparse.Namespace) -> None:
    """Displays fleet account topology, token readiness, and monthly credit headroom."""
    env_vars = load_env_fleet()
    accounts = discover_accounts(env_vars)

    print("\n" + "=" * 70)
    print(" GITHUB COPILOT MULTI-ACCOUNT CLI FLEET STATUS")
    print("=" * 70)

    total_credits = 0
    active_workers = 0

    async with httpx.AsyncClient(timeout=10.0) as client:
        for acc in accounts:
            status_str = "[NO TOKEN SET]"
            if acc["has_token"]:
                try:
                    resp = await client.get(
                        "https://api.github.com/user",
                        headers={
                            "Authorization": f"token {acc['token']}",
                            "Accept": "application/vnd.github.v3+json",
                            "User-Agent": "Fleet-Orchestrator",
                        },
                    )
                    if resp.status_code == 200:
                        gh_login = resp.json().get("login", "")
                        status_str = f"[VERIFIED: @{gh_login}]"
                    elif resp.status_code == 401:
                        status_str = "[INVALID / EXPIRED TOKEN (401)]"
                    else:
                        status_str = f"[API HTTP {resp.status_code}]"
                except Exception:
                    status_str = "[READY (Offline check)]"

            token_hint = f"{acc['token'][:14]}...{acc['token'][-4:]}" if acc["has_token"] else "(empty / placeholder)"
            print(f"\nWorker {acc['index']}: {acc['worker_id']} ({acc['name']})")
            print(f"  Status:       {status_str}")
            print(f"  Token:        {token_hint}")
            print(f"  Quota Pool:   {acc['monthly_credits']} AI credits/mo")
            print(f"  Session Home: {acc['state_dir']}")

            if acc["has_token"]:
                total_credits += acc["monthly_credits"]
                active_workers += 1

    print("\n" + "-" * 70)
    print(f"Active Ready Workers: {active_workers} / {len(accounts)}")
    print(f"Pooled Monthly Capacity: {total_credits} AI credits")
    print("=" * 70 + "\n")


async def cmd_canary(args: argparse.Namespace) -> None:
    """Executes concurrent non-interactive verification across all ready accounts."""
    env_vars = load_env_fleet()
    accounts = discover_accounts(env_vars)
    ready = [a for a in accounts if a["has_token"]]

    if not ready:
        print("[!] No ready accounts found with active tokens in .env.fleet.")
        print("    Please paste your Fine-Grained PATs into .env.fleet first.")
        return

    print(f"[*] Running concurrent canary tests across {len(ready)} accounts...")

    async def _test_worker(acc: dict[str, Any]) -> dict[str, Any]:
        adapter = CopilotCLIAdapter(
            worker_id=acc["worker_id"],
            nickname=acc["name"],
            github_token=acc["token"],
            copilot_home=acc["state_dir"],
            timeout=30.0,
            max_ai_credits=5,
        )
        res = await adapter.execute_task(
            task_id=f"canary_{acc['worker_id']}",
            spec="echo 'Fleet Canary Active'",
            stage="canary",
            context={},
        )
        return {"account": acc, "result": res}

    results = await asyncio.gather(*[_test_worker(a) for a in ready], return_exceptions=True)

    for r in results:
        if isinstance(r, Exception):
            print(f"[-] Exception: {r}")
        else:
            acc = r["account"]
            res = r["result"]
            if res.get("success"):
                print(f"[+] {acc['worker_id']} ({acc['name']}): PASS | Model: {res.get('model_used')} | Tokens: {res.get('tokens_used')}")
            else:
                print(f"[-] {acc['worker_id']} ({acc['name']}): FAIL | Error: {res.get('error')}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Copilot Multi-Account Fleet Controller")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("status", help="Show fleet account status and credit headroom")
    subparsers.add_parser("canary", help="Run concurrent canary ping across ready accounts")

    args = parser.parse_args()
    if args.command == "status":
        asyncio.run(cmd_status(args))
    elif args.command == "canary":
        asyncio.run(cmd_canary(args))


if __name__ == "__main__":
    main()
