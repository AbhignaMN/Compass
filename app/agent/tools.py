"""Pydantic-validated tool definitions and async DB executors for Compass."""

import json
import logging
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, ValidationError
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.schemas import (
    BuildRoadmapInput,
    CompareJobsInput,
    InterviewPrepOutput,
    InterviewPrepTipsInput,
    JobComparisonOutput,
    MemoryHit,
    ProfileSnapshot,
    RankJobsInput,
    RecallMemoryInput,
    RoadmapPlan,
    SearchJobsInput,
    SkillGapInput,
    TailoredResumeOutput,
    TailorResumeSummaryInput,
    ToolTraceEntry,
    UpdateProfileInput,
)
from app.db.models import Job, Profile, User
from app.search.ranking import fetch_user_interactions, rank_jobs
from app.search.retrieval import hybrid_search, hydrate_candidates
from app.search.schemas import RankedJob, SearchCandidate, SkillGapResult
from app.search.skill_gap import compute_skill_gap
from app.services.embeddings import embed_text
from app.services.skills import normalize_skill_name

logger = logging.getLogger(__name__)


@dataclass
class ToolSpec:
    name: str
    description: str
    input_model: type[BaseModel]


TOOL_SPECS: list[ToolSpec] = [
    ToolSpec(
        name="update_profile",
        description=(
            "Save or update structured user career profile facts (skills, interests, city, "
            "remote_ok, minimum monthly INR salary, experience_level, goals)."
        ),
        input_model=UpdateProfileInput,
    ),
    ToolSpec(
        name="search_jobs",
        description=(
            "Run hybrid semantic + keyword job search in Postgres with hard SQL filters "
            "(location, remote_only, salary_min in monthly INR, exclude_keywords)."
        ),
        input_model=SearchJobsInput,
    ),
    ToolSpec(
        name="rank_jobs",
        description=(
            "Rank candidate job_ids returned by search_jobs using user profile skills, "
            "preferences, freshness, and past interactions. Returns fit scores and breakdowns."
        ),
        input_model=RankJobsInput,
    ),
    ToolSpec(
        name="skill_gap",
        description=(
            "Run SQL skill-gap analysis for a specific job_id against the user's profile skills, "
            "returning matched skills and missing skills ordered by importance."
        ),
        input_model=SkillGapInput,
    ),
    ToolSpec(
        name="build_roadmap",
        description=(
            "Generate a structured week-by-week career learning roadmap with RAG citations from "
            "Compass career guides, measurable outcomes, and adjacent-role alternatives."
        ),
        input_model=BuildRoadmapInput,
    ),
    ToolSpec(
        name="recall_memory",
        description="Search the user's long-term memories (facts, preferences, goals) semantically.",
        input_model=RecallMemoryInput,
    ),
    ToolSpec(
        name="compare_jobs",
        description="Compare two specific job_ids side-by-side on salary, location, skills, and trade-offs.",
        input_model=CompareJobsInput,
    ),
    ToolSpec(
        name="tailor_resume_summary",
        description=(
            "Generate an honest, ATS-friendly fresher resume summary and 3 bullet points tailored "
            "to a specific job_id using only the user's real skills and highlights."
        ),
        input_model=TailorResumeSummaryInput,
    ),
    ToolSpec(
        name="interview_prep_tips",
        description="Return focused technical & behavioral interview prep tips for a role or job_id.",
        input_model=InterviewPrepTipsInput,
    ),
]

TOOL_SPEC_BY_NAME: dict[str, ToolSpec] = {spec.name: spec for spec in TOOL_SPECS}


def get_llm_tool_definitions() -> list[dict[str, Any]]:
    """Export all tools with Pydantic-generated JSON Schemas for Claude/Groq/Gemini."""
    return [
        {
            "name": spec.name,
            "description": spec.description,
            "input_schema": spec.input_model.model_json_schema(),
        }
        for spec in TOOL_SPECS
    ]


@dataclass
class TurnToolState:
    """Mutable per-turn state grounding recommendations strictly to DB tool results."""

    candidates_by_id: dict[uuid.UUID, SearchCandidate] = field(default_factory=dict)
    ranked_by_id: dict[uuid.UUID, RankedJob] = field(default_factory=dict)
    latest_ranked_jobs: list[RankedJob] = field(default_factory=list)
    latest_skill_gap: SkillGapResult | None = None
    latest_roadmap: RoadmapPlan | None = None
    profile: ProfileSnapshot | None = None
    trace: list[ToolTraceEntry] = field(default_factory=list)


RoadmapBuilderFn = Callable[[AsyncSession, uuid.UUID, str, int], Awaitable[RoadmapPlan]]


class ToolExecutor:
    """Validates tool arguments with Pydantic v2 and executes tools against Postgres."""

    def __init__(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        state: TurnToolState | None = None,
        roadmap_builder: RoadmapBuilderFn | None = None,
    ) -> None:
        self.session = session
        self.user_id = user_id
        self.state = state or TurnToolState()
        self.roadmap_builder = roadmap_builder

    async def execute(self, tool_name: str, raw_args: dict[str, Any]) -> tuple[str, bool]:
        """Validate & execute a tool call; returns (json_result_string, is_error)."""
        spec = TOOL_SPEC_BY_NAME.get(tool_name)
        if spec is None:
            msg = json.dumps({"error": f"Unknown tool '{tool_name}'."})
            self.state.trace.append(
                ToolTraceEntry(tool_name=tool_name, tool_input=raw_args, ok=False, summary="Unknown tool")
            )
            return msg, True

        try:
            validated = spec.input_model.model_validate(raw_args)
        except ValidationError as exc:
            err_payload = {
                "error": "Tool input validation failed",
                "details": exc.errors(include_url=False),
            }
            self.state.trace.append(
                ToolTraceEntry(
                    tool_name=tool_name,
                    tool_input=raw_args,
                    ok=False,
                    summary="Pydantic validation error",
                )
            )
            return json.dumps(err_payload, default=str), True

        try:
            handler = getattr(self, f"_tool_{tool_name}")
            output_payload, summary = await handler(validated)
            self.state.trace.append(
                ToolTraceEntry(
                    tool_name=tool_name,
                    tool_input=validated.model_dump(mode="json"),
                    ok=True,
                    summary=summary,
                )
            )
            return json.dumps(output_payload, default=str), False
        except Exception as exc:
            logger.exception("Tool %s failed", tool_name)
            self.state.trace.append(
                ToolTraceEntry(
                    tool_name=tool_name,
                    tool_input=validated.model_dump(mode="json"),
                    ok=False,
                    summary=f"Execution error: {exc}",
                )
            )
            return json.dumps({"error": f"Tool execution error: {exc}"}), True

    async def _ensure_user_and_profile(self) -> Profile:
        user = await self.session.get(User, self.user_id)
        if user is None:
            user = User(id=self.user_id)
            self.session.add(user)
            await self.session.flush()

        profile = await self.session.get(Profile, self.user_id)
        if profile is None:
            profile = Profile(user_id=self.user_id, skills=[], interests=[], remote_ok=True)
            self.session.add(profile)
            await self.session.flush()
        return profile

    def _to_profile_snapshot(self, profile: Profile) -> ProfileSnapshot:
        snap = ProfileSnapshot(
            user_id=profile.user_id,
            skills=list(profile.skills or []),
            interests=list(profile.interests or []),
            location_pref=profile.location_pref,
            remote_ok=bool(profile.remote_ok),
            salary_min=profile.salary_min,
            experience_level=profile.experience_level,
            goals=profile.goals,
        )
        self.state.profile = snap
        return snap

    async def _tool_update_profile(self, data: UpdateProfileInput) -> tuple[dict[str, Any], str]:
        profile = await self._ensure_user_and_profile()

        if data.skills is not None:
            normalized = [normalize_skill_name(s) for s in data.skills if s.strip()]
            if data.replace_skills:
                merged = list(dict.fromkeys(normalized))
            else:
                merged = list(dict.fromkeys([*(profile.skills or []), *normalized]))
            profile.skills = merged

        if data.interests is not None:
            profile.interests = list(
                dict.fromkeys(i.strip().lower() for i in data.interests if i.strip())
            )
        if data.location_pref is not None:
            profile.location_pref = data.location_pref.strip()
        if data.remote_ok is not None:
            profile.remote_ok = data.remote_ok
        if data.salary_min is not None:
            profile.salary_min = data.salary_min
        if data.experience_level is not None:
            profile.experience_level = data.experience_level
        if data.goals is not None:
            profile.goals = data.goals.strip()

        await self.session.flush()
        snap = self._to_profile_snapshot(profile)
        return snap.model_dump(mode="json"), f"Updated profile ({len(snap.skills)} skills)"

    async def _tool_search_jobs(self, data: SearchJobsInput) -> tuple[dict[str, Any], str]:
        candidates = await hybrid_search(
            self.session,
            query=data.query,
            filters=data.filters,
            k=data.k,
        )
        for cand in candidates:
            self.state.candidates_by_id[cand.job_id] = cand

        compact = [
            {
                "job_id": str(c.job_id),
                "title": c.title,
                "company": c.company,
                "location": c.location,
                "remote": c.remote,
                "salary_min": c.salary_min,
                "salary_max": c.salary_max,
                "skills": [s.name for s in c.skills[:8]],
                "rrf_score": round(c.rrf_score, 5),
                "vector_similarity": round(c.vector_similarity, 4),
            }
            for c in candidates
        ]
        return {"count": len(compact), "candidates": compact}, f"Found {len(compact)} candidate jobs"

    async def _tool_rank_jobs(self, data: RankJobsInput) -> tuple[dict[str, Any], str]:
        profile = await self._ensure_user_and_profile()
        self._to_profile_snapshot(profile)

        missing_ids = [cid for cid in data.candidate_ids if cid not in self.state.candidates_by_id]
        if missing_ids:
            hydrated = await hydrate_candidates(self.session, missing_ids, {}, {}, {})
            for cand in hydrated:
                self.state.candidates_by_id[cand.job_id] = cand

        candidates = [
            self.state.candidates_by_id[cid]
            for cid in data.candidate_ids
            if cid in self.state.candidates_by_id
        ]
        interactions = await fetch_user_interactions(
            self.session, self.user_id, [c.job_id for c in candidates]
        )
        ranked = rank_jobs(profile, candidates, interaction_events=interactions)[: data.top_k]

        self.state.latest_ranked_jobs = ranked
        for item in ranked:
            self.state.ranked_by_id[item.job_id] = item

        return {
            "count": len(ranked),
            "ranked_jobs": [r.model_dump(mode="json") for r in ranked],
        }, f"Ranked top {len(ranked)} jobs"

    async def _tool_skill_gap(self, data: SkillGapInput) -> tuple[dict[str, Any], str]:
        gap = await compute_skill_gap(self.session, self.user_id, data.job_id)
        if gap is None:
            return {"error": f"Job {data.job_id} not found"}, "Job not found"
        self.state.latest_skill_gap = gap
        return gap.model_dump(mode="json"), f"Skill gap: {len(gap.missing_skills)} missing"

    async def _tool_recall_memory(self, data: RecallMemoryInput) -> tuple[dict[str, Any], str]:
        qvec = "[" + ",".join(f"{x:.6f}" for x in embed_text(data.query)) + "]"
        sql = text(
            """
            SELECT id, type, text,
                   COALESCE(1.0 - (embedding <=> CAST(:qvec AS vector)), 0.0) AS similarity
            FROM memories
            WHERE user_id = :user_id
            ORDER BY embedding <=> CAST(:qvec AS vector) ASC NULLS LAST, last_seen DESC
            LIMIT :k
            """
        )
        rows = (
            await self.session.execute(sql, {"user_id": self.user_id, "qvec": qvec, "k": data.k})
        ).all()
        hits = [
            MemoryHit(
                id=row.id,
                type=row.type,
                text=row.text,
                similarity=round(float(row.similarity or 0.0), 4),
            )
            for row in rows
        ]
        return {"memories": [h.model_dump(mode="json") for h in hits]}, f"Recalled {len(hits)} memories"

    async def _tool_build_roadmap(self, data: BuildRoadmapInput) -> tuple[dict[str, Any], str]:
        if self.roadmap_builder is None:
            from app.agent.roadmap import build_rag_roadmap

            plan = await build_rag_roadmap(
                session=self.session,
                user_id=self.user_id,
                target_role=data.target_role,
                weeks=data.weeks,
            )
        else:
            plan = await self.roadmap_builder(
                self.session, self.user_id, data.target_role, data.weeks
            )
        self.state.latest_roadmap = plan
        return plan.model_dump(mode="json"), f"Built {len(plan.weeks)}-week roadmap for {plan.target_role}"

    async def _tool_compare_jobs(self, data: CompareJobsInput) -> tuple[dict[str, Any], str]:
        profile = await self._ensure_user_and_profile()
        ids = [data.job_id_a, data.job_id_b]
        missing = [jid for jid in ids if jid not in self.state.candidates_by_id]
        if missing:
            for cand in await hydrate_candidates(self.session, missing, {}, {}, {}):
                self.state.candidates_by_id[cand.job_id] = cand

        if data.job_id_a not in self.state.candidates_by_id or data.job_id_b not in self.state.candidates_by_id:
            return {"error": "One or both job_ids could not be found."}, "Comparison missing job"

        cands = [self.state.candidates_by_id[data.job_id_a], self.state.candidates_by_id[data.job_id_b]]
        interactions = await fetch_user_interactions(self.session, self.user_id, ids)
        ranked_map = {r.job_id: r for r in rank_jobs(profile, cands, interaction_events=interactions)}
        ja, jb = ranked_map[data.job_id_a], ranked_map[data.job_id_b]
        self.state.ranked_by_id[ja.job_id] = ja
        self.state.ranked_by_id[jb.job_id] = jb

        def _fmt_sal(j: RankedJob) -> str:
            if j.salary_min and j.salary_max:
                return f"₹{j.salary_min // 1000}K–{j.salary_max // 1000}K/mo"
            return "Undisclosed"

        salary_cmp = f"{ja.company}: {_fmt_sal(ja)} vs {jb.company}: {_fmt_sal(jb)}."
        loc_cmp = (
            f"{ja.company} is in {ja.location} ({'Remote' if ja.remote else 'Hybrid/On-site'}) vs "
            f"{jb.company} in {jb.location} ({'Remote' if jb.remote else 'Hybrid/On-site'})."
        )
        skill_tradeoff = (
            f"{ja.company} needs {', '.join(ja.missing_skills[:3]) or 'no major gaps'}; "
            f"{jb.company} needs {', '.join(jb.missing_skills[:3]) or 'no major gaps'}."
        )
        better = ja if ja.fit_score_pct >= jb.fit_score_pct else jb
        rec = (
            f"{better.title} at {better.company} scores higher overall ({better.fit_score_pct}%, "
            f"{better.fit_label}) based on your current skills and preferences."
        )

        out = JobComparisonOutput(
            job_a=ja,
            job_b=jb,
            salary_comparison=salary_cmp,
            location_comparison=loc_cmp,
            skill_tradeoff=skill_tradeoff,
            recommendation=rec,
        )
        return out.model_dump(mode="json"), f"Compared {ja.company} vs {jb.company}"

    async def _tool_tailor_resume_summary(
        self, data: TailorResumeSummaryInput
    ) -> tuple[dict[str, Any], str]:
        profile = await self._ensure_user_and_profile()
        job = await self.session.get(Job, data.job_id)
        if job is None:
            return {"error": f"Job {data.job_id} not found"}, "Job not found"

        gap = await compute_skill_gap(self.session, self.user_id, data.job_id)
        matched = gap.matched_skills if gap else list(profile.skills or [])
        missing = [m.skill for m in gap.missing_skills[:4]] if gap else []
        level = (profile.experience_level or "fresher").title()

        skill_phrase = ", ".join(matched[:5]) if matched else "software fundamentals"
        summary = (
            f"{level} targeting {job.title} at {job.company}, bringing hands-on projects in "
            f"{skill_phrase} with a focus on clean, tested, production-ready deliverables."
        )
        bullets = [
            f"Built end-to-end projects using {skill_phrase}, emphasizing readable code and automated verification.",
        ]
        if data.user_highlights:
            for hi in data.user_highlights[:2]:
                bullets.append(f"Applied relevant experience ({hi.strip()}) aligned with {job.title} responsibilities.")
        else:
            bullets.append(
                f"Collaborated with Git workflows and structured problem-solving directly relevant to {job.company}'s stack."
            )
        if missing:
            bullets.append(
                f"Currently ramping up on {', '.join(missing[:2])} through hands-on mini-projects to close role gaps quickly."
            )

        out = TailoredResumeOutput(
            job_id=job.id,
            job_title=job.title,
            company=job.company,
            matched_skills_used=matched,
            gaps_to_address_honestly=missing,
            summary=summary,
            bullet_points=bullets[:3],
        )
        return out.model_dump(mode="json"), f"Tailored resume summary for {job.title}"

    async def _tool_interview_prep_tips(
        self, data: InterviewPrepTipsInput
    ) -> tuple[dict[str, Any], str]:
        missing_skills: list[str] = []
        if data.job_id is not None:
            gap = await compute_skill_gap(self.session, self.user_id, data.job_id)
            if gap:
                missing_skills = [m.skill for m in gap.missing_skills[:4]]

        role_lower = data.role.lower()
        if any(k in role_lower for k in ("ai", "ml", "llm", "nlp", "data scien")):
            topics = [
                "Embeddings, cosine similarity vs keyword BM25, and hybrid RRF retrieval",
                "Structured outputs, tool-use agent loops, and hallucination guardrails",
                "Python coding, SQL joins/aggregations, and evaluation metrics (Recall@K, nDCG)",
            ]
            questions = [
                "How would you evaluate a RAG system and debug low retrieval recall?",
                "Why choose HNSW over IVFFlat in pgvector when the index updates frequently?",
                "Walk through a failure mode in your AI project and how you mitigated it.",
            ]
        elif any(k in role_lower for k in ("backend", "api", "python", "java", "node", "go")):
            topics = [
                "Relational schema design, B-tree/GIN indexes, and SQL EXPLAIN plans",
                "REST API design, status codes, auth (JWT/OAuth2), and rate limiting",
                "Core DSA (hash maps, trees, graphs) plus async I/O & caching trade-offs",
            ]
            questions = [
                "How do you diagnose and fix an N+1 query problem in an API endpoint?",
                "Explain ACID transactions and when you would add a composite index.",
                "Design a rate-limited URL shortener or job search API for 10K users.",
            ]
        elif any(k in role_lower for k in ("data", "analyst", "bi")):
            topics = [
                "SQL window functions, CTEs, cohort retention, and funnel conversion queries",
                "Pandas data cleaning, A/B testing (p-values, guardrails), and statistics",
                "Root-cause analysis (RCA) and translating charts into business actions",
            ]
            questions = [
                "Orders dropped 12% in Bengaluru this week — how do you investigate?",
                "Write a SQL query to compute 7-day user retention by signup cohort.",
                "How do you decide sample size and stopping rules for an A/B test?",
            ]
        elif any(k in role_lower for k in ("security", "soc", "appsec", "cyber")):
            topics = [
                "TCP/IP, HTTP/TLS handshakes, Linux permissions, and log analysis",
                "OWASP Top 10 (SQLi, XSS, IDOR, SSRF, broken auth) and secure code fixes",
                "SIEM alert triage and incident response playbooks",
            ]
            questions = [
                "Walk through how SQL injection happens and why parameterized queries stop it.",
                "You see 200 failed SSH logins followed by one success — what are your next 3 steps?",
                "Explain the difference between authentication, authorization, and IDOR.",
            ]
        elif any(k in role_lower for k in ("qa", "sdet", "test")):
            topics = [
                "Test design (boundary values, negative cases) and Page Object Model",
                "Playwright/Selenium flake prevention and REST API schema assertions",
                "SQL state verification and GitHub Actions CI test gates",
            ]
            questions = [
                "Write 6 test cases (including edge/negative) for a UPI payment flow.",
                "Why are hardcoded sleeps bad in UI tests, and how do you eliminate flakiness?",
                "How would you validate both the HTTP response and DB state in an API test?",
            ]
        else:
            topics = [
                "Core fundamentals for the role's primary language/tooling and Git",
                "Walking through one end-to-end project (architecture, trade-offs, testing)",
                "Clear STAR-format behavioral stories showing ownership and debugging",
            ]
            questions = [
                "Walk me through the hardest bug you solved in your best project.",
                "What trade-offs did you make in your architecture, and what would you improve next?",
                "How do you prioritize when requirements are ambiguous?",
            ]

        tip = (
            f"Brush up on {', '.join(missing_skills[:2])} with a 2-hour hands-on mini-example before interviewing."
            if missing_skills
            else "Prepare a crisp 90-second walkthrough of your strongest deployed project and its measurable outcomes."
        )
        out = InterviewPrepOutput(
            role=data.role,
            focus_topics=topics,
            practice_questions=questions,
            quick_win_tip=tip,
            missing_skills_to_brush_up=missing_skills,
        )
        return out.model_dump(mode="json"), f"Prepared interview tips for {data.role}"
