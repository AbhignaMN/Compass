"""Stage 3 tests: RRF fusion, SQL filters, weighted job ranking, and SQL skill-gap query."""

import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.search.ranking import rank_jobs
from app.search.retrieval import _build_hard_filter_sql, reciprocal_rank_fusion
from app.search.schemas import JobSearchFilters, JobSkillInfo, SearchCandidate
from app.search.skill_gap import SKILL_GAP_SQL, compute_skill_gap


def _make_candidate(
    *,
    title: str = "Backend Engineer (Python / FastAPI)",
    company: str = "KaveriPay",
    location: str = "Bengaluru, Karnataka",
    remote: bool = False,
    salary_min: int = 60000,
    salary_max: int = 80000,
    skills: list[tuple[str, str, int]] | None = None,
    vector_similarity: float = 0.85,
    days_ago: int = 2,
) -> SearchCandidate:
    base_now = datetime(2026, 11, 20, 12, 0, tzinfo=UTC)
    skill_objs = [
        JobSkillInfo(name=n, category=c, importance=imp)
        for n, c, imp in (
            skills
            or [
                ("python", "language", 3),
                ("fastapi", "backend", 3),
                ("postgresql", "database", 2),
                ("docker", "cloud_devops", 1),
            ]
        )
    ]
    return SearchCandidate(
        job_id=uuid.uuid4(),
        title=title,
        company=company,
        location=location,
        remote=remote,
        salary_min=salary_min,
        salary_max=salary_max,
        description=f"{title} working with Python, FastAPI, PostgreSQL.",
        source="seed",
        source_url=f"https://sample.local/{uuid.uuid4()}",
        posted_at=base_now - timedelta(days=days_ago),
        skills=skill_objs,
        vector_similarity=vector_similarity,
        rrf_score=0.03,
    )


def test_reciprocal_rank_fusion_promotes_shared_top_hits() -> None:
    id_a, id_b, id_c, id_d = uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    vector_list = [id_a, id_b, id_c]
    keyword_list = [id_b, id_d, id_a]

    scores = reciprocal_rank_fusion([vector_list, keyword_list], k=60)
    assert scores[id_b] == pytest.approx(1 / 62 + 1 / 61)
    assert scores[id_a] == pytest.approx(1 / 61 + 1 / 63)
    assert scores[id_b] > scores[id_a] > scores[id_c]
    assert scores[id_d] > scores[id_c]


def test_hard_filter_sql_builds_safe_parameterized_clauses() -> None:
    filters = JobSearchFilters(
        location="Bengaluru",
        remote_only=False,
        salary_min=50000,
        exclude_keywords=["sales", "bpo"],
    )
    where_sql, params = _build_hard_filter_sql(filters)
    assert "j.status = 'active'" in where_sql
    assert "j.location ILIKE :loc_pattern" in where_sql
    assert "COALESCE(j.salary_max, j.salary_min) >= :salary_min" in where_sql
    assert "j.title NOT ILIKE :excl_kw_0" in where_sql
    assert "j.title NOT ILIKE :excl_kw_1" in where_sql
    assert params["loc_pattern"] == "%Bengaluru%"
    assert params["salary_min"] == 50000
    assert params["excl_kw_0"] == "%sales%"


def test_rank_jobs_combines_weights_and_interaction_boost_penalty() -> None:
    now = datetime(2026, 11, 20, 12, 0, tzinfo=UTC)
    profile = {
        "skills": ["Python", "FastAPI", "Postgres"],
        "interests": ["backend", "python"],
        "location_pref": "Bengaluru",
        "remote_ok": True,
        "salary_min": 50000,
        "experience_level": "fresher",
    }

    strong = _make_candidate(
        title="Backend Engineer (Python / FastAPI)",
        location="Bengaluru, Karnataka",
        salary_min=65000,
        salary_max=85000,
        vector_similarity=0.90,
        days_ago=1,
    )
    weak = _make_candidate(
        title="Junior Manual QA Tester",
        location="Chennai, Tamil Nadu",
        remote=False,
        salary_min=25000,
        salary_max=32000,
        skills=[("manual testing", "qa_testing", 3), ("selenium", "qa_testing", 2)],
        vector_similarity=0.42,
        days_ago=40,
    )
    saved_copy = _make_candidate(
        title="Python Backend Developer",
        location="Bengaluru, Karnataka",
        salary_min=60000,
        salary_max=80000,
        vector_similarity=0.84,
        days_ago=3,
    )

    ranked = rank_jobs(
        profile,
        [weak, saved_copy, strong],
        interaction_events={saved_copy.job_id: "saved", weak.job_id: "dismissed"},
        now=now,
    )

    assert len(ranked) == 3
    by_id = {r.job_id: r for r in ranked}
    assert by_id[strong.job_id].scores.final_score > by_id[weak.job_id].scores.final_score
    assert by_id[saved_copy.job_id].scores.interaction_adjustment == pytest.approx(0.08)
    assert by_id[weak.job_id].scores.interaction_adjustment == pytest.approx(-0.18)
    assert by_id[strong.job_id].fit_label == "True North"
    assert by_id[weak.job_id].fit_label == "Detour"
    assert "python" in by_id[strong.job_id].matched_skills
    assert "docker" in by_id[strong.job_id].missing_skills
    assert by_id[strong.job_id].scores.freshness > by_id[weak.job_id].scores.freshness


async def test_compute_skill_gap_parses_sql_rows_in_importance_order() -> None:
    user_id = uuid.uuid4()
    job_id = uuid.uuid4()

    fake_rows = [
        SimpleNamespace(
            job_title="AI / LLM Engineer Intern",
            company="Nakshatra AI",
            skill_name="python",
            category="language",
            importance=3,
            is_matched=True,
        ),
        SimpleNamespace(
            job_title="AI / LLM Engineer Intern",
            company="Nakshatra AI",
            skill_name="pgvector",
            category="ai_ml",
            importance=3,
            is_matched=False,
        ),
        SimpleNamespace(
            job_title="AI / LLM Engineer Intern",
            company="Nakshatra AI",
            skill_name="docker",
            category="cloud_devops",
            importance=1,
            is_matched=False,
        ),
    ]
    mock_result = MagicMock()
    mock_result.all.return_value = fake_rows
    mock_session = AsyncMock()
    mock_session.execute.return_value = mock_result

    gap = await compute_skill_gap(mock_session, user_id, job_id)
    assert gap is not None
    assert gap.job_title == "AI / LLM Engineer Intern"
    assert gap.matched_skills == ["python"]
    assert [m.skill for m in gap.missing_skills] == ["pgvector", "docker"]
    assert gap.missing_skills[0].importance_label == "must-have"
    assert gap.missing_skills[1].importance_label == "nice-to-have"
    assert gap.coverage_pct == pytest.approx(33.3)
    assert "jsonb_array_elements_text" in str(SKILL_GAP_SQL)
