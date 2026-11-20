"""Health check endpoint with database and pgvector verification."""

import logging

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import text

from app.config import get_settings
from app.db.session import engine

logger = logging.getLogger(__name__)
router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    database: str
    pgvector: bool
    claude_model: str
    embedding_model: str


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Reports API liveness and verifies Postgres + pgvector readiness."""
    settings = get_settings()
    db_status = "unavailable"
    pgvector_enabled = False

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
            ext_result = await conn.execute(
                text("SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector')")
            )
            pgvector_enabled = bool(ext_result.scalar())
            db_status = "ok"
    except Exception as exc:
        logger.warning("Database health check failed: %s", exc)

    overall_status = "ok" if (db_status == "ok" and pgvector_enabled) else "degraded"
    return HealthResponse(
        status=overall_status,
        service=settings.app_name,
        version=settings.app_version,
        database=db_status,
        pgvector=pgvector_enabled,
        claude_model=settings.claude_model,
        embedding_model=settings.embedding_model,
    )
