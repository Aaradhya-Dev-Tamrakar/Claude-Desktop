from __future__ import annotations

import os
from pathlib import Path
from pydantic import BaseModel

SERVER_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = SERVER_ROOT.parent

class Settings(BaseModel):
    PROJECT_NAME: str = "Cloud AI Production Orchestrator"
    VERSION: str = "2.0.0"
    API_V1_STR: str = "/api/v1"
    
    # Storage
    DATA_DIR: Path = SERVER_ROOT / "data"
    DATABASE_PATH: Path = SERVER_ROOT / "data" / "production.db"
    SCHEMA_PATH: Path = SERVER_ROOT / "database" / "schema.sql"
    SKU_TEMPLATES_DIR: Path = REPO_ROOT / "sku-templates"
    TEAM_CONTEXT_PATH: Path = REPO_ROOT / "team-context.md"
    
    # Security
    API_AUTH_KEY: str = os.getenv("API_AUTH_KEY", "dev-secret-key-change-in-prod")
    
    # Scheduler & Supervisor Settings
    HEARTBEAT_TIMEOUT_SECONDS: int = 120
    SUPERVISOR_INTERVAL_SECONDS: int = 30
    SCHEDULER_INTERVAL_SECONDS: int = 15
    DEFAULT_COOLDOWN_MINUTES: int = 300  # 5 hours
    MCP_PATH: str = "/mcp"

settings = Settings()
settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
