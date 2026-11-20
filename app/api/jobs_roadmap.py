"""Job detail, user interaction feedback, and roadmap endpoints."""

import uuid
from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.schemas import RoadmapPlan
from app.api.chat import resolve_anonymous_user_id
from app.db.models import Interaction, Job, JobSkill, Roadmap, Skill, User
from app.db.session import get_db_session
from app.search.schemas import JobSkillInfo, SkillGapResult
from app.search.skill_gap import compute_skill_gap

router = APIRouter(tags=["jobs-and-roadmaps"])


class JobDetailResponse(BaseModel):
    id: uuid.UUID
    title: str
    company: str
    location: str
    remote: bool
    salary_min: int | None = None
    salary_max: int | None = None
    description: str
    source: str
    source_url: str
    posted_at: datetime
    status: str
    skills: list[JobSkillInfo]
    skill_gap: SkillGapResult | None = None


class FeedbackRequest(BaseModel):
    job_id: uuid.UUID
    event: Literal["shown", "clicked", "saved", "dismissed"] | None = None
    rating: Literal["up", "down"] | None = None


class FeedbackResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    job_id: uuid.UUID
    event: str
    recorded: bool = True


class RoadmapRecordResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    target_role: str
    version: int
    plan: RoadmapPlan
    created_at: datetime


@router.get("/jobs/{job_id}", response_model=JobDetailResponse)
async def get_job_detail(
    job_id: uuid.UUID,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
) -> JobDetailResponse:
    job = await session.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    skills_res = await session.execute(
        select(Skill.name, Skill.category, JobSkill.importance)
        .join(Skill, Skill.id == JobSkill.skill_id)
        .where(JobSkill.job_id == job_id)
        .order_by(JobSkill.importance.desc(), Skill.name.asc())
    )
    skills = [
        JobSkillInfo(name=name, category=category, importance=int(imp))
        for name, category, imp in skills_res.all()
    ]

    user_id = resolve_anonymous_user_id(request)
    gap: SkillGapResult | None = None
    try:
        gap = await compute_skill_gap(session, user_id, job_id)
    except Exception:
        gap = None

    return JobDetailResponse(
        id=job.id,
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
        status=job.status,
        skills=skills,
        skill_gap=gap,
    )


@router.post("/feedback", response_model=FeedbackResponse)
async def record_feedback(
    payload: FeedbackRequest,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
) -> FeedbackResponse:
    event = payload.event
    if event is None:
        if payload.rating == "up":
            event = "saved"
        elif payload.rating == "down":
            event = "dismissed"
        else:
            raise HTTPException(status_code=422, detail="Provide either event or rating ('up'|'down').")

    user_id = resolve_anonymous_user_id(request)
    user = await session.get(User, user_id)
    if user is None:
        session.add(User(id=user_id))
        await session.flush()

    job = await session.get(Job, payload.job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    interaction = Interaction(
        id=uuid.uuid4(),
        user_id=user_id,
        job_id=payload.job_id,
        event=event,
    )
    session.add(interaction)
    await session.commit()

    return FeedbackResponse(
        id=interaction.id,
        user_id=user_id,
        job_id=payload.job_id,
        event=event,
    )


@router.get("/roadmap/{user_id}", response_model=list[RoadmapRecordResponse])
async def get_user_roadmaps(
    user_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
) -> list[RoadmapRecordResponse]:
    res = await session.execute(
        select(Roadmap)
        .where(Roadmap.user_id == user_id)
        .order_by(Roadmap.created_at.desc())
        .limit(10)
    )
    rows = list(res.scalars().all())
    out: list[RoadmapRecordResponse] = []
    for row in rows:
        plan_obj: Any = row.plan
        out.append(
            RoadmapRecordResponse(
                id=row.id,
                user_id=row.user_id,
                target_role=row.target_role,
                version=row.version,
                plan=RoadmapPlan.model_validate(plan_obj),
                created_at=row.created_at,
            )
        )
    return out
