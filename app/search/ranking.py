"""Weighted job ranking with configurable weights, interaction boosts, and score breakdowns."""

import math
import uuid
from datetime import UTC, datetime
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.db.models import Interaction
from app.search.schemas import RankedJob, ScoreBreakdown, SearchCandidate
from app.services.skills import normalize_skill_name

INTERACTION_ADJUSTMENTS: dict[str, float] = {
    "saved": 0.08,
    "clicked": 0.02,
    "dismissed": -0.18,
    "shown": 0.0,
}


def _extract_profile_field(profile: Any, key: str, default: Any = None) -> Any:
    if profile is None:
        return default
    if isinstance(profile, dict):
        return profile.get(key, default)
    return getattr(profile, key, default)


def _compute_skill_overlap(
    user_skills: set[str],
    candidate: SearchCandidate,
) -> tuple[float, list[str], list[str]]:
    if not candidate.skills:
        return 0.5, [], []

    matched: list[str] = []
    missing: list[str] = []
    total_weight = 0.0
    matched_weight = 0.0

    for sk in candidate.skills:
        w = float(sk.importance)
        total_weight += w
        if sk.name.lower() in user_skills:
            matched.append(sk.name)
            matched_weight += w
        else:
            missing.append(sk.name)

    if not user_skills:
        # Cold-start user without skills yet: return neutral score rather than 0
        return 0.5, [], missing

    ratio = matched_weight / total_weight if total_weight > 0 else 0.5
    return min(1.0, max(0.0, ratio)), matched, missing


def _compute_preference_fit(profile: Any, candidate: SearchCandidate) -> float:
    location_pref = (_extract_profile_field(profile, "location_pref") or "").strip().lower()
    remote_ok = bool(_extract_profile_field(profile, "remote_ok", True))
    salary_min = _extract_profile_field(profile, "salary_min")
    interests = [str(i).strip().lower() for i in (_extract_profile_field(profile, "interests") or [])]
    exp_level = (_extract_profile_field(profile, "experience_level") or "").strip().lower()

    # 1. Location & remote preference (weight 0.45)
    loc_lower = candidate.location.lower()
    if not location_pref:
        loc_score = 0.85 if (candidate.remote or not remote_ok) else 0.75
    elif location_pref == "remote":
        loc_score = 1.0 if candidate.remote else 0.25
    elif location_pref in loc_lower:
        loc_score = 1.0
    elif candidate.remote and remote_ok:
        loc_score = 0.85
    else:
        loc_score = 0.25

    # 2. Salary preference (weight 0.35)
    if not salary_min:
        sal_score = 0.75
    else:
        job_hi = candidate.salary_max or candidate.salary_min
        job_lo = candidate.salary_min or candidate.salary_max
        if job_hi is None:
            sal_score = 0.55
        elif job_lo is not None and job_lo >= salary_min:
            sal_score = 1.0
        elif job_hi >= salary_min:
            sal_score = 0.80
        else:
            sal_score = max(0.1, float(job_hi) / float(salary_min) * 0.6)

    # 3. Interest & experience alignment (weight 0.20)
    text_blob = f"{candidate.title} {candidate.description[:600]}".lower()
    interest_score = 0.65
    if interests:
        hits = sum(1 for item in interests if item and item in text_blob)
        interest_score = min(1.0, 0.4 + 0.6 * (hits / max(1, len(interests))))
    if exp_level:
        is_intern = "intern" in candidate.title.lower()
        if (exp_level == "intern" and is_intern) or (exp_level in {"fresher", "junior"} and not is_intern):
            interest_score = min(1.0, interest_score + 0.15)

    return round(min(1.0, max(0.0, 0.45 * loc_score + 0.35 * sal_score + 0.20 * interest_score)), 4)


def _compute_freshness(posted_at: datetime, now: datetime) -> float:
    if posted_at.tzinfo is None:
        posted_at = posted_at.replace(tzinfo=UTC)
    age_days = max(0.0, (now - posted_at).total_seconds() / 86400.0)
    return round(min(1.0, max(0.0, math.exp(-age_days / 30.0))), 4)


def _fit_label(pct: int) -> Literal["True North", "Heading right", "Detour"]:
    if pct >= 70:
        return "True North"
    if pct >= 48:
        return "Heading right"
    return "Detour"


def _build_why_it_fits(
    candidate: SearchCandidate,
    matched_skills: list[str],
    missing_skills: list[str],
    preference_fit: float,
) -> str:
    reasons: list[str] = []
    if matched_skills:
        top_matched = ", ".join(matched_skills[:4])
        reasons.append(f"Matches your {top_matched} skills")
    if candidate.remote:
        reasons.append("remote-friendly")
    elif preference_fit >= 0.8:
        reasons.append(f"fits your {candidate.location.split(',')[0]} & salary preferences")
    if candidate.salary_min and candidate.salary_max:
        reasons.append(f"pays ₹{candidate.salary_min // 1000}K–{candidate.salary_max // 1000}K/mo")
    if missing_skills:
        reasons.append(f"missing {', '.join(missing_skills[:2])}")
    return "; ".join(reasons) if reasons else "Relevant semantic match for your target track"


def rank_jobs(
    profile: Any,
    candidates: list[SearchCandidate],
    interaction_events: dict[uuid.UUID, str] | None = None,
    now: datetime | None = None,
    settings: Settings | None = None,
    top_n: int = 50,
) -> list[RankedJob]:
    """Score top 50 candidates using configurable weights + interaction adjustments."""
    cfg = settings or get_settings()
    ref_time = now or datetime.now(UTC)
    interactions = interaction_events or {}

    raw_skills = _extract_profile_field(profile, "skills") or []
    user_skills = {normalize_skill_name(str(s)) for s in raw_skills if str(s).strip()}

    pool = candidates[:top_n]
    max_rrf = max((c.rrf_score for c in pool), default=0.0)

    ranked: list[RankedJob] = []
    for cand in pool:
        if cand.vector_similarity > 0:
            semantic = min(1.0, max(0.0, cand.vector_similarity))
        elif max_rrf > 0:
            semantic = min(1.0, max(0.0, cand.rrf_score / max_rrf))
        else:
            semantic = 0.0

        skill_overlap, matched_skills, missing_skills = _compute_skill_overlap(user_skills, cand)
        pref_fit = _compute_preference_fit(profile, cand)
        freshness = _compute_freshness(cand.posted_at, ref_time)

        base_score = (
            cfg.rank_weight_semantic * semantic
            + cfg.rank_weight_skill_overlap * skill_overlap
            + cfg.rank_weight_preference_fit * pref_fit
            + cfg.rank_weight_freshness * freshness
        )

        event = interactions.get(cand.job_id, "")
        adj = INTERACTION_ADJUSTMENTS.get(event, 0.0)
        final_score = min(1.0, max(0.0, base_score + adj))
        pct = int(round(final_score * 100))

        ranked.append(
            RankedJob(
                job_id=cand.job_id,
                title=cand.title,
                company=cand.company,
                location=cand.location,
                remote=cand.remote,
                salary_min=cand.salary_min,
                salary_max=cand.salary_max,
                source=cand.source,
                source_url=cand.source_url,
                posted_at=cand.posted_at,
                fit_score_pct=pct,
                fit_label=_fit_label(pct),
                scores=ScoreBreakdown(
                    semantic=round(semantic, 4),
                    skill_overlap=round(skill_overlap, 4),
                    preference_fit=round(pref_fit, 4),
                    freshness=round(freshness, 4),
                    interaction_adjustment=round(adj, 4),
                    final_score=round(final_score, 4),
                ),
                matched_skills=matched_skills,
                missing_skills=missing_skills,
                why_it_fits=_build_why_it_fits(cand, matched_skills, missing_skills, pref_fit),
            )
        )

    ranked.sort(key=lambda r: (r.scores.final_score, r.scores.skill_overlap), reverse=True)
    return ranked


async def fetch_user_interactions(
    session: AsyncSession,
    user_id: uuid.UUID,
    job_ids: list[uuid.UUID],
) -> dict[uuid.UUID, str]:
    """Fetch the most recent interaction event per job for a user."""
    if not job_ids:
        return {}
    stmt = (
        select(Interaction.job_id, Interaction.event)
        .where(Interaction.user_id == user_id, Interaction.job_id.in_(job_ids))
        .order_by(Interaction.created_at.asc())
    )
    result = await session.execute(stmt)
    # Later events overwrite earlier ones (e.g. saved -> dismissed)
    return {job_id: event for job_id, event in result.all()}
