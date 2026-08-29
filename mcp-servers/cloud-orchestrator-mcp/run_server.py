#!/usr/bin/env python3
"""cloud-orchestrator-mcp: Claude Desktop MCP bridge to the FastAPI cloud orchestrator.

This server exposes a small, chat-friendly set of tools for creating jobs,
listing/routing tasks, inspecting workers, and checking the health of the
coordinator backend. It does not own the database or task state itself; it
simply proxies to the FastAPI service in server/.

Invoked via team-mcp.json:
    "cloud-orchestrator-mcp": {
      "command": "python",
      "args": ["{{REPO_ROOT}}\\mcp-servers\\cloud-orchestrator-mcp\\run_server.py"],
      "env": {
        "ORCHESTRATOR_API_URL": "http://localhost:8000/api/v1"
      }
    }
"""

from __future__ import annotations

import os
from typing import Any, cast

import httpx
from mcp.server.mcpserver import MCPServer

API_URL = os.getenv("ORCHESTRATOR_API_URL", "http://localhost:8000/api/v1").rstrip("/")

srv = MCPServer(
    name="cloud-orchestrator-mcp",
    description=(
        "Claude Desktop MCP bridge for the cloud orchestration backend. "
        "Provides job, task, worker, and health queries for the FastAPI "
        "server located under server/."
    ),
)


def _request_raw(method: str, path: str, *, params: dict[str, Any] | None = None, json_body: dict[str, Any] | None = None) -> Any:
    url = f"{API_URL}{path}"
    response = httpx.request(
        method=method,
        url=url,
        params=params,
        json=json_body,
        timeout=30.0,
    )

    try:
        payload = response.json()
    except ValueError:
        payload = {"raw": response.text}

    if response.status_code >= 400:
        detail = payload.get("detail") if isinstance(payload, dict) else payload
        raise RuntimeError(f"Orchestrator API request failed ({response.status_code}): {detail}")

    return payload


def _request_json(method: str, path: str, *, params: dict[str, Any] | None = None, json_body: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = _request_raw(method, path, params=params, json_body=json_body)
    if not isinstance(payload, dict):
        raise TypeError(f"Expected a JSON object from {path!r}, got {type(payload).__name__}")
    return payload


def _request_list(method: str, path: str, *, params: dict[str, Any] | None = None, json_body: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    payload = _request_raw(method, path, params=params, json_body=json_body)
    if not isinstance(payload, list):
        raise TypeError(f"Expected a JSON list from {path!r}, got {type(payload).__name__}")
    return cast(list[dict[str, Any]], payload)


@srv.tool(
    name="submit_job_from_template",
    description=(
        "Submit a job to the backend using one of the known SKU templates from "
        "sku-templates/; this routes through the FastAPI /jobs endpoint."
    ),
)
def submit_job_from_template(
    template_name: str,
    parameters: dict[str, Any] | None = None,
    client: str = "claude-desktop",
    input_uri: str = "manual",
) -> dict[str, Any]:
    params = parameters or {}

    template_to_pipeline = {
        "seo_content_batch": ["research", "draft", "seo_optimize", "qa", "format"],
        "30_day_social_package": ["research", "draft", "publish", "qa", "format"],
        "100_product_descriptions": ["research", "draft", "qa", "format"],
        "document_processing_50": ["ingest", "extract", "synthesize", "qa"],
        "default": ["research", "draft", "qa", "format"],
    }

    payload = {
        "sku": template_name,
        "client": client,
        "input_uri": input_uri,
        "pipeline": params.get("pipeline", template_to_pipeline.get(template_name, template_to_pipeline["default"])),
        "quality_rules": params.get("quality_rules", []),
    }

    if "deadline" in params and params["deadline"]:
        payload["deadline"] = params["deadline"]

    return _request_json("POST", "/jobs", json_body=payload)


@srv.tool(
    name="list_jobs",
    description="List jobs in the orchestration system, optionally filtered by status.",
)
def list_jobs(status: str | None = None) -> list[dict[str, Any]]:
    return _request_list("GET", "/jobs", params={"status": status} if status else {})


@srv.tool(
    name="get_job",
    description="Fetch a single job by ID.",
)
def get_job(job_id: str) -> dict[str, Any]:
    return _request_json("GET", f"/jobs/{job_id}")


@srv.tool(
    name="list_tasks",
    description="List tasks with optional filters such as status, stage, or job_id.",
)
def list_tasks(
    status: str | None = None,
    stage: str | None = None,
    job_id: str | None = None,
    parent_id: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    params = {k: v for k, v in {
        "status": status,
        "stage": stage,
        "job_id": job_id,
        "parent_id": parent_id,
        "limit": limit,
    }.items() if v is not None}
    return _request_list("GET", "/tasks", params=params)


@srv.tool(
    name="get_task",
    description="Fetch one task by ID.",
)
def get_task(task_id: str) -> dict[str, Any]:
    return _request_json("GET", f"/tasks/{task_id}")


@srv.tool(
    name="claim_task",
    description="Claim a pending or expired task for a worker.",
)
def claim_task(task_id: str, worker_id: str, lease_seconds: int = 300, branch_name: str | None = None) -> dict[str, Any]:
    payload = {"worker_id": worker_id, "lease_seconds": lease_seconds}
    if branch_name is not None:
        payload["branch_name"] = branch_name
    return _request_json("POST", f"/tasks/{task_id}/claim", json_body=payload)


@srv.tool(
    name="release_task",
    description="Release a task back to the pending queue.",
)
def release_task(task_id: str, worker_id: str, claim_token: str | None = None) -> dict[str, Any]:
    payload = {"worker_id": worker_id}
    if claim_token is not None:
        payload["claim_token"] = claim_token
    return _request_json("POST", f"/tasks/{task_id}/release", json_body=payload)


@srv.tool(
    name="block_task",
    description="Mark a task as blocked with a reason.",
)
def block_task(task_id: str, worker_id: str, reason: str) -> dict[str, Any]:
    return _request_json("POST", f"/tasks/{task_id}/block", json_body={"worker_id": worker_id, "reason": reason})


@srv.tool(
    name="list_workers",
    description="List registered worker nodes and their status/capabilities.",
)
def list_workers(status: str | None = None) -> list[dict[str, Any]]:
    return _request_list("GET", "/workers", params={"status": status} if status else {})


@srv.tool(
    name="get_worker",
    description="Get a single worker by ID.",
)
def get_worker(worker_id: str) -> dict[str, Any]:
    return _request_json("GET", f"/workers/{worker_id}")


@srv.tool(
    name="submit_task_checkpoint",
    description="Submit a checkpoint/result for a task.",
)
def submit_task_checkpoint(
    task_id: str,
    submitted_by: str,
    summary: str,
    result_text: str | None = None,
    job_id: str | None = None,
    kind: str = "text",
    branch_name: str | None = None,
    commit_sha: str | None = None,
    claim_token: str | None = None,
) -> dict[str, Any]:
    payload = {
        "task_id": task_id,
        "submitted_by": submitted_by,
        "summary": summary,
        "kind": kind,
    }
    if result_text is not None:
        payload["result_text"] = result_text
    if job_id is not None:
        payload["job_id"] = job_id
    if branch_name is not None:
        payload["branch_name"] = branch_name
    if commit_sha is not None:
        payload["commit_sha"] = commit_sha
    if claim_token is not None:
        payload["claim_token"] = claim_token

    return _request_json("POST", f"/tasks/{task_id}/checkpoint", json_body=payload)


@srv.tool(
    name="get_system_health",
    description="Return backend health plus a quick status summary for jobs, tasks, and workers.",
)
def get_system_health() -> dict[str, Any]:
    health = _request_json("GET", "/health")
    jobs = _request_list("GET", "/jobs")
    tasks = _request_list("GET", "/tasks", params={"limit": "200"})
    workers = _request_list("GET", "/workers")

    status_summary = {
        "job_count": len(jobs),
        "task_count": len(tasks),
        "worker_count": len(workers),
        "pending_tasks": sum(1 for t in tasks if isinstance(t, dict) and t.get("status") == "pending"),
        "claimed_tasks": sum(1 for t in tasks if isinstance(t, dict) and t.get("status") == "claimed"),
        "done_tasks": sum(1 for t in tasks if isinstance(t, dict) and t.get("status") in {"done", "merged"}),
    }

    return {"health": health, "summary": status_summary}


if __name__ == "__main__":
    # Exits to stdio, which is what Claude Desktop expects from an MCP server.
    srv.run()
