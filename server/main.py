from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from time import perf_counter
from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware

from server.core.config import settings, validate_security_settings
from server.core.database import init_db, get_db_conn
from server.core.observability import log_request, metrics_text, record_request, request_id
from server.api.routes_jobs import router as jobs_router
from server.api.routes_tasks import router as tasks_router
from server.api.routes_workers import router as workers_router
from server.api.routes_memory import router as memory_router
from server.mcp_remote import mcp_server

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    validate_security_settings()
    await init_db()
    print(f"[{settings.PROJECT_NAME}] Database initialized at {settings.DATABASE_PATH}")
    
    # Start supervisor background worker
    supervisor_task = asyncio.create_task(run_supervisor_loop())
    
    yield
    
    # Shutdown
    supervisor_task.cancel()
    try:
        await supervisor_task
    except asyncio.CancelledError:
        pass

async def run_supervisor_loop():
    """Background supervisor monitoring heartbeats, dead workers, and reclaiming expired leases."""
    while True:
        try:
            await asyncio.sleep(settings.SUPERVISOR_INTERVAL_SECONDS)
            from server.core.supervisor import run_supervisor_cycle

            # 1. Run supervisor watchdog cycle (reclaim expired/offline tasks)
            await run_supervisor_cycle()

            # NOTE (INV-WSR-002 §1.1): Auto-scheduler PUSH assignment is disabled in favor of
            # Closed-Loop Pull-with-Scheduler-Arbitration (POST /tasks/acquire).
            # This prevents dual-mode concurrency where the scheduler claims tasks
            # that pull workers never ingest, generating orphaned leases.
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"[Supervisor Error] {e}")

class MCPAuthMiddleware:
    """Enforce API key authentication on the mounted MCP SSE application."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            expected_key = settings.API_AUTH_KEY
            if expected_key:
                headers = dict(scope.get("headers", []))
                x_api_key = headers.get(b"x-api-key", b"").decode("utf-8", errors="ignore")
                auth_header = headers.get(b"authorization", b"").decode("utf-8", errors="ignore")

                bearer_token = ""
                if auth_header.lower().startswith("bearer "):
                    bearer_token = auth_header[7:].strip()

                provided_token = x_api_key or bearer_token
                if not provided_token or provided_token != expected_key:
                    response_body = b'{"detail": "Invalid or missing authentication credentials"}'
                    await send({
                        "type": "http.response.start",
                        "status": 401,
                        "headers": [
                            (b"content-type", b"application/json"),
                            (b"www-authenticate", b"Bearer"),
                            (b"content-length", str(len(response_body)).encode("utf-8")),
                        ],
                    })
                    await send({
                        "type": "http.response.body",
                        "body": response_body,
                    })
                    return

        await self.app(scope, receive, send)

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def observe_http_requests(request: Request, call_next):
    correlation_id = request_id(request.headers.get("X-Request-ID"))
    started = perf_counter()
    response_status = status.HTTP_500_INTERNAL_SERVER_ERROR
    try:
        response = await call_next(request)
        response_status = response.status_code
        return response
    finally:
        duration = perf_counter() - started
        record_request(request.method, request.url.path, response_status, duration)
        log_request(correlation_id, request.method, request.url.path, response_status, duration)
        if "response" in locals():
            response.headers["X-Request-ID"] = correlation_id

app.include_router(jobs_router, prefix=settings.API_V1_STR)
app.include_router(tasks_router, prefix=settings.API_V1_STR)
app.include_router(workers_router, prefix=settings.API_V1_STR)
app.include_router(memory_router, prefix=settings.API_V1_STR)

# Mount the Streamable HTTP / SSE MCP Server directly into FastAPI with auth enforcement
app.mount(settings.MCP_PATH, MCPAuthMiddleware(mcp_server.sse_app()))

@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "version": settings.VERSION,
        "mcp_endpoint": settings.MCP_PATH,
    }

@app.get("/health/live")
async def liveness_check():
    return {"status": "ok", "version": settings.VERSION}

@app.get("/health/ready")
async def readiness_check():
    db = None
    try:
        db = await get_db_conn()
        await db.execute("SELECT 1")
        return {"status": "ready", "database": "ok", "version": settings.VERSION}
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Database is not ready") from exc
    finally:
        if db:
            await db.close()

@app.get("/metrics")
async def metrics():
    return Response(content=metrics_text(), media_type="text/plain; version=0.0.4")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server.main:app", host="0.0.0.0", port=8000, reload=True)
