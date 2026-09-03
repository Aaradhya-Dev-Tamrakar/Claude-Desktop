from __future__ import annotations

import json
import logging
from collections import defaultdict
from time import perf_counter
from typing import Any
from uuid import uuid4

logger = logging.getLogger("orchestrator.http")
_request_counts: dict[tuple[str, str], int] = defaultdict(int)
_request_durations: dict[str, float] = defaultdict(float)


def request_id(value: str | None) -> str:
    return value or uuid4().hex


def record_request(method: str, path: str, status_code: int, duration_seconds: float) -> None:
    _request_counts[(method, path, str(status_code))] += 1
    _request_durations[path] += duration_seconds


def log_request(request_id_value: str, method: str, path: str, status_code: int, duration_seconds: float) -> None:
    logger.info(json.dumps({
        "event": "http_request",
        "request_id": request_id_value,
        "method": method,
        "path": path,
        "status_code": status_code,
        "duration_ms": round(duration_seconds * 1000, 2),
    }, separators=(",", ":")))


def metrics_text() -> str:
    lines = [
        "# HELP orchestrator_http_requests_total Total HTTP requests by method, path, and status.",
        "# TYPE orchestrator_http_requests_total counter",
    ]
    for (method, path, status_code), count in sorted(_request_counts.items()):
        lines.append(
            f'orchestrator_http_requests_total{{method="{method}",path="{path}",status="{status_code}"}} {count}'
        )

    lines.extend([
        "# HELP orchestrator_http_request_duration_seconds_sum Total HTTP request duration by path.",
        "# TYPE orchestrator_http_request_duration_seconds_sum counter",
    ])
    for path, duration in sorted(_request_durations.items()):
        lines.append(f'orchestrator_http_request_duration_seconds_sum{{path="{path}"}} {duration:.6f}')
    return "\n".join(lines) + "\n"
