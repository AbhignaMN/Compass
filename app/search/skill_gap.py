"""SQL-based skill-gap analysis joining user profile skills to job_skills."""

import uuid
from typing import Literal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.search.schemas import SkillGapItem, SkillGapResult

IMPORTANCE_LABELS: dict[int, Literal["must-have", "core", "nice-to-have"]] = {
    3: "must-have",
    2: "core",
    1: "nice-to-have",
}

SKILL_GAP_SQL = text(
    """
    WITH user_skills AS (
        SELECT lower(trim(skill_val)) AS skill_name
        FROM profiles p,
             LATERAL jsonb_array_elements_text(COALESCE(p.skills, '[]'::jsonb)) AS skill_val
        WHERE p.user_id = :user_id
    )
    SELECT
        j.title AS job_title,
        j.company AS company,
        s.name AS skill_name,
        s.category AS category,
        js.importance AS importance,
        (us.skill_name IS NOT NULL) AS is_matched
    FROM jobs j
    LEFT JOIN job_skills js ON js.job_id = j.id
    LEFT JOIN skills s ON s.id = js.skill_id
    LEFT JOIN user_skills us ON us.skill_name = lower(s.name)
    WHERE j.id = :job_id
    ORDER BY js.importance DESC NULLS LAST, s.name ASC
    """
)


async def compute_skill_gap(
    session: AsyncSession,
    user_id: uuid.UUID,
    job_id: uuid.UUID,
) -> SkillGapResult | None:
    """Compute matched and missing skills for (user_id, job_id) directly in Postgres SQL."""
    result = await session.execute(SKILL_GAP_SQL, {"user_id": user_id, "job_id": job_id})
    rows = result.all()
    if not rows:
        return None

    job_title = rows[0].job_title
    company = rows[0].company
    matched: list[str] = []
    missing: list[SkillGapItem] = []

    for row in rows:
        if row.skill_name is None:
            continue
        if row.is_matched:
            matched.append(row.skill_name)
        else:
            imp = int(row.importance or 2)
            missing.append(
                SkillGapItem(
                    skill=row.skill_name,
                    category=row.category or "general",
                    importance=imp,
                    importance_label=IMPORTANCE_LABELS.get(imp, "core"),
                )
            )

    total = len(matched) + len(missing)
    coverage = round((len(matched) / total) * 100.0, 1) if total > 0 else 100.0
    return SkillGapResult(
        job_id=job_id,
        job_title=job_title,
        company=company,
        matched_skills=matched,
        missing_skills=missing,
        coverage_pct=coverage,
    )
