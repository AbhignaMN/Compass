"""Local embedding service (fastembed BAAI/bge-small-en-v1.5, 384 dims) with LRU cache."""

import hashlib
import logging
from functools import lru_cache
from threading import Lock
from typing import Any

from app.config import get_settings

logger = logging.getLogger(__name__)

_model_lock = Lock()
_embedding_model: Any | None = None


def get_embedding_model() -> Any:
    """Lazy-load the fastembed TextEmbedding model once per process."""
    global _embedding_model
    if _embedding_model is not None:
        return _embedding_model

    with _model_lock:
        if _embedding_model is None:
            from fastembed import TextEmbedding

            settings = get_settings()
            logger.info(
                "Loading local embedding model %s (cache_dir=%s)",
                settings.embedding_model,
                settings.embedding_cache_dir,
            )
            _embedding_model = TextEmbedding(
                model_name=settings.embedding_model,
                cache_dir=settings.embedding_cache_dir,
                threads=1,
            )
    return _embedding_model


@lru_cache(maxsize=2048)
def _embed_single_cached(normalized_text: str) -> tuple[float, ...]:
    model = get_embedding_model()
    vec = next(model.embed([normalized_text], batch_size=1))
    return tuple(float(x) for x in vec.tolist())


def embed_text(text: str) -> list[float]:
    """Embed a single query or short text using an in-memory LRU cache."""
    normalized = " ".join(text.strip().split())
    if not normalized:
        normalized = "career"
    return list(_embed_single_cached(normalized))


def embed_texts(texts: list[str], batch_size: int = 4) -> list[list[float]]:
    """Batch-embed documents for fast seeding and incremental ingestion."""
    if not texts:
        return []
    cleaned = [" ".join(t.strip().split()) or "career" for t in texts]
    model = get_embedding_model()
    return [vec.tolist() for vec in model.embed(cleaned, batch_size=batch_size)]


def clear_embedding_cache() -> None:
    _embed_single_cached.cache_clear()


def embedding_cache_info() -> dict[str, int]:
    info = _embed_single_cached.cache_info()
    return {
        "hits": info.hits,
        "misses": info.misses,
        "currsize": info.currsize,
        "maxsize": info.maxsize or 0,
    }


def build_job_embedding_text(
    title: str,
    company: str,
    location: str,
    remote: bool,
    description: str,
    skills: list[str] | None = None,
) -> str:
    """Assemble the canonical text representation embedded for a job posting."""
    work_mode = "Remote" if remote else "On-site / Hybrid"
    skill_line = f"Skills: {', '.join(skills)}." if skills else ""
    return (
        f"Role: {title} at {company}. Location: {location} ({work_mode}). "
        f"{skill_line} {description[:2500]}"
    ).strip()


def compute_content_hash(
    *,
    title: str,
    company: str,
    location: str,
    remote: bool,
    salary_min: int | None,
    salary_max: int | None,
    description: str,
) -> str:
    """Stable SHA-256 fingerprint used to detect changed job rows before re-embedding."""
    canonical = "|".join(
        [
            title.strip().lower(),
            company.strip().lower(),
            location.strip().lower(),
            str(bool(remote)),
            str(salary_min or ""),
            str(salary_max or ""),
            " ".join(description.strip().split()),
        ]
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
