"""Pydantic v2 schemas for retrieval, ranking, and skill-gap analysis."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class JobSearchFilters(BaseModel):
    location: str | None = Field(default=None, description="City or region filter, e.g. Bengaluru")
    remote_only: bool | None = Field(default=None, description="If true, require remote=true")
    salary_min: int | None = Field(
        default=None, ge=0, description="Minimum monthly INR salary floor"
    )
    exclude_keywords: list[str] = Field(
        default_factory=list,
        description="Keywords to exclude from job titles (e.g. ['sales'])",
    )


class JobSkillInfo(BaseModel):
    name: str
    category: str
    importance: int = Field(ge=1, le=3)


class SearchCandidate(BaseModel):
    job_id: uuid.UUID
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
    skills: list[JobSkillInfo] = Field(default_factory=list)
    vector_rank: int | None = None
    keyword_rank: int | None = None
    vector_similarity: float = 0.0
    keyword_score: float = 0.0
    rrf_score: float = 0.0


class ScoreBreakdown(BaseModel):
    semantic: float
    skill_overlap: float
    preference_fit: float
    freshness: float
    interaction_adjustment: float = 0.0
    final_score: float


class RankedJob(BaseModel):
    job_id: uuid.UUID
    title: str
    company: str
    location: str
    remote: bool
    salary_min: int | None = None
    salary_max: int | None = None
    source: str
    source_url: str
    posted_at: datetime
    fit_score_pct: int = Field(ge=0, le=100)
    fit_label: Literal["True North", "Heading right", "Detour"]
    scores: ScoreBreakdown
    matched_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    why_it_fits: str


class SkillGapItem(BaseModel):
    skill: str
    category: str
    importance: int = Field(ge=1, le=3)
    importance_label: Literal["must-have", "core", "nice-to-have"]


class SkillGapResult(BaseModel):
    job_id: uuid.UUID
    job_title: str
    company: str
    matched_skills: list[str] = Field(default_factory=list)
    missing_skills: list[SkillGapItem] = Field(default_factory=list)
    coverage_pct: float = Field(ge=0.0, le=100.0)
