"""Stage 1 verification tests: config, DB URL normalization, ORM schema, and /health."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from app.config import Settings
from app.db.base import Base
from app.db.models import EMBEDDING_DIM, Job, JobEmbedding, KBChunk, Memory
from app.db.session import normalize_database_url


def test_settings_defaults_and_weights_sum() -> None:
    settings = Settings()
    total_weight = (
        settings.rank_weight_semantic
        + settings.rank_weight_skill_overlap
        + settings.rank_weight_preference_fit
        + settings.rank_weight_freshness
    )
    assert total_weight == pytest.approx(1.0)
    assert settings.embedding_dim == 384
    assert settings.embedding_model == "BAAI/bge-small-en-v1.5"
    assert settings.claude_model != ""


def test_normalize_database_url_handles_neon_ssl() -> None:
    raw = "postgres://user:pass@ep-cool.neon.tech/neondb?sslmode=require&channel_binding=require"
    clean_url, connect_args = normalize_database_url(raw)
    assert clean_url == "postgresql+asyncpg://user:pass@ep-cool.neon.tech/neondb"
    assert "ssl" in connect_args
    assert connect_args["ssl"] is not False


def test_normalize_database_url_handles_local_postgres() -> None:
    raw = "postgresql://compass:compass@localhost:5432/compass"
    clean_url, connect_args = normalize_database_url(raw)
    assert clean_url == "postgresql+asyncpg://compass:compass@localhost:5432/compass"
    assert connect_args == {}


def test_schema_contains_all_required_tables_and_vector_dims() -> None:
    expected_tables = {
        "users",
        "profiles",
        "jobs",
        "job_embeddings",
        "skills",
        "job_skills",
        "conversations",
        "messages",
        "memories",
        "interactions",
        "roadmaps",
        "kb_chunks",
    }
    assert expected_tables.issubset(set(Base.metadata.tables.keys()))
    assert EMBEDDING_DIM == 384
    assert JobEmbedding.__table__.c.embedding.type.dim == 384
    assert Memory.__table__.c.embedding.type.dim == 384
    assert KBChunk.__table__.c.embedding.type.dim == 384

    job_indexes = {idx.name for idx in Job.__table__.indexes}
    assert "ix_jobs_tsv_gin" in job_indexes
    assert "ix_jobs_status_posted_at" in job_indexes

    emb_indexes = {idx.name for idx in JobEmbedding.__table__.indexes}
    assert "ix_job_embeddings_hnsw_cosine" in emb_indexes


async def test_health_endpoint_ok_when_db_and_pgvector_ready(client: AsyncClient) -> None:
    mock_conn = AsyncMock()
    ext_result = MagicMock()
    ext_result.scalar.return_value = True
    mock_conn.execute.side_effect = [MagicMock(), ext_result]

    mock_ctx = AsyncMock()
    mock_ctx.__aenter__.return_value = mock_conn
    mock_ctx.__aexit__.return_value = None

    mock_engine = MagicMock()
    mock_engine.connect.return_value = mock_ctx

    with patch("app.api.health.engine", mock_engine):
        response = await client.get("/health")

    assert response.status_code == 200
    assert "X-Request-ID" in response.headers
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["database"] == "ok"
    assert payload["pgvector"] is True
    assert payload["service"] == "Compass"


async def test_health_endpoint_degraded_when_db_unavailable(client: AsyncClient) -> None:
    mock_engine = MagicMock()
    mock_engine.connect.side_effect = ConnectionRefusedError("db down")

    with patch("app.api.health.engine", mock_engine):
        response = await client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "degraded"
    assert payload["database"] == "unavailable"
    assert payload["pgvector"] is False
