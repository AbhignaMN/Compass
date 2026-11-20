"""Profile and memory management endpoints for the 'Your profile' UI side panel."""

import uuid
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.schemas import ProfileSnapshot
from app.api.chat import USER_COOKIE_NAME, USER_HEADER_NAME, resolve_anonymous_user_id
from app.db.models import Memory, Profile, User
from app.db.session import get_db_session
from app.services.embeddings import embed_text
from app.services.skills import normalize_skill_name

router = APIRouter(tags=["profile"])


class MemoryItemResponse(BaseModel):
    id: uuid.UUID
    type: Literal["fact", "preference", "goal"]
    text: str
    last_seen: datetime
    created_at: datetime


class ProfilePanelResponse(BaseModel):
    profile: ProfileSnapshot
    memories: list[MemoryItemResponse]


class ProfilePatchRequest(BaseModel):
    skills: list[str] | None = None
    interests: list[str] | None = None
    location_pref: str | None = None
    remote_ok: bool | None = None
    salary_min: int | None = Field(default=None, ge=0)
    experience_level: Literal["student", "intern", "fresher", "junior"] | None = None
    goals: str | None = None


class MemoryPatchRequest(BaseModel):
    text: str = Field(min_length=3, max_length=240)
    type: Literal["fact", "preference", "goal"] | None = None


async def _get_or_create_profile(session: AsyncSession, user_id: uuid.UUID) -> Profile:
    user = await session.get(User, user_id)
    if user is None:
        session.add(User(id=user_id))
        await session.flush()

    profile = await session.get(Profile, user_id)
    if profile is None:
        profile = Profile(user_id=user_id, skills=[], interests=[], remote_ok=True)
        session.add(profile)
        await session.flush()
    return profile


def _serialize_profile(profile: Profile) -> ProfileSnapshot:
    return ProfileSnapshot(
        user_id=profile.user_id,
        skills=list(profile.skills or []),
        interests=list(profile.interests or []),
        location_pref=profile.location_pref,
        remote_ok=bool(profile.remote_ok),
        salary_min=profile.salary_min,
        experience_level=profile.experience_level,
        goals=profile.goals,
    )


@router.get("/profile", response_model=ProfilePanelResponse)
async def get_profile_panel(
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_db_session),
) -> ProfilePanelResponse:
    user_id = resolve_anonymous_user_id(request)
    profile = await _get_or_create_profile(session, user_id)
    mem_res = await session.execute(
        select(Memory)
        .where(Memory.user_id == user_id)
        .order_by(Memory.last_seen.desc())
    )
    memories = list(mem_res.scalars().all())
    await session.commit()

    response.headers[USER_HEADER_NAME] = str(user_id)
    response.set_cookie(key=USER_COOKIE_NAME, value=str(user_id), max_age=60 * 60 * 24 * 180, samesite="lax")
    return ProfilePanelResponse(
        profile=_serialize_profile(profile),
        memories=[
            MemoryItemResponse(
                id=m.id,
                type=m.type,  # type: ignore[arg-type]
                text=m.text,
                last_seen=m.last_seen,
                created_at=m.created_at,
            )
            for m in memories
        ],
    )


@router.patch("/profile", response_model=ProfileSnapshot)
async def patch_profile(
    payload: ProfilePatchRequest,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
) -> ProfileSnapshot:
    user_id = resolve_anonymous_user_id(request)
    profile = await _get_or_create_profile(session, user_id)

    if payload.skills is not None:
        profile.skills = list(
            dict.fromkeys(normalize_skill_name(s) for s in payload.skills if s.strip())
        )
    if payload.interests is not None:
        profile.interests = list(dict.fromkeys(i.strip().lower() for i in payload.interests if i.strip()))
    if payload.location_pref is not None:
        profile.location_pref = payload.location_pref.strip() or None
    if payload.remote_ok is not None:
        profile.remote_ok = payload.remote_ok
    if payload.salary_min is not None:
        profile.salary_min = payload.salary_min
    if payload.experience_level is not None:
        profile.experience_level = payload.experience_level
    if payload.goals is not None:
        profile.goals = payload.goals.strip() or None

    await session.commit()
    return _serialize_profile(profile)


@router.patch("/memories/{memory_id}", response_model=MemoryItemResponse)
async def patch_memory(
    memory_id: uuid.UUID,
    payload: MemoryPatchRequest,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
) -> MemoryItemResponse:
    user_id = resolve_anonymous_user_id(request)
    mem = await session.get(Memory, memory_id)
    if mem is None or mem.user_id != user_id:
        raise HTTPException(status_code=404, detail="Memory not found")

    mem.text = payload.text.strip()
    if payload.type is not None:
        mem.type = payload.type
    mem.embedding = embed_text(mem.text)
    mem.last_seen = datetime.now(UTC)
    await session.commit()

    return MemoryItemResponse(
        id=mem.id,
        type=mem.type,  # type: ignore[arg-type]
        text=mem.text,
        last_seen=mem.last_seen,
        created_at=mem.created_at,
    )


@router.delete("/memories/{memory_id}")
async def delete_memory(
    memory_id: uuid.UUID,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, bool]:
    user_id = resolve_anonymous_user_id(request)
    mem = await session.get(Memory, memory_id)
    if mem is None or mem.user_id != user_id:
        raise HTTPException(status_code=404, detail="Memory not found")

    await session.delete(mem)
    await session.commit()
    return {"deleted": True}
