"""Stage 2 tests: skill taxonomy, seed dataset, KB chunking, local embeddings, and ingestion."""

import json
import math
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from app.services.chunker import chunk_markdown
from app.services.embeddings import (
    clear_embedding_cache,
    compute_content_hash,
    embed_text,
    embed_texts,
    embedding_cache_info,
)
from app.services.skills import SKILL_TAXONOMY, extract_skills, normalize_skill_name
from scripts import seed_jobs
from scripts.ingest_jobs import (
    normalize_arbeitnow_job,
    normalize_remotive_job,
    parse_monthly_inr_salary,
    strip_html,
)


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def test_skill_taxonomy_size_and_normalization() -> None:
    assert len(SKILL_TAXONOMY) >= 145
    names = [name for name, _, _ in SKILL_TAXONOMY]
    assert len(names) == len(set(names)), "Duplicate canonical skill names found"

    assert normalize_skill_name("PyTorch") == "pytorch"
    assert normalize_skill_name("Postgres") == "postgresql"
    assert normalize_skill_name("k8s") == "kubernetes"
    assert normalize_skill_name("ReactJS") == "react"
    assert normalize_skill_name("cpp") == "c++"
    assert normalize_skill_name("GitHub Actions") == "ci/cd"


def test_extract_skills_handles_importance_and_boundaries() -> None:
    title = "Junior Python & FastAPI Backend Engineer"
    description = (
        "Must-Have Skills:\n"
        "- Strong Python, PostgreSQL, and REST APIs with C++ exposure.\n"
        "- Familiarity with React and Docker.\n"
        "Good to Have:\n"
        "- Kubernetes and Redis experience."
    )
    extracted = extract_skills(title, description)
    by_name = {s.name: s.importance for s in extracted}

    assert by_name["python"] == 3
    assert by_name["fastapi"] == 3
    assert by_name["c++"] >= 2
    assert by_name["postgresql"] >= 2
    assert by_name["kubernetes"] == 1
    assert by_name["redis"] == 1
    # Guard against short-name false positives ("r" inside "react", "go" inside "good")
    assert "r" not in by_name
    assert "go" not in by_name
    assert "c" not in by_name


def test_seed_jobs_dataset_quality() -> None:
    seed_path = Path("data/jobs_seed.json")
    assert seed_path.exists(), "data/jobs_seed.json must be generated"
    jobs = json.loads(seed_path.read_text(encoding="utf-8"))
    assert len(jobs) >= 300

    urls = {j["source_url"] for j in jobs}
    assert len(urls) == len(jobs), "source_url values must be unique"

    locations = {j["location"] for j in jobs}
    assert any("Bengaluru" in loc for loc in locations)
    assert any("Hyderabad" in loc for loc in locations)
    assert any("Pune" in loc for loc in locations)
    assert any("Gurugram" in loc for loc in locations)
    assert any(j["remote"] for j in jobs)

    tracks = {j["track"] for j in jobs}
    for required_track in {"ai_ml", "backend", "fullstack", "data", "cybersecurity", "qa", "product"}:
        assert required_track in tracks

    for job in jobs[:25]:
        extracted = extract_skills(job["title"], job["description"])
        assert len(extracted) >= 3, f"Expected >=3 extracted skills for {job['title']}"


def test_kb_guides_exist_and_chunk_to_reasonable_sizes() -> None:
    kb_files = sorted(Path("data/kb").glob("*.md"))
    assert len(kb_files) >= 8

    total_chunks = 0
    for path in kb_files:
        chunks = chunk_markdown(
            content=path.read_text(encoding="utf-8"),
            source_url=f"kb://{path.name}",
            default_title=path.stem,
        )
        assert len(chunks) >= 3
        for chunk in chunks:
            word_count = len(chunk.text.split())
            assert 5 <= word_count <= 260
            assert chunk.source_url == f"kb://{path.name}"
        total_chunks += len(chunks)
    assert total_chunks >= 35


def test_content_hash_detects_changes() -> None:
    base_kwargs = {
        "title": "AI Intern",
        "company": "Nakshatra AI",
        "location": "Bengaluru",
        "remote": False,
        "salary_min": 35000,
        "salary_max": 45000,
        "description": "Build RAG systems with Python and pgvector.",
    }
    h1 = compute_content_hash(**base_kwargs)
    h2 = compute_content_hash(**base_kwargs)
    h3 = compute_content_hash(**{**base_kwargs, "salary_min": 40000})
    assert h1 == h2
    assert h1 != h3


def test_ingest_normalizers_and_html_stripping() -> None:
    cleaned = strip_html("<p>Build <b>Python</b> APIs &amp; ML pipelines.</p><ul><li>SQL</li></ul>")
    assert "Python" in cleaned
    assert "APIs & ML" in cleaned
    assert "<p>" not in cleaned

    lo, hi = parse_monthly_inr_salary("$60,000 - $80,000 / year")
    assert lo is not None and hi is not None and lo < hi

    rem = normalize_remotive_job(
        {
            "title": "Junior Python Developer",
            "company_name": "Acme",
            "candidate_required_location": "Worldwide",
            "salary": "",
            "description": "<p>FastAPI and PostgreSQL</p>",
            "url": "https://remotive.com/job/123",
            "publication_date": "2026-11-10T10:00:00Z",
        }
    )
    assert rem["source"] == "remotive"
    assert rem["remote"] is True
    assert "FastAPI" in rem["description"]

    arb = normalize_arbeitnow_job(
        {
            "title": "Backend Engineer",
            "company_name": "BerlinTech",
            "location": "Remote",
            "remote": True,
            "description": "<div>Docker and Kubernetes</div>",
            "url": "https://arbeitnow.com/jobs/456",
            "created_at": 1763500000,
        }
    )
    assert arb["source"] == "arbeitnow"
    assert arb["remote"] is True


def test_local_fastembed_dimensions_semantics_and_cache() -> None:
    clear_embedding_cache()
    v_backend = embed_text("Python FastAPI PostgreSQL backend engineer Bengaluru")
    v_backend_again = embed_text("Python   FastAPI PostgreSQL backend engineer Bengaluru")
    v_similar = embed_text("Async Python REST API developer with Postgres and SQL")
    v_different = embed_text("Door to door retail sales associate commission only")

    assert len(v_backend) == 384
    assert v_backend == v_backend_again
    assert embedding_cache_info()["hits"] >= 1
    assert _cosine(v_backend, v_similar) > _cosine(v_backend, v_different)

    batch = embed_texts(["Data analyst SQL Power BI", "Cybersecurity SOC SIEM"])
    assert len(batch) == 2
    assert len(batch[0]) == 384


async def test_job_seeding_releases_database_before_embedding(monkeypatch) -> None:
    result = MagicMock()
    result.all.return_value = []
    session = SimpleNamespace(
        execute=AsyncMock(return_value=result),
        rollback=AsyncMock(),
        add=MagicMock(),
        flush=AsyncMock(),
    )
    job = {
        "title": "Python Engineer",
        "company": "Example",
        "location": "Bengaluru",
        "remote": False,
        "salary_min": 30000,
        "salary_max": 50000,
        "description": "Build Python services.",
        "source_url": "https://example.test/jobs/python-engineer",
    }

    def fake_embed_texts(texts: list[str], batch_size: int) -> list[list[float]]:
        assert session.rollback.await_count == 1
        assert len(texts) == 1
        assert batch_size == 4
        return [[0.0] * 384]

    monkeypatch.setattr(seed_jobs, "embed_texts", fake_embed_texts)

    stats = await seed_jobs.upsert_jobs_batch(session, [job], {"python": 1})

    assert stats["inserted"] == 1
    assert stats["embedded"] == 1
