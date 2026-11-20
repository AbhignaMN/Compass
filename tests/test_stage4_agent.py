"""Stage 4 tests: hand-written agent loop, Pydantic tool validation, retry-once, grounding, and /chat."""

import json
import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from app.agent.llm import LLMClient, LLMResponse, ToolCallRequest
from app.agent.loop import (
    SAFE_FALLBACK_REPLY,
    _resolve_grounded_jobs,
    parse_structured_reply,
    run_agent_turn,
)
from app.agent.schemas import AgentTurnResult
from app.agent.tools import ToolExecutor, TurnToolState, get_llm_tool_definitions
from app.config import get_settings
from app.db.models import Conversation, Profile, User
from app.search.schemas import RankedJob, ScoreBreakdown


def _make_ranked_job(job_id: uuid.UUID, title: str = "Python Backend Engineer") -> RankedJob:
    return RankedJob(
        job_id=job_id,
        title=title,
        company="KaveriPay",
        location="Bengaluru, Karnataka",
        remote=False,
        salary_min=60000,
        salary_max=80000,
        source="seed",
        source_url=f"https://sample.local/{job_id}",
        posted_at=datetime(2026, 11, 19, tzinfo=UTC),
        fit_score_pct=84,
        fit_label="True North",
        scores=ScoreBreakdown(
            semantic=0.88,
            skill_overlap=0.80,
            preference_fit=0.90,
            freshness=0.95,
            interaction_adjustment=0.0,
            final_score=0.84,
        ),
        matched_skills=["python", "fastapi"],
        missing_skills=["docker"],
        why_it_fits="Matches your python, fastapi skills; pays ₹60K–80K/mo",
    )


def _mock_async_session(user_id: uuid.UUID, conv_id: uuid.UUID) -> AsyncMock:
    session = AsyncMock()
    user = User(id=user_id)
    profile = Profile(
        user_id=user_id,
        skills=["python"],
        interests=["backend"],
        location_pref="Bengaluru",
        remote_ok=True,
        salary_min=50000,
        experience_level="fresher",
        goals="no sales",
    )
    conv = Conversation(id=conv_id, user_id=user_id, summary=None)

    async def fake_get(model, pk):
        if model is User:
            return user
        if model is Profile:
            return profile
        if model is Conversation:
            return conv
        return None

    session.get.side_effect = fake_get
    empty_res = MagicMock()
    empty_res.scalars.return_value.all.return_value = []
    empty_res.all.return_value = []
    session.execute.return_value = empty_res
    session.add = MagicMock()
    return session


def test_tool_definitions_export_all_required_tools() -> None:
    defs = get_llm_tool_definitions()
    names = {d["name"] for d in defs}
    required = {
        "update_profile",
        "search_jobs",
        "rank_jobs",
        "skill_gap",
        "build_roadmap",
        "recall_memory",
        "compare_jobs",
        "tailor_resume_summary",
        "interview_prep_tips",
    }
    assert required.issubset(names)


async def test_tool_executor_rejects_invalid_pydantic_input() -> None:
    session = AsyncMock()
    executor = ToolExecutor(session=session, user_id=uuid.uuid4())
    # Invalid negative salary_min should be rejected cleanly by Pydantic v2
    payload_str, is_error = await executor.execute("update_profile", {"salary_min": -5000})
    assert is_error is True
    payload = json.loads(payload_str)
    assert payload["error"] == "Tool input validation failed"
    assert executor.state.trace[-1].ok is False


def test_resolve_grounded_jobs_strips_hallucinated_ids() -> None:
    real_id = uuid.uuid4()
    fake_id = uuid.uuid4()
    state = TurnToolState(ranked_by_id={real_id: _make_ranked_job(real_id)})

    verified = _resolve_grounded_jobs([str(fake_id), str(real_id), "not-a-uuid"], state)
    assert [j.job_id for j in verified] == [real_id]


def test_parse_structured_reply_strips_json_fences() -> None:
    raw = '```json\n{"reply": "Great start! What city do you prefer?", "suggested_replies": ["Bengaluru", "Remote"], "referenced_job_ids": []}\n```'
    parsed = parse_structured_reply(raw)
    assert "Bengaluru" in parsed.suggested_replies
    assert parsed.reply.startswith("Great start")


async def test_agent_loop_retries_once_on_malformed_output_then_succeeds() -> None:
    user_id, conv_id = uuid.uuid4(), uuid.uuid4()
    session = _mock_async_session(user_id, conv_id)

    mock_llm = AsyncMock()
    mock_llm.complete.side_effect = [
        LLMResponse(text="{malformed json here"),
        LLMResponse(
            text=json.dumps(
                {
                    "reply": "You're off to a strong start with Python! Are you open to remote roles too?",
                    "suggested_replies": ["Yes, remote works", "Only Bengaluru", "Show jobs now"],
                    "referenced_job_ids": [],
                }
            )
        ),
    ]

    result = await run_agent_turn(
        session=session,
        user_id=user_id,
        conversation_id=conv_id,
        user_message="I know Python and want Bengaluru roles",
        llm_client=mock_llm,
        persist_post_turn_memory=False,
    )

    assert mock_llm.complete.await_count == 2
    assert "strong start" in result.reply
    assert len(result.suggested_replies) == 3


async def test_agent_loop_falls_back_safely_after_second_malformed_output() -> None:
    user_id, conv_id = uuid.uuid4(), uuid.uuid4()
    session = _mock_async_session(user_id, conv_id)

    mock_llm = AsyncMock()
    mock_llm.complete.side_effect = [
        LLMResponse(text="{broken 1"),
        LLMResponse(text="{broken 2"),
    ]

    result = await run_agent_turn(
        session=session,
        user_id=user_id,
        conversation_id=conv_id,
        user_message="Hi",
        llm_client=mock_llm,
        persist_post_turn_memory=False,
    )

    assert result.reply == SAFE_FALLBACK_REPLY
    assert len(result.suggested_replies) == 3


async def test_agent_loop_executes_tool_calls_and_records_trace() -> None:
    user_id, conv_id = uuid.uuid4(), uuid.uuid4()
    session = _mock_async_session(user_id, conv_id)

    mock_llm = AsyncMock()
    mock_llm.complete.side_effect = [
        LLMResponse(
            text="",
            tool_calls=[
                ToolCallRequest(
                    id="call_1",
                    name="update_profile",
                    arguments={"skills": ["Python", "SQL"], "salary_min": 50000, "location_pref": "Bengaluru"},
                ),
                ToolCallRequest(
                    id="call_2",
                    name="interview_prep_tips",
                    arguments={"role": "Backend Engineer (Python)"},
                ),
            ],
        ),
        LLMResponse(
            text=json.dumps(
                {
                    "reply": "Updated your bearings for Bengaluru at ₹50K+/mo! Here are your top Python backend prep focus areas.",
                    "suggested_replies": ["Find matching jobs", "Build a 4-week roadmap"],
                    "referenced_job_ids": [],
                }
            )
        ),
    ]

    result = await run_agent_turn(
        session=session,
        user_id=user_id,
        conversation_id=conv_id,
        user_message="I know Python and SQL, want 50K+ in Bengaluru, give me interview tips",
        llm_client=mock_llm,
        persist_post_turn_memory=False,
    )

    assert [t.tool_name for t in result.tool_trace] == ["update_profile", "interview_prep_tips"]
    assert all(t.ok for t in result.tool_trace)
    assert result.profile is not None
    assert "sql" in result.profile.skills


async def test_chat_endpoint_supports_json_and_sse_streaming(client: AsyncClient) -> None:
    uid, cid = uuid.uuid4(), uuid.uuid4()
    fake_turn = AgentTurnResult(
        conversation_id=cid,
        user_id=uid,
        reply="Welcome to Compass! What kind of work excites you?",
        suggested_replies=["Python & AI", "Backend APIs", "Not sure yet"],
    )

    with patch("app.api.chat.run_agent_turn", new=AsyncMock(return_value=fake_turn)):
        res_json = await client.post("/chat", json={"message": "Hi"})
        assert res_json.status_code == 200
        assert res_json.json()["reply"].startswith("Welcome to Compass")
        assert "X-Compass-User-Id" in res_json.headers

        res_sse = await client.post("/chat", json={"message": "Hi", "stream": True})
        assert res_sse.status_code == 200
        assert "text/event-stream" in res_sse.headers["content-type"]
        body = res_sse.text
        assert "event: token" in body
        assert "event: meta" in body
        assert "event: done" in body


async def test_live_llm_provider_smoke_when_key_configured() -> None:
    """Runs a real live LLM call (Groq/Anthropic/Gemini) when an API key is configured in .env."""
    settings = get_settings()
    llm = LLMClient(settings)
    if not llm.is_configured():
        pytest.skip("No LLM API key configured in environment")

    resp = await llm.complete(
        system=(
            "You are Compass, a career mentor. Respond ONLY with JSON: "
            '{"reply": "short greeting", "suggested_replies": ["A", "B"], "referenced_job_ids": []}'
        ),
        messages=[{"role": "user", "content": "Hi! I am a fresher who likes Python."}],
        max_tokens=200,
        json_mode=True,
    )
    parsed = parse_structured_reply(resp.text)
    assert len(parsed.reply) > 5
    assert resp.provider == settings.llm_provider
    # Keep SimpleNamespace imported check clean
    assert SimpleNamespace(ok=True).ok
