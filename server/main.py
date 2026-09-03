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
    """Background supervisor monitoring heartbeats, dead workers, and auto-scheduling pending tasks."""
    while True:
        try:
            await asyncio.sleep(settings.SUPERVISOR_INTERVAL_SECONDS)
            from server.core.supervisor import run_supervisor_cycle
            from server.core.scheduler import scheduler
            
            # 1. Run supervisor watchdog cycle (reclaim expired/offline tasks)
            await run_supervisor_cycle()
            
            # 2. Auto-schedule pending tasks to idle workers
            db = await get_db_conn()
            try:
                await scheduler.schedule_next_pending_tasks(db, limit=10)
            finally:
                await db.close()
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"[Supervisor Error] {e}")

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

# Mount the Streamable HTTP / SSE MCP Server directly into FastAPI
app.mount(settings.MCP_PATH, mcp_server.sse_app())

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
