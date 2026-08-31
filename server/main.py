from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from server.core.config import settings
from server.core.database import init_db, get_db_conn
from server.api.routes_jobs import router as jobs_router
from server.api.routes_tasks import router as tasks_router
from server.api.routes_workers import router as workers_router
from server.api.routes_memory import router as memory_router
from server.mcp_remote import mcp_server

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
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
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server.main:app", host="0.0.0.0", port=8000, reload=True)
