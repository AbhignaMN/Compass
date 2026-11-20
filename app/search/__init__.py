"""Hybrid retrieval, weighted job ranking, and SQL skill-gap analysis."""

from app.search.ranking import fetch_user_interactions, rank_jobs
from app.search.retrieval import hybrid_search, reciprocal_rank_fusion
from app.search.schemas import (
    JobSearchFilters,
    JobSkillInfo,
    RankedJob,
    ScoreBreakdown,
    SearchCandidate,
    SkillGapItem,
    SkillGapResult,
)
from app.search.skill_gap import compute_skill_gap

__all__ = [
    "JobSearchFilters",
    "JobSkillInfo",
    "RankedJob",
    "ScoreBreakdown",
    "SearchCandidate",
    "SkillGapItem",
    "SkillGapResult",
    "compute_skill_gap",
    "fetch_user_interactions",
    "hybrid_search",
    "rank_jobs",
    "reciprocal_rank_fusion",
]
