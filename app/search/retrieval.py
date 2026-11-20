"""Hybrid search: pgvector cosine similarity + Postgres FTS merged via RRF (k=60)."""

import uuid
from collections import defaultdict
from typing import Any, Literal

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models import Job, JobSkill, Skill
from app.search.schemas import JobSearchFilters, JobSkillInfo, SearchCandidate
from app.services.embeddings import embed_text

SearchMode = Literal["hybrid", "vector", "keyword"]


def reciprocal_rank_fusion(
    ranked_lists: list[list[uuid.UUID]],
    k: int = 60,
) -> dict[uuid.UUID, float]:
    """Combine multiple ranked ID lists with Reciprocal Rank Fusion: sum(1 / (k + rank))."""
    scores: dict[uuid.UUID, float] = defaultdict(float)
    for id_list in ranked_lists:
        for rank, item_id in enumerate(id_list, start=1):
            scores[item_id] += 1.0 / (k + rank)
    return dict(scores)


def _build_hard_filter_sql(filters: JobSearchFilters | None) -> tuple[str, dict[str, Any]]:
    """Build SQL WHERE clauses and bound params for hard job filters."""
    clauses = ["j.status = 'active'"]
    params: dict[str, Any] = {}

    if not filters:
        return " AND ".join(clauses), params

    if filters.remote_only is True:
        clauses.append("j.remote = true")

    if filters.location:
        loc = filters.location.strip()
        if loc.lower() == "remote":
            clauses.append("(j.remote = true OR j.location ILIKE :loc_pattern)")
            params["loc_pattern"] = "%remote%"
        else:
            clauses.append("(j.location ILIKE :loc_pattern OR j.remote = true)")
            params["loc_pattern"] = f"%{loc}%"

    if filters.salary_min is not None and filters.salary_min > 0:
        # Include jobs whose salary band reaches at least the user's minimum (or undisclosed)
        clauses.append("(COALESCE(j.salary_max, j.salary_min) >= :salary_min)")
        params["salary_min"] = int(filters.salary_min)

    for idx, kw in enumerate(filters.exclude_keywords):
        cleaned = kw.strip()
        if cleaned:
            key = f"excl_kw_{idx}"
            clauses.append(f"j.title NOT ILIKE :{key}")
            params[key] = f"%{cleaned}%"

    return " AND ".join(clauses), params


def _vector_literal(vec: list[float]) -> str:
    return "[" + ",".join(f"{x:.6f}" for x in vec) + "]"


async def vector_search(
    session: AsyncSession,
    query_embedding: list[float],
    filters: JobSearchFilters | None = None,
    limit: int = 50,
) -> list[tuple[uuid.UUID, float]]:
    """Run pgvector HNSW cosine similarity search with SQL hard filters."""
    where_sql, params = _build_hard_filter_sql(filters)
    params["qvec"] = _vector_literal(query_embedding)
    params["limit"] = limit

    sql = text(
        f"""
        SELECT j.id, (1.0 - (je.embedding <=> CAST(:qvec AS vector))) AS similarity
        FROM jobs j
        JOIN job_embeddings je ON je.job_id = j.id
        WHERE {where_sql}
        ORDER BY je.embedding <=> CAST(:qvec AS vector) ASC
        LIMIT :limit
        """
    )
    result = await session.execute(sql, params)
    return [(row[0], float(row[1])) for row in result.all()]


async def keyword_search(
    session: AsyncSession,
    query: str,
    filters: JobSearchFilters | None = None,
    limit: int = 50,
) -> list[tuple[uuid.UUID, float]]:
    """Run Postgres full-text search on weighted tsvector with SQL hard filters."""
    cleaned_query = " ".join(query.strip().split())
    if not cleaned_query:
        return []

    where_sql, params = _build_hard_filter_sql(filters)
    params["q"] = cleaned_query
    params["limit"] = limit

    sql = text(
        f"""
        WITH tsq AS (
            SELECT websearch_to_tsquery('english', :q) AS q
        )
        SELECT j.id, ts_rank_cd(j.tsv, tsq.q) AS kw_score
        FROM jobs j, tsq
        WHERE {where_sql}
          AND j.tsv @@ tsq.q
        ORDER BY kw_score DESC, j.posted_at DESC
        LIMIT :limit
        """
    )
    result = await session.execute(sql, params)
    rows = [(row[0], float(row[1])) for row in result.all()]

    # If strict AND websearch returned few hits, broaden with OR-ed plain terms for recall
    if len(rows) < min(10, limit):
        tokens = [t for t in cleaned_query.replace("/", " ").split() if len(t) >= 2][:10]
        if len(tokens) >= 2:
            or_query = " OR ".join(tokens)
            params_or = {**params, "q": or_query}
            or_result = await session.execute(sql, params_or)
            seen = {r[0] for r in rows}
            for row_id, score in or_result.all():
                if row_id not in seen:
                    rows.append((row_id, float(score) * 0.6))
                    seen.add(row_id)
                if len(rows) >= limit:
                    break

    return rows[:limit]


async def hydrate_candidates(
    session: AsyncSession,
    ordered_ids: list[uuid.UUID],
    vector_meta: dict[uuid.UUID, tuple[int, float]],
    keyword_meta: dict[uuid.UUID, tuple[int, float]],
    rrf_scores: dict[uuid.UUID, float],
) -> list[SearchCandidate]:
    """Load Job rows and associated skills in two batch queries, preserving rank order."""
    if not ordered_ids:
        return []

    jobs_res = await session.execute(select(Job).where(Job.id.in_(ordered_ids)))
    jobs_by_id = {job.id: job for job in jobs_res.scalars().all()}

    skills_res = await session.execute(
        select(JobSkill.job_id, Skill.name, Skill.category, JobSkill.importance)
        .join(Skill, Skill.id == JobSkill.skill_id)
        .where(JobSkill.job_id.in_(ordered_ids))
        .order_by(JobSkill.importance.desc(), Skill.name.asc())
    )
    skills_by_job: dict[uuid.UUID, list[JobSkillInfo]] = defaultdict(list)
    for job_id, name, category, importance in skills_res.all():
        skills_by_job[job_id].append(
            JobSkillInfo(name=name, category=category, importance=int(importance))
        )

    candidates: list[SearchCandidate] = []
    for job_id in ordered_ids:
        job = jobs_by_id.get(job_id)
        if not job:
            continue
        v_rank, v_sim = vector_meta.get(job_id, (None, 0.0))
        k_rank, k_score = keyword_meta.get(job_id, (None, 0.0))
        candidates.append(
            SearchCandidate(
                job_id=job.id,
                title=job.title,
                company=job.company,
                location=job.location,
                remote=job.remote,
                salary_min=job.salary_min,
                salary_max=job.salary_max,
                description=job.description,
                source=job.source,
                source_url=job.source_url,
                posted_at=job.posted_at,
                skills=skills_by_job.get(job.id, []),
                vector_rank=v_rank,
                keyword_rank=k_rank,
                vector_similarity=v_sim,
                keyword_score=k_score,
                rrf_score=rrf_scores.get(job.id, 0.0),
            )
        )
    return candidates


async def hybrid_search(
    session: AsyncSession,
    query: str,
    filters: JobSearchFilters | None = None,
    k: int = 20,
    candidate_pool: int = 50,
    mode: SearchMode = "hybrid",
) -> list[SearchCandidate]:
    """Execute vector + keyword search separately and fuse with RRF (k=60)."""
    settings = get_settings()
    pool_size = max(k, candidate_pool)

    vector_hits: list[tuple[uuid.UUID, float]] = []
    keyword_hits: list[tuple[uuid.UUID, float]] = []

    if mode in ("hybrid", "vector"):
        query_vec = embed_text(query)
        vector_hits = await vector_search(session, query_vec, filters=filters, limit=pool_size)

    if mode in ("hybrid", "keyword"):
        keyword_hits = await keyword_search(session, query, filters=filters, limit=pool_size)

    vector_meta = {
        job_id: (rank, sim) for rank, (job_id, sim) in enumerate(vector_hits, start=1)
    }
    keyword_meta = {
        job_id: (rank, score) for rank, (job_id, score) in enumerate(keyword_hits, start=1)
    }

    ranked_lists: list[list[uuid.UUID]] = []
    if vector_hits:
        ranked_lists.append([job_id for job_id, _ in vector_hits])
    if keyword_hits:
        ranked_lists.append([job_id for job_id, _ in keyword_hits])

    if not ranked_lists:
        return []

    rrf_scores = reciprocal_rank_fusion(ranked_lists, k=settings.rrf_k)
    ordered_ids = sorted(
        rrf_scores.keys(),
        key=lambda jid: (
            rrf_scores[jid],
            vector_meta.get(jid, (999, 0.0))[1],
            keyword_meta.get(jid, (999, 0.0))[1],
        ),
        reverse=True,
    )[:k]

    return await hydrate_candidates(session, ordered_ids, vector_meta, keyword_meta, rrf_scores)
