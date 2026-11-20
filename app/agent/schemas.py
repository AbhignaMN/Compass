"""Pydantic v2 input/output schemas for every agent tool and structured agent responses."""

import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.search.schemas import JobSearchFilters, RankedJob, SkillGapResult

# ---------------------------------------------------------------------------
# Tool input schemas
# ---------------------------------------------------------------------------


class UpdateProfileInput(BaseModel):
    skills: list[str] | None = Field(
        default=None,
        description="Canonical or raw skills the user knows (merged with existing skills unless replace_skills=true).",
    )
    replace_skills: bool = Field(
        default=False,
        description="Set true only if replacing the entire skills list.",
    )
    interests: list[str] | None = Field(
        default=None,
        description="Preferred career tracks/domains, e.g. ['ai_ml', 'backend', 'python'].",
    )
    location_pref: str | None = Field(
        default=None,
        description="Preferred city or 'Remote', e.g. 'Bengaluru'.",
    )
    remote_ok: bool | None = Field(default=None, description="Whether remote roles are acceptable.")
    salary_min: int | None = Field(
        default=None,
        ge=0,
        description="Minimum expected monthly salary in INR (e.g. 50000 for 50K/month).",
    )
    experience_level: Literal["student", "intern", "fresher", "junior"] | None = Field(
        default=None,
        description="Current career stage.",
    )
    goals: str | None = Field(
        default=None,
        description="Short summary of the user's career goals or dislikes (e.g. 'no sales').",
    )


class SearchJobsInput(BaseModel):
    query: str = Field(
        min_length=2,
        description="Semantic + keyword search query describing desired role and skills.",
    )
    filters: JobSearchFilters = Field(default_factory=JobSearchFilters)
    k: int = Field(default=15, ge=1, le=50)


class RankJobsInput(BaseModel):
    candidate_ids: list[uuid.UUID] = Field(
        min_length=1,
        max_length=50,
        description="Job UUIDs previously returned by search_jobs.",
    )
    top_k: int = Field(default=5, ge=1, le=20)


class SkillGapInput(BaseModel):
    job_id: uuid.UUID = Field(description="Job UUID from search_jobs or rank_jobs.")


class RecallMemoryInput(BaseModel):
    query: str = Field(min_length=2, description="Topic to recall from user long-term memory.")
    k: int = Field(default=5, ge=1, le=15)


class BuildRoadmapInput(BaseModel):
    target_role: str = Field(
        min_length=2,
        description="Target role name, e.g. 'AI / LLM Engineer Intern' or 'Backend Engineer (Python)'.",
    )
    weeks: int = Field(default=4, ge=2, le=8)


class CompareJobsInput(BaseModel):
    job_id_a: uuid.UUID = Field(description="First job UUID to compare.")
    job_id_b: uuid.UUID = Field(description="Second job UUID to compare.")


class TailorResumeSummaryInput(BaseModel):
    job_id: uuid.UUID = Field(description="Target job UUID to tailor the resume summary for.")
    user_highlights: list[str] = Field(
        default_factory=list,
        description="Optional projects, coursework, or internship highlights mentioned by the user.",
    )


class InterviewPrepTipsInput(BaseModel):
    role: str = Field(min_length=2, description="Target role name.")
    job_id: uuid.UUID | None = Field(
        default=None,
        description="Optional specific job UUID to customize prep topics around missing skills.",
    )


# ---------------------------------------------------------------------------
# Tool output schemas
# ---------------------------------------------------------------------------


class ProfileSnapshot(BaseModel):
    user_id: uuid.UUID
    skills: list[str] = Field(default_factory=list)
    interests: list[str] = Field(default_factory=list)
    location_pref: str | None = None
    remote_ok: bool = True
    salary_min: int | None = None
    experience_level: str | None = None
    goals: str | None = None


class MemoryHit(BaseModel):
    id: uuid.UUID
    type: Literal["fact", "preference", "goal"]
    text: str
    similarity: float = 0.0


class JobComparisonOutput(BaseModel):
    job_a: RankedJob
    job_b: RankedJob
    salary_comparison: str
    location_comparison: str
    skill_tradeoff: str
    recommendation: str


class TailoredResumeOutput(BaseModel):
    job_id: uuid.UUID
    job_title: str
    company: str
    matched_skills_used: list[str]
    gaps_to_address_honestly: list[str]
    summary: str
    bullet_points: list[str]


class InterviewPrepOutput(BaseModel):
    role: str
    focus_topics: list[str]
    practice_questions: list[str]
    quick_win_tip: str
    missing_skills_to_brush_up: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Roadmap schema (Section 5 exact fields)
# ---------------------------------------------------------------------------


class RoadmapWeek(BaseModel):
    week: int = Field(ge=1)
    goal: str
    resource: str
    project: str
    outcome: str


class RoadmapAlternative(BaseModel):
    role: str
    tradeoff: str


class RoadmapSource(BaseModel):
    source_url: str
    title: str


class RoadmapPlan(BaseModel):
    target_role: str
    fit_score: int = Field(ge=0, le=100)
    ranked_gaps: list[str] = Field(default_factory=list)
    weeks: list[RoadmapWeek] = Field(min_length=1)
    apply_when: str
    alternatives: list[RoadmapAlternative] = Field(min_length=1)
    sources: list[RoadmapSource] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Structured final agent output & turn trace
# ---------------------------------------------------------------------------


class StructuredMentorReply(BaseModel):
    """Schema-validated final response returned by the LLM after tool execution."""

    reply: str = Field(
        min_length=1,
        description="Warm, concise career mentor response (2-6 short sentences, plain language).",
    )
    suggested_replies: list[str] = Field(
        default_factory=list,
        max_length=3,
        description="2 or 3 short, tappable next-step chips for the user.",
    )
    referenced_job_ids: list[str] = Field(
        default_factory=list,
        description="Exact job_id UUID strings from tool outputs that are being recommended.",
    )


class ToolTraceEntry(BaseModel):
    tool_name: str
    tool_input: dict[str, Any]
    ok: bool
    summary: str


class AgentTurnResult(BaseModel):
    conversation_id: uuid.UUID
    user_id: uuid.UUID
    reply: str
    suggested_replies: list[str] = Field(default_factory=list)
    recommended_jobs: list[RankedJob] = Field(default_factory=list)
    skill_gap: SkillGapResult | None = None
    roadmap: RoadmapPlan | None = None
    profile: ProfileSnapshot | None = None
    tool_trace: list[ToolTraceEntry] = Field(default_factory=list)
