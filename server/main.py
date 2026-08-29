from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from server.core.config import settings
from server.core.database import init_db
from server.api.routes_jobs import router as jobs_router
from server.api.routes_tasks import router as tasks_router
from server.api.routes_workers import router as workers_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_db()
    print(f"[{settings.PROJECT_NAME}] Database initialized at {settings.DATABASE_PATH}")
    
    # Start supervisor background worker if needed
    supervisor_task = asyncio.create_task(run_supervisor_loop())
    
    yield
    
    # Shutdown
    supervisor_task.cancel()
    try:
        await supervisor_task
    except asyncio.CancelledError:
        pass

async def run_supervisor_loop():
    """Background supervisor monitoring heartbeats and dead workers."""
    while True:
        try:
            await asyncio.sleep(settings.SUPERVISOR_INTERVAL_SECONDS)
            # Supervisor logic imported lazily to avoid circular deps
            from server.core.supervisor import run_supervisor_cycle
            await run_supervisor_cycle()
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

@app.get("/health")
async def health_check():
    return {"status": "ok", "version": settings.VERSION}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server.main:app", host="0.0.0.0", port=8000, reload=True)
