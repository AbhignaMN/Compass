"""RAG-grounded career roadmap generator using hybrid retrieval over kb_chunks."""

import json
import logging
import re
import uuid
from collections import defaultdict
from pathlib import Path
from typing import Any

from pydantic import ValidationError
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.llm import LLMClient
from app.agent.schemas import (
    RoadmapAlternative,
    RoadmapPlan,
    RoadmapSource,
    RoadmapWeek,
)
from app.config import get_settings
from app.db.models import Profile, Roadmap, User
from app.search.retrieval import reciprocal_rank_fusion
from app.services.chunker import chunk_markdown
from app.services.embeddings import embed_text
from app.services.memory import cosine_similarity

logger = logging.getLogger(__name__)
DEFAULT_KB_DIR = Path("data/kb")

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE | re.DOTALL)
_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


async def retrieve_kb_chunks(
    session: AsyncSession,
    query: str,
    k: int = 6,
) -> list[dict[str, str]]:
    """Retrieve top-k career guide chunks via hybrid vector + FTS RRF over kb_chunks."""
    settings = get_settings()
    qvec = "[" + ",".join(f"{x:.6f}" for x in embed_text(query)) + "]"

    try:
        vec_sql = text(
            """
            SELECT id, source_url, title, text
            FROM kb_chunks
            ORDER BY embedding <=> CAST(:qvec AS vector) ASC
            LIMIT 20
            """
        )
        kw_sql = text(
            """
            SELECT id, source_url, title, text
            FROM kb_chunks
            WHERE tsv @@ websearch_to_tsquery('english', :q)
            ORDER BY ts_rank_cd(tsv, websearch_to_tsquery('english', :q)) DESC
            LIMIT 20
            """
        )
        vec_rows = (await session.execute(vec_sql, {"qvec": qvec})).all()
        kw_rows = (await session.execute(kw_sql, {"q": query})).all()

        by_id: dict[uuid.UUID, dict[str, str]] = {}
        for row in [*vec_rows, *kw_rows]:
            by_id[row.id] = {
                "source_url": row.source_url,
                "title": row.title,
                "text": row.text,
            }

        ranked_lists = []
        if vec_rows:
            ranked_lists.append([r.id for r in vec_rows])
        if kw_rows:
            ranked_lists.append([r.id for r in kw_rows])

        if ranked_lists:
            rrf = reciprocal_rank_fusion(ranked_lists, k=settings.rrf_k)
            ordered = sorted(rrf.keys(), key=lambda cid: rrf[cid], reverse=True)[:k]
            return [by_id[cid] for cid in ordered if cid in by_id]
    except Exception as exc:
        logger.warning("DB kb_chunks retrieval unavailable (%s); falling back to local data/kb", exc)

    return _retrieve_local_kb_fallback(query, k=k)


def _retrieve_local_kb_fallback(query: str, k: int = 6) -> list[dict[str, str]]:
    """Read and rank local data/kb/*.md chunks when kb_chunks table is empty or offline."""
    md_files = sorted(DEFAULT_KB_DIR.glob("*.md"))
    if not md_files:
        return []

    q_vec = embed_text(query)
    scored: list[tuple[float, dict[str, str]]] = []
    q_terms = {w.lower() for w in query.split() if len(w) >= 2}

    for path in md_files:
        chunks = chunk_markdown(
            content=path.read_text(encoding="utf-8"),
            source_url=f"kb://{path.name}",
            default_title=path.stem.replace("-", " ").title(),
        )
        for chunk in chunks:
            c_vec = embed_text(f"{chunk.title}\n{chunk.text[:400]}")
            sim = cosine_similarity(q_vec, c_vec)
            kw_bonus = 0.05 * sum(1 for t in q_terms if t in chunk.title.lower() or t in chunk.text.lower())
            scored.append(
                (
                    sim + kw_bonus,
                    {"source_url": chunk.source_url, "title": chunk.title, "text": chunk.text},
                )
            )

    scored.sort(key=lambda item: item[0], reverse=True)
    return [item[1] for item in scored[:k]]


def _parse_roadmap_json(raw_text: str) -> RoadmapPlan:
    cleaned = _FENCE_RE.sub("", raw_text.strip()).strip()
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        match = _JSON_RE.search(cleaned)
        if not match:
            raise
        data = json.loads(match.group(0))
    return RoadmapPlan.model_validate(data)


def _enforce_grounded_sources(
    plan: RoadmapPlan, retrieved_chunks: list[dict[str, str]]
) -> RoadmapPlan:
    """Ensure every cited source in plan.sources exists in the retrieved KB chunks."""
    valid_by_url: dict[str, str] = {}
    for chunk in retrieved_chunks:
        valid_by_url.setdefault(chunk["source_url"], chunk["title"])

    grounded: list[RoadmapSource] = []
    seen: set[str] = set()
    for src in plan.sources:
        if src.source_url in valid_by_url and src.source_url not in seen:
            grounded.append(
                RoadmapSource(source_url=src.source_url, title=valid_by_url[src.source_url])
            )
            seen.add(src.source_url)

    if not grounded:
        for url, title in list(valid_by_url.items())[:3]:
            grounded.append(RoadmapSource(source_url=url, title=title))

    return plan.model_copy(update={"sources": grounded})


def _deterministic_fallback_roadmap(
    target_role: str,
    user_skills: list[str],
    weeks: int,
    chunks: list[dict[str, str]],
) -> RoadmapPlan:
    sources = []
    seen = set()
    for ch in chunks:
        if ch["source_url"] not in seen:
            sources.append(RoadmapSource(source_url=ch["source_url"], title=ch["title"]))
            seen.add(ch["source_url"])
        if len(sources) >= 3:
            break

    base_weeks = [
        RoadmapWeek(
            week=1,
            goal=f"Solidify core language, SQL, and fundamentals for {target_role}",
            resource="Official documentation + PostgreSQL Exercises (pgexercises.com)",
            project=f"Clean starter repo solving 2 real {target_role} core problems with tests",
            outcome="All core tests passing and documented in README",
        ),
        RoadmapWeek(
            week=2,
            goal=f"Build the primary technical workflow expected in {target_role} interviews",
            resource="Hands-on curated guide referenced in Compass KB",
            project=f"End-to-end mini-project tailored to {target_role} with real data",
            outcome="Working local demo with reproducible setup instructions",
        ),
        RoadmapWeek(
            week=3,
            goal="Add automated verification, benchmarks, and edge-case handling",
            resource="pytest / Postman / evaluation best practices from Compass KB",
            project="Add automated evaluation metrics and CI checks to your portfolio project",
            outcome="Published benchmark table and green GitHub Actions run",
        ),
        RoadmapWeek(
            week=4,
            goal="Deploy live, polish resume bullets, and practice mock interviews",
            resource="Docker + Render/Neon free-tier deployment guides",
            project="Deploy live URL with health check, architecture diagram, and 3 crisp STAR stories",
            outcome="Public live demo link ready to send to recruiters",
        ),
    ]

    gaps = ["production deployment", "automated testing", "role-specific portfolio project"]
    fit = min(85, 45 + len(user_skills) * 6)
    return RoadmapPlan(
        target_role=target_role,
        fit_score=fit,
        ranked_gaps=gaps,
        weeks=base_weeks[:weeks],
        apply_when=f"Start applying to {target_role} openings by Week {max(2, weeks - 1)} once your deployed project and tests are live.",
        alternatives=[
            RoadmapAlternative(
                role="Backend Engineer (Python / FastAPI)",
                tradeoff="Higher fresher hiring volume in India; more focus on APIs and SQL than specialized modeling.",
            ),
            RoadmapAlternative(
                role="Junior Data Analyst",
                tradeoff="Faster entry ramp via SQL + Python analytics, with a slightly lower starting ceiling than SWE.",
            ),
        ],
        sources=sources,
    )


async def build_rag_roadmap(
    *,
    session: AsyncSession,
    user_id: uuid.UUID,
    target_role: str,
    weeks: int = 4,
    llm_client: LLMClient | None = None,
) -> RoadmapPlan:
    """Retrieve KB chunks via hybrid RAG, generate a cited JSON roadmap, and persist versioned row."""
    settings = get_settings()
    llm = llm_client or LLMClient(settings)

    profile = await session.get(Profile, user_id)
    user_skills = list(profile.skills or []) if profile else []
    exp_level = (profile.experience_level or "fresher") if profile else "fresher"

    chunks = await retrieve_kb_chunks(
        session,
        query=f"{target_role} roadmap learning path free courses skills fresher India",
        k=6,
    )
    context_blocks = "\n\n".join(
        f"[SOURCE: {c['source_url']} | {c['title']}]\n{c['text']}" for c in chunks
    )

    plan: RoadmapPlan | None = None
    if llm.is_configured():
        system = (
            "You are Compass, a practical career mentor for freshers in India. "
            "Generate a realistic, week-by-week career learning roadmap grounded STRICTLY in the provided "
            "knowledge-base chunks. Cite the exact source_url values you used in `sources`. "
            "Return ONLY valid JSON matching this exact schema:\n"
            "{\n"
            '  "target_role": "string",\n'
            '  "fit_score": 0-100 integer,\n'
            '  "ranked_gaps": ["most important missing skill", ...],\n'
            '  "weeks": [{"week": 1, "goal": "...", "resource": "...", "project": "...", "outcome": "..."}],\n'
            '  "apply_when": "clear milestone for when to start applying",\n'
            '  "alternatives": [{"role": "Adjacent Role", "tradeoff": "honest 1-line tradeoff"}],\n'
            '  "sources": [{"source_url": "kb://...", "title": "..."}]\n'
            "}\n"
            "Include 2 or 3 adjacent-role alternatives with honest trade-offs."
        )
        user_prompt = (
            f"Target role: {target_role}\n"
            f"Duration: {weeks} weeks\n"
            f"User experience level: {exp_level}\n"
            f"User current skills: {', '.join(user_skills) if user_skills else 'beginner / none listed yet'}\n\n"
            f"Retrieved Career Guide Chunks:\n{context_blocks}"
        )

        messages: list[dict[str, Any]] = [{"role": "user", "content": user_prompt}]
        for attempt in range(2):
            resp = await llm.complete(
                system=system,
                messages=messages,
                max_tokens=1600,
                temperature=0.25,
                json_mode=True,
            )
            try:
                parsed = _parse_roadmap_json(resp.text)
                plan = _enforce_grounded_sources(parsed, chunks)
                break
            except (json.JSONDecodeError, ValidationError) as exc:
                logger.warning("Roadmap JSON validation failed (attempt %d): %s", attempt + 1, exc)
                if attempt == 0:
                    messages.append({"role": "assistant", "content": resp.text})
                    messages.append(
                        {
                            "role": "user",
                            "content": f"Validation error: {exc}. Return ONLY valid JSON matching the schema.",
                        }
                    )

    if plan is None:
        plan = _deterministic_fallback_roadmap(target_role, user_skills, weeks, chunks)

    # Persist versioned roadmap row
    try:
        user = await session.get(User, user_id)
        if user is None:
            session.add(User(id=user_id))
            await session.flush()

        max_ver_res = await session.execute(
            select(func.max(Roadmap.version)).where(
                Roadmap.user_id == user_id, Roadmap.target_role == plan.target_role
            )
        )
        next_version = int(max_ver_res.scalar() or 0) + 1
        session.add(
            Roadmap(
                id=uuid.uuid4(),
                user_id=user_id,
                target_role=plan.target_role,
                plan=plan.model_dump(mode="json"),
                version=next_version,
            )
        )
        await session.flush()
    except Exception as exc:
        logger.warning("Could not persist roadmap to DB: %s", exc)

    # Keep defaultdict referenced cleanly if needed in extensions
    _ = defaultdict(list)
    return plan
