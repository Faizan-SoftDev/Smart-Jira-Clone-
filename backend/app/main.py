"""FastAPI application entry point."""

from contextlib import asynccontextmanager
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.infrastructure.api.v1.tasks import router as tasks_router
from app.infrastructure.api.v1.auth import router as auth_router
from app.infrastructure.api.v1.projects import router as projects_router
from app.infrastructure.api.ws.kanban_sync import kanban_router, kanban_sync_manager
from app.infrastructure.database.models import Base
from app.infrastructure.database.session import engine


def _cors_origins() -> list[str]:
    """Read explicit frontend origins, retaining local development defaults."""
    configured = os.getenv("CORS_ORIGINS", "")
    if configured:
        return [origin.strip().rstrip("/") for origin in configured.split(",") if origin.strip()]
    return ["http://localhost:5173", "http://127.0.0.1:5173"]


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Create database tables for the local development environment."""
    if os.getenv("CREATE_DATABASE_SCHEMA", "false").lower() == "true":
        Base.metadata.create_all(bind=engine)
    await kanban_sync_manager.start()
    try:
        yield
    finally:
        await kanban_sync_manager.stop()


app = FastAPI(title="Smart Jira Clone API", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(tasks_router, prefix="/api/v1")
app.include_router(auth_router, prefix="/api/v1")
app.include_router(projects_router, prefix="/api/v1")
app.include_router(kanban_router)


@app.get("/health")
def health_check() -> dict[str, str]:
    """Return a lightweight health response."""
    return {"status": "ok"}
