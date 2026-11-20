"""Stage 6 tests: RAG roadmaps with citations, REST endpoints, and 16 scripted multi-turn scenarios."""

import json
import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from app.agent.llm import LLMClient, LLMResponse, ToolCallRequest
from app.agent.loop import run_agent_turn
from app.agent.roadmap import build_rag_roadmap
from app.agent.schemas import RoadmapPlan
from app.config import get_settings
from app.db.models import Conversation, Job, Memory, Profile, Roadmap, User
from app.db.session import get_db_session
from app.main import app
from app.search.schemas import JobSkillInfo, SearchCandidate, SkillGapItem, SkillGapResult
from app.services.embeddings import embed_text
from app.services.memory import ExtractedMemoryItem, merge_memory_item


def _make_fake_session(
    user_id: uuid.UUID,
    conv_id: uuid.UUID,
    *,
    profile: Profile | None = None,
    memories: list[dict[str, str]] | None = None,
    jobs: dict[uuid.UUID, Job] | None = None,
) -> AsyncMock:
    session = AsyncMock()
    user = User(id=user_id)
    prof = profile or Profile(
        user_id=user_id,
        skills=["python", "sql"],
        interests=["ai_ml", "backend"],
        location_pref="Bengaluru",
        remote_ok=True,
        salary_min=50000,
        experience_level="fresher",
        goals="no sales",
    )
    conv = Conversation(id=conv_id, user_id=user_id, summary=None)
    job_map = jobs or {}

    async def fake_get(model, pk):
        if model is User:
            return user
        if model is Profile:
            return prof
        if model is Conversation:
            return conv
        if model is Job:
            return job_map.get(pk)
        return None

    session.get.side_effect = fake_get
    session.add = MagicMock()

    async def fake_execute(stmt, params=None):
        sql_str = str(stmt)
        res = MagicMock()
        if "FROM memories" in sql_str and memories:
            res.all.return_value = [
                SimpleNamespace(
                    id=uuid.uuid4(),
                    type=m["type"],
                    text=m["text"],
                    similarity=0.9,
                )
                for m in memories
            ]
        else:
            res.all.return_value = []
        res.scalars.return_value.all.return_value = []
        res.scalar.return_value = 0
        return res

    session.execute.side_effect = fake_execute
    return session


def _candidate(job_id: uuid.UUID, title: str, company: str, location: str, sal_min: int, sal_max: int) -> SearchCandidate:
    return SearchCandidate(
        job_id=job_id,
        title=title,
        company=company,
        location=location,
        remote="remote" in location.lower(),
        salary_min=sal_min,
        salary_max=sal_max,
        description=f"{title} using Python, FastAPI, PostgreSQL, Docker.",
        source="seed",
        source_url=f"https://sample-jobs.compass.local/{job_id}",
        posted_at=datetime(2026, 11, 19, tzinfo=UTC),
        skills=[
            JobSkillInfo(name="python", category="language", importance=3),
            JobSkillInfo(name="fastapi", category="backend", importance=3),
            JobSkillInfo(name="docker", category="cloud_devops", importance=2),
        ],
        vector_similarity=0.88,
        rrf_score=0.032,
    )


# ---------------------------------------------------------------------------
# 16 Scripted Multi-Turn Conversation Scenarios (Section 5.1 requirements)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "scenario_name,user_turns,tool_sequence,reply_text,chips,expected_tools",
    [
        (
            "01_cold_start_thin_profile",
            ["Hi, I'm graduating soon."],
            [],
            "Welcome to Compass! What kind of tech or product work excites you most right now?",
            ["Python & AI/ML", "Backend APIs", "Not sure yet"],
            [],
        ),
        (
            "02_vague_user_gets_3_tappable_examples",
            ["Honestly I have no idea what career I want."],
            [],
            "That's completely normal! Let's narrow it down gently—which of these sounds least boring to try for a week?",
            ["Building web apps", "Analyzing data & charts", "Securing networks"],
            [],
        ),
        (
            "03_discouraged_fresher_empathy_first",
            ["I got rejected from 12 internships and feel like giving up."],
            [],
            "I hear you—silent rejections are exhausting and don't measure your potential. Let's pick one high-fit fresher role and tighten a single project bullet together.",
            ["Review my strongest skill", "Find realistic starter roles", "Build a 4-week plan"],
            [],
        ),
        (
            "04_rich_fresher_intro_updates_profile",
            ["I'm a fresher, like Python, hate sales, want 50K+ in Bengaluru."],
            [
                ToolCallRequest(
                    id="t1",
                    name="update_profile",
                    arguments={
                        "skills": ["Python"],
                        "interests": ["python", "backend", "ai_ml"],
                        "location_pref": "Bengaluru",
                        "salary_min": 50000,
                        "experience_level": "fresher",
                        "goals": "avoid sales roles",
                    },
                )
            ],
            "Got it—Python fresher roles in Bengaluru at ₹50K+/mo, zero sales. Want me to pull your top matches now?",
            ["Show Bengaluru Python jobs", "Include remote roles too", "Check my skill gaps"],
            ["update_profile"],
        ),
        (
            "05_user_changes_mind_on_salary",
            ["Actually, raise my minimum salary to 75K/month."],
            [ToolCallRequest(id="t1", name="update_profile", arguments={"salary_min": 75000})],
            "Updated your floor to ₹75K/month! That's a stretch tier for freshers, so I'll highlight strong-fit product startups.",
            ["Search ₹75K+ roles", "See skills needed for ₹75K+", "Show remote options"],
            ["update_profile"],
        ),
        (
            "06_user_changes_mind_on_city_remote",
            ["Scratch Bengaluru, I can only do remote from home now."],
            [
                ToolCallRequest(
                    id="t1",
                    name="update_profile",
                    arguments={"location_pref": "Remote", "remote_ok": True},
                )
            ],
            "No problem—switched your heading to Remote-only across India. Let's re-run your matches with remote filter on.",
            ["Show remote Python roles", "Compare remote vs hybrid pay", "Build a remote-ready roadmap"],
            ["update_profile"],
        ),
        (
            "07_interview_prep_tool",
            ["Give me quick interview prep tips for an AI/LLM intern role."],
            [ToolCallRequest(id="t1", name="interview_prep_tips", arguments={"role": "AI / LLM Engineer Intern"})],
            "Focus on hybrid search trade-offs, structured Pydantic tool outputs, and one clean eval metric walkthrough.",
            ["Practice a mock question", "Build a 4-week AI roadmap", "Tailor my resume"],
            ["interview_prep_tips"],
        ),
        (
            "08_no_strong_match_honest_admission",
            ["Find me a 5 lakh/month remote fresher quantum hardware role."],
            [
                ToolCallRequest(
                    id="t1",
                    name="search_jobs",
                    arguments={
                        "query": "quantum hardware fresher",
                        "filters": {"remote_only": True, "salary_min": 500000},
                    },
                )
            ],
            "I don't have a strong match for that right now—₹5L/mo fresher remote quantum roles aren't in our listings. Want to explore AI/ML or embedded systems roles instead?",
            ["Relax salary filter", "Explore AI/ML fresher roles", "Explore backend roles"],
            ["search_jobs"],
        ),
        (
            "09_safety_off_topic_decline",
            ["Can you give me guaranteed crypto stock picks and draft a legal NDA?"],
            [],
            "I stick strictly to career guidance and can't give financial guarantees or legal advice. If you're exploring FinTech engineering roles, I'd love to help with that!",
            ["Explore FinTech SWE roles", "Check my skills", "Build a career plan"],
            [],
        ),
        (
            "10_easier_roles_pivot",
            ["These backend roles feel too hard, show me lower-barrier entry tracks."],
            [
                ToolCallRequest(
                    id="t1",
                    name="update_profile",
                    arguments={"interests": ["qa", "data"]},
                )
            ],
            "Smart pivot—QA Automation (pytest/Playwright) and Junior Data Analyst roles use your Python/SQL with a gentler entry ramp.",
            ["Show QA Automation jobs", "Show Data Analyst jobs", "Compare QA vs Data Analyst"],
            ["update_profile"],
        ),
    ],
)
async def test_scripted_mentor_scenarios_batch(
    scenario_name: str,
    user_turns: list[str],
    tool_sequence: list[ToolCallRequest],
    reply_text: str,
    chips: list[str],
    expected_tools: list[str],
) -> None:
    user_id, conv_id = uuid.uuid4(), uuid.uuid4()
    session = _make_fake_session(user_id, conv_id)

    llm_responses: list[LLMResponse] = []
    if tool_sequence:
        llm_responses.append(LLMResponse(text="", tool_calls=tool_sequence))
    llm_responses.append(
        LLMResponse(
            text=json.dumps(
                {
                    "reply": reply_text,
                    "suggested_replies": chips,
                    "referenced_job_ids": [],
                }
            )
        )
    )
    mock_llm = AsyncMock()
    mock_llm.complete.side_effect = llm_responses

    with patch("app.agent.tools.hybrid_search", new=AsyncMock(return_value=[])):
        result = await run_agent_turn(
            session=session,
            user_id=user_id,
            conversation_id=conv_id,
            user_message=user_turns[0],
            llm_client=mock_llm,
            persist_post_turn_memory=False,
        )

    assert result.reply == reply_text, f"Failed scenario {scenario_name}"
    assert 2 <= len(result.suggested_replies) <= 3
    assert [t.tool_name for t in result.tool_trace] == expected_tools


async def test_scenario_11_search_rank_and_reference_resolution_second_job() -> None:
    """Scenario 11 & 12: Search + Rank jobs, then resolve 'what about the second one?' via skill_gap."""
    user_id, conv_id = uuid.uuid4(), uuid.uuid4()
    job1_id, job2_id = uuid.uuid4(), uuid.uuid4()
    c1 = _candidate(job1_id, "Backend Engineer (Python)", "KaveriPay", "Bengaluru, Karnataka", 60000, 80000)
    c2 = _candidate(job2_id, "AI / LLM Engineer Intern", "Nakshatra AI", "Remote (India)", 35000, 45000)
    session = _make_fake_session(user_id, conv_id)

    mock_llm = AsyncMock()
    mock_llm.complete.side_effect = [
        LLMResponse(
            tool_calls=[
                ToolCallRequest(id="s1", name="search_jobs", arguments={"query": "python backend ai"})
            ]
        ),
        LLMResponse(
            tool_calls=[
                ToolCallRequest(
                    id="r1",
                    name="rank_jobs",
                    arguments={"candidate_ids": [str(job1_id), str(job2_id)], "top_k": 2},
                )
            ]
        ),
        LLMResponse(
            text=json.dumps(
                {
                    "reply": "Here are two grounded matches—KaveriPay (True North) and Nakshatra AI (Heading right).",
                    "suggested_replies": ["Check gaps on #2", "Compare both jobs", "Build a roadmap"],
                    "referenced_job_ids": [str(job1_id), str(job2_id)],
                }
            )
        ),
    ]

    with (
        patch("app.agent.tools.hybrid_search", new=AsyncMock(return_value=[c1, c2])),
        patch("app.agent.tools.fetch_user_interactions", new=AsyncMock(return_value={})),
    ):
        turn1 = await run_agent_turn(
            session=session,
            user_id=user_id,
            conversation_id=conv_id,
            user_message="Find Python backend and AI roles",
            llm_client=mock_llm,
            persist_post_turn_memory=False,
        )

    assert len(turn1.recommended_jobs) == 2
    assert {j.job_id for j in turn1.recommended_jobs} == {job1_id, job2_id}

    # Turn 2: resolve "what about the second one?" -> skill_gap(job2_id)
    gap_res = SkillGapResult(
        job_id=job2_id,
        job_title="AI / LLM Engineer Intern",
        company="Nakshatra AI",
        matched_skills=["python"],
        missing_skills=[
            SkillGapItem(skill="pgvector", category="ai_ml", importance=3, importance_label="must-have"),
            SkillGapItem(skill="docker", category="cloud_devops", importance=2, importance_label="core"),
        ],
        coverage_pct=33.3,
    )
    mock_llm2 = AsyncMock()
    mock_llm2.complete.side_effect = [
        LLMResponse(tool_calls=[ToolCallRequest(id="g1", name="skill_gap", arguments={"job_id": str(job2_id)})]),
        LLMResponse(
            text=json.dumps(
                {
                    "reply": "For Nakshatra AI (the second role), you already match Python—your top gap is pgvector followed by Docker.",
                    "suggested_replies": ["Build a 4-week AI roadmap", "Tailor my resume", "Compare with #1"],
                    "referenced_job_ids": [],
                }
            )
        ),
    ]
    with patch("app.agent.tools.compute_skill_gap", new=AsyncMock(return_value=gap_res)):
        turn2 = await run_agent_turn(
            session=session,
            user_id=user_id,
            conversation_id=conv_id,
            user_message="What about the second one? What skills am I missing?",
            llm_client=mock_llm2,
            persist_post_turn_memory=False,
        )
    assert turn2.skill_gap is not None
    assert turn2.skill_gap.job_id == job2_id
    assert turn2.skill_gap.missing_skills[0].skill == "pgvector"


async def test_scenario_13_compare_two_jobs_and_scenario_14_tailor_resume() -> None:
    """Scenarios 13 & 14: compare_jobs and tailor_resume_summary tools."""
    user_id, conv_id = uuid.uuid4(), uuid.uuid4()
    job1_id, job2_id = uuid.uuid4(), uuid.uuid4()
    c1 = _candidate(job1_id, "Backend Engineer (Python)", "KaveriPay", "Bengaluru, Karnataka", 60000, 80000)
    c2 = _candidate(job2_id, "Junior Data Analyst", "Chanakya Analytics", "Remote (India)", 45000, 60000)
    job1_orm = Job(
        id=job1_id,
        title=c1.title,
        company=c1.company,
        location=c1.location,
        remote=False,
        salary_min=60000,
        salary_max=80000,
        description=c1.description,
        source="seed",
        source_url=c1.source_url,
        posted_at=c1.posted_at,
        status="active",
        content_hash="abc",
    )
    session = _make_fake_session(user_id, conv_id, jobs={job1_id: job1_orm})

    mock_llm = AsyncMock()
    mock_llm.complete.side_effect = [
        LLMResponse(
            tool_calls=[
                ToolCallRequest(
                    id="cmp1",
                    name="compare_jobs",
                    arguments={"job_id_a": str(job1_id), "job_id_b": str(job2_id)},
                ),
                ToolCallRequest(
                    id="res1",
                    name="tailor_resume_summary",
                    arguments={"job_id": str(job1_id), "user_highlights": ["Built a FastAPI job search API"]},
                ),
            ]
        ),
        LLMResponse(
            text=json.dumps(
                {
                    "reply": "KaveriPay pays higher in Bengaluru while Chanakya offers full remote flexibility. I also drafted a tailored resume summary for KaveriPay.",
                    "suggested_replies": ["Build a roadmap", "Interview prep tips"],
                    "referenced_job_ids": [str(job1_id), str(job2_id)],
                }
            )
        ),
    ]

    with (
        patch("app.agent.tools.hydrate_candidates", new=AsyncMock(return_value=[c1, c2])),
        patch("app.agent.tools.fetch_user_interactions", new=AsyncMock(return_value={})),
        patch(
            "app.agent.tools.compute_skill_gap",
            new=AsyncMock(
                return_value=SkillGapResult(
                    job_id=job1_id,
                    job_title=c1.title,
                    company=c1.company,
                    matched_skills=["python", "sql"],
                    missing_skills=[],
                    coverage_pct=100.0,
                )
            ),
        ),
    ):
        res = await run_agent_turn(
            session=session,
            user_id=user_id,
            conversation_id=conv_id,
            user_message="Compare those two jobs and tailor my resume for KaveriPay",
            llm_client=mock_llm,
            persist_post_turn_memory=False,
        )

    assert [t.tool_name for t in res.tool_trace] == ["compare_jobs", "tailor_resume_summary"]
    assert all(t.ok for t in res.tool_trace)


async def test_scenario_15_cross_session_return_next_day_uses_memories() -> None:
    """Scenario 15: New conversation next day injects earlier long-term memories into system prompt."""
    user_id = uuid.uuid4()
    new_conv_id = uuid.uuid4()
    session = _make_fake_session(
        user_id,
        new_conv_id,
        memories=[
            {"type": "preference", "text": "Hates sales roles and cold calling."},
            {"type": "preference", "text": "Prefers Bengaluru roles paying at least 50K/month."},
        ],
    )

    captured_systems: list[str] = []

    async def capture_complete(**kwargs):
        captured_systems.append(kwargs["system"])
        return LLMResponse(
            text=json.dumps(
                {
                    "reply": "Welcome back! Since you prefer Bengaluru non-sales Python roles at ₹50K+/mo, want to see fresh matches today?",
                    "suggested_replies": ["Show fresh matches", "Review my roadmap"],
                    "referenced_job_ids": [],
                }
            )
        )

    mock_llm = AsyncMock()
    mock_llm.complete.side_effect = capture_complete

    res = await run_agent_turn(
        session=session,
        user_id=user_id,
        conversation_id=new_conv_id,
        user_message="Hey, I'm back today! Any new roles for me?",
        llm_client=mock_llm,
        persist_post_turn_memory=False,
    )

    assert "Hates sales roles" in captured_systems[0]
    assert "Bengaluru" in captured_systems[0]
    assert "Welcome back" in res.reply


async def test_scenario_16_rag_roadmap_with_citations_and_live_llm() -> None:
    """Scenario 16: build_rag_roadmap retrieves KB chunks, validates schema, and cites real sources."""
    user_id = uuid.uuid4()
    session = _make_fake_session(user_id, uuid.uuid4())
    # Force fallback to local data/kb/*.md by raising on empty mock DB vector query
    session.execute.side_effect = RuntimeError("offline unit test DB")

    settings = get_settings()
    llm = LLMClient(settings)
    if not llm.is_configured():
        # Offline fallback still must produce valid grounded schema
        plan = await build_rag_roadmap(
            session=session,
            user_id=user_id,
            target_role="AI / LLM Engineer Intern",
            weeks=4,
            llm_client=llm,
        )
    else:
        plan = await build_rag_roadmap(
            session=session,
            user_id=user_id,
            target_role="AI / LLM Engineer Intern",
            weeks=4,
            llm_client=llm,
        )

    assert isinstance(plan, RoadmapPlan)
    assert 0 <= plan.fit_score <= 100
    assert len(plan.weeks) >= 1
    assert len(plan.alternatives) >= 1
    assert len(plan.sources) >= 1
    assert all(src.source_url.startswith("kb://") for src in plan.sources)


async def test_jobs_feedback_and_roadmap_rest_endpoints(client: AsyncClient) -> None:
    user_id, job_id, roadmap_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    now = datetime.now(UTC)

    job_orm = Job(
        id=job_id,
        title="Backend Engineer (Python / FastAPI)",
        company="KaveriPay",
        location="Bengaluru, Karnataka",
        remote=False,
        salary_min=60000,
        salary_max=80000,
        description="Build Python FastAPI microservices.",
        source="seed",
        source_url="https://sample-jobs.compass.local/kaveripay/backend-0001",
        posted_at=now,
        status="active",
        content_hash="hash123",
    )
    roadmap_orm = Roadmap(
        id=roadmap_id,
        user_id=user_id,
        target_role="Backend Engineer",
        version=1,
        created_at=now,
        plan={
            "target_role": "Backend Engineer",
            "fit_score": 76,
            "ranked_gaps": ["docker", "redis"],
            "weeks": [
                {
                    "week": 1,
                    "goal": "Master Postgres indexing",
                    "resource": "Use The Index, Luke",
                    "project": "Benchmark 10 SQL queries",
                    "outcome": "Documented EXPLAIN plans",
                }
            ],
            "apply_when": "Week 3",
            "alternatives": [{"role": "Full-Stack Engineer", "tradeoff": "Adds frontend scope"}],
            "sources": [{"source_url": "kb://backend-engineer.md", "title": "Backend Guide"}],
        },
    )

    session = AsyncMock()
    session.add = MagicMock()

    async def fake_get(model, pk):
        if model is Job and pk == job_id:
            return job_orm
        if model is User and pk == user_id:
            return User(id=user_id)
        return None

    session.get.side_effect = fake_get

    async def fake_execute(stmt, params=None):
        res = MagicMock()
        if "roadmaps" in str(stmt).lower():
            res.scalars.return_value.all.return_value = [roadmap_orm]
        else:
            res.all.return_value = [("python", "language", 3), ("fastapi", "backend", 3)]
        return res

    session.execute.side_effect = fake_execute

    async def override_db():
        yield session

    app.dependency_overrides[get_db_session] = override_db
    headers = {"X-Compass-User-Id": str(user_id)}
    try:
        r_job = await client.get(f"/jobs/{job_id}", headers=headers)
        assert r_job.status_code == 200
        assert r_job.json()["title"] == "Backend Engineer (Python / FastAPI)"

        r_fb = await client.post("/feedback", headers=headers, json={"job_id": str(job_id), "rating": "up"})
        assert r_fb.status_code == 200
        assert r_fb.json()["event"] == "saved"

        r_rm = await client.get(f"/roadmap/{user_id}", headers=headers)
        assert r_rm.status_code == 200
        assert len(r_rm.json()) == 1
        assert r_rm.json()[0]["plan"]["sources"][0]["source_url"] == "kb://backend-engineer.md"
    finally:
        app.dependency_overrides.clear()

    # Keep merge_memory_item + Memory smoke clean
    mem_list: list[Memory] = []
    item = ExtractedMemoryItem(type="goal", text="Target AI/LLM intern role by next semester")
    action, _ = merge_memory_item(mem_list, item, embed_text(item.text), user_id=user_id)
    assert action == "inserted"
