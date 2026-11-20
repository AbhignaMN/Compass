"""Hand-written Compass agent loop (no LangChain, max 6 iterations, retry-once validation)."""

import json
import logging
import re
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.llm import LLMClient
from app.agent.prompts import build_system_prompt
from app.agent.schemas import (
    AgentTurnResult,
    ProfileSnapshot,
    StructuredMentorReply,
)
from app.agent.tools import (
    RoadmapBuilderFn,
    ToolExecutor,
    TurnToolState,
    get_llm_tool_definitions,
)
from app.config import get_settings
from app.db.models import Conversation, Interaction, Message, Profile, User
from app.search.schemas import RankedJob

logger = logging.getLogger(__name__)

StatusCallback = Callable[[str], Awaitable[None]]

SAFE_FALLBACK_REPLY = (
    "I hit a small snag formatting my notes, but I'm right here to help you chart your next step. "
    "Could you tell me the role or skills you want to explore right now?"
)

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE | re.DOTALL)
_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)


def parse_structured_reply(raw_text: str) -> StructuredMentorReply:
    """Parse and Pydantic-validate the LLM's final JSON mentor response."""
    cleaned = _FENCE_RE.sub("", raw_text.strip()).strip()
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        match = _JSON_OBJECT_RE.search(cleaned)
        if not match:
            raise
        data = json.loads(match.group(0))
    return StructuredMentorReply.model_validate(data)


async def _load_recent_messages(
    session: AsyncSession, conversation_id: uuid.UUID, limit: int = 12
) -> list[dict[str, Any]]:
    stmt = (
        select(Message)
        .where(Message.conversation_id == conversation_id, Message.role.in_(["user", "assistant"]))
        .order_by(Message.created_at.desc())
        .limit(limit)
    )
    rows = list(reversed((await session.execute(stmt)).scalars().all()))
    return [{"role": m.role, "content": m.content} for m in rows]


async def _load_relevant_memories(
    session: AsyncSession, user_id: uuid.UUID, query_text: str, k: int = 6
) -> list[dict[str, Any]]:
    from sqlalchemy import text as sa_text

    from app.services.embeddings import embed_text

    try:
        qvec = "[" + ",".join(f"{x:.6f}" for x in embed_text(query_text)) + "]"
        sql = sa_text(
            """
            SELECT type, text
            FROM memories
            WHERE user_id = :user_id
            ORDER BY embedding <=> CAST(:qvec AS vector) ASC NULLS LAST, last_seen DESC
            LIMIT :k
            """
        )
        rows = (
            await session.execute(sql, {"user_id": user_id, "qvec": qvec, "k": k})
        ).all()
        return [{"type": r.type, "text": r.text} for r in rows]
    except Exception:
        return []


async def _ensure_conversation(
    session: AsyncSession, user_id: uuid.UUID, conversation_id: uuid.UUID | None
) -> Conversation:
    user = await session.get(User, user_id)
    if user is None:
        session.add(User(id=user_id))
        await session.flush()

    if conversation_id is not None:
        conv = await session.get(Conversation, conversation_id)
        if conv is not None and conv.user_id == user_id:
            return conv

    conv = Conversation(id=conversation_id or uuid.uuid4(), user_id=user_id)
    session.add(conv)
    await session.flush()
    return conv


def _profile_to_dict(profile: Profile | None) -> dict[str, Any] | None:
    if profile is None:
        return None
    return {
        "skills": list(profile.skills or []),
        "interests": list(profile.interests or []),
        "location_pref": profile.location_pref,
        "remote_ok": bool(profile.remote_ok),
        "salary_min": profile.salary_min,
        "experience_level": profile.experience_level,
        "goals": profile.goals,
    }


def _resolve_grounded_jobs(
    referenced_ids: list[str], state: TurnToolState
) -> list[RankedJob]:
    """Guarantee every recommended job comes strictly from verified DB tool results."""
    verified: list[RankedJob] = []
    seen: set[uuid.UUID] = set()

    for raw_id in referenced_ids:
        try:
            jid = uuid.UUID(str(raw_id).strip())
        except ValueError:
            continue
        if jid in state.ranked_by_id and jid not in seen:
            verified.append(state.ranked_by_id[jid])
            seen.add(jid)

    # If rank_jobs ran during this turn and the LLM omitted IDs from referenced_job_ids,
    # surface the top ranked DB jobs so UI job cards stay grounded and complete.
    if not verified and state.latest_ranked_jobs:
        verified = state.latest_ranked_jobs[:5]

    return verified


async def run_agent_turn(
    *,
    session: AsyncSession,
    user_id: uuid.UUID,
    user_message: str,
    conversation_id: uuid.UUID | None = None,
    llm_client: LLMClient | None = None,
    roadmap_builder: RoadmapBuilderFn | None = None,
    on_status: StatusCallback | None = None,
    persist_post_turn_memory: bool = True,
) -> AgentTurnResult:
    """Execute one full conversational turn with tools, validation, retry-once, and grounding."""
    settings = get_settings()
    llm = llm_client or LLMClient(settings)

    conv = await _ensure_conversation(session, user_id, conversation_id)
    profile = await session.get(Profile, user_id)
    history = await _load_recent_messages(session, conv.id, limit=12)
    memories = await _load_relevant_memories(session, user_id, user_message, k=6)

    # Persist incoming user message
    session.add(
        Message(
            id=uuid.uuid4(),
            conversation_id=conv.id,
            role="user",
            content=user_message,
        )
    )
    await session.flush()

    system_prompt = build_system_prompt(
        profile=_profile_to_dict(profile),
        memories=memories,
        rolling_summary=conv.summary,
    )
    messages: list[dict[str, Any]] = [*history, {"role": "user", "content": user_message}]
    tools = get_llm_tool_definitions()
    state = TurnToolState()
    if profile is not None:
        state.profile = ProfileSnapshot(
            user_id=profile.user_id,
            skills=list(profile.skills or []),
            interests=list(profile.interests or []),
            location_pref=profile.location_pref,
            remote_ok=bool(profile.remote_ok),
            salary_min=profile.salary_min,
            experience_level=profile.experience_level,
            goals=profile.goals,
        )

    executor = ToolExecutor(
        session=session,
        user_id=user_id,
        state=state,
        roadmap_builder=roadmap_builder,
    )

    structured: StructuredMentorReply | None = None
    validation_retried = False

    if on_status:
        await on_status("Charting your course...")

    for iteration in range(settings.agent_max_iterations):
        response = await llm.complete(
            system=system_prompt,
            messages=messages,
            tools=tools if iteration < settings.agent_max_iterations - 1 else None,
        )

        if response.tool_calls:
            messages.append(
                {
                    "role": "assistant",
                    "content": response.text,
                    "tool_calls": [
                        {"id": tc.id, "name": tc.name, "arguments": tc.arguments}
                        for tc in response.tool_calls
                    ],
                }
            )
            for tc in response.tool_calls:
                if on_status:
                    await on_status(f"Checking bearings ({tc.name.replace('_', ' ')})...")
                result_str, is_error = await executor.execute(tc.name, tc.arguments)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "name": tc.name,
                        "content": result_str,
                        "is_error": is_error,
                    }
                )
            continue

        # No tool calls -> validate final structured JSON output
        try:
            structured = parse_structured_reply(response.text)
            break
        except (json.JSONDecodeError, ValidationError) as exc:
            logger.warning("Malformed structured agent output (retried=%s): %s", validation_retried, exc)
            if not validation_retried:
                validation_retried = True
                messages.append({"role": "assistant", "content": response.text})
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            "Your last response failed Pydantic validation with this error:\n"
                            f"{exc}\n"
                            "Return ONLY a valid JSON object matching "
                            '{"reply": str, "suggested_replies": [str, ...], "referenced_job_ids": [str, ...]}.'
                        ),
                    }
                )
                continue
            # Already retried once -> fall back safely
            plain = response.text.strip()
            if plain and not plain.startswith("{"):
                structured = StructuredMentorReply(
                    reply=plain,
                    suggested_replies=[
                        "Show matching jobs",
                        "Check my skill gaps",
                        "Build a 4-week roadmap",
                    ],
                    referenced_job_ids=[],
                )
            else:
                structured = StructuredMentorReply(
                    reply=SAFE_FALLBACK_REPLY,
                    suggested_replies=[
                        "Explore Python & AI roles",
                        "Find fresher backend jobs",
                        "Help me pick a track",
                    ],
                    referenced_job_ids=[],
                )
            break

    if structured is None:
        structured = StructuredMentorReply(
            reply=SAFE_FALLBACK_REPLY,
            suggested_replies=[
                "Show matching jobs",
                "Build a learning roadmap",
                "Update my preferences",
            ],
            referenced_job_ids=[],
        )

    grounded_jobs = _resolve_grounded_jobs(structured.referenced_job_ids, state)

    # Persist assistant reply + tool trace
    session.add(
        Message(
            id=uuid.uuid4(),
            conversation_id=conv.id,
            role="assistant",
            content=structured.reply,
            tool_calls=[t.model_dump(mode="json") for t in state.trace] or None,
        )
    )

    # Log 'shown' interactions for grounded job recommendations
    for job in grounded_jobs:
        session.add(
            Interaction(
                id=uuid.uuid4(),
                user_id=user_id,
                job_id=job.job_id,
                event="shown",
            )
        )

    await session.flush()

    # Post-turn memory extraction & rolling summary (implemented in Stage 5)
    if persist_post_turn_memory:
        try:
            from app.services.memory import update_post_turn_memory

            await update_post_turn_memory(
                session=session,
                user_id=user_id,
                conversation=conv,
                user_message=user_message,
                assistant_reply=structured.reply,
                llm_client=llm,
            )
        except ImportError:
            pass
        except Exception as exc:
            logger.warning("Post-turn memory update skipped due to error: %s", exc)

    await session.commit()

    return AgentTurnResult(
        conversation_id=conv.id,
        user_id=user_id,
        reply=structured.reply,
        suggested_replies=structured.suggested_replies[:3],
        recommended_jobs=grounded_jobs,
        skill_gap=state.latest_skill_gap,
        roadmap=state.latest_roadmap,
        profile=state.profile,
        tool_trace=state.trace,
    )
