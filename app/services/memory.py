"""Short-term rolling conversation summary and long-term semantic memory extractor.

Features:
- Separate fast LLM JSON call extracting durable facts, preferences, and goals.
- Local 384-dim fastembed cosine similarity deduplication (>= 0.88 refreshes last_seen).
- Conflict-aware update-in-place (e.g., changed salary floor, city, or remote preference).
- Rolling conversation summary kept in `conversations.summary`.
"""

import json
import logging
import math
import re
import uuid
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.llm import LLMClient
from app.config import get_settings
from app.db.models import Conversation, Memory, Message
from app.services.embeddings import embed_text

logger = logging.getLogger(__name__)

DEDUPE_SIMILARITY_THRESHOLD = 0.88
CONFLICT_SIMILARITY_THRESHOLD = 0.58

CONFLICT_TOPIC_KEYWORDS: dict[str, tuple[str, ...]] = {
    "salary": ("salary", "stipend", "inr", "lpa", "pay", "compensation", "k/mo", "000", "ctc"),
    "location": ("bengaluru", "bangalore", "hyderabad", "pune", "gurugram", "mumbai", "chennai", "noida", "delhi", "city", "relocat"),
    "remote": ("remote", "work from home", "wfh", "hybrid", "on-site", "onsite", "in-office"),
    "experience": ("fresher", "intern", "student", "final year", "graduate", "years of experience"),
}

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE | re.DOTALL)
_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


class ExtractedMemoryItem(BaseModel):
    type: Literal["fact", "preference", "goal"]
    text: str = Field(min_length=4, max_length=240)


class ExtractedMemoryBatch(BaseModel):
    memories: list[ExtractedMemoryItem] = Field(default_factory=list, max_length=6)


def cosine_similarity(vec_a: list[float] | None, vec_b: list[float] | None) -> float:
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0
    dot = sum(float(a) * float(b) for a, b in zip(vec_a, vec_b, strict=True))
    norm_a = math.sqrt(sum(float(a) * float(a) for a in vec_a))
    norm_b = math.sqrt(sum(float(b) * float(b) for b in vec_b))
    return dot / (norm_a * norm_b) if norm_a and norm_b else 0.0


def detect_conflict_topic(text_value: str) -> str | None:
    lower = text_value.lower()
    for topic, keywords in CONFLICT_TOPIC_KEYWORDS.items():
        if any(kw in lower for kw in keywords):
            return topic
    return None


def _parse_memory_batch(raw_text: str) -> ExtractedMemoryBatch:
    cleaned = _FENCE_RE.sub("", raw_text.strip()).strip()
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        match = _JSON_RE.search(cleaned)
        if not match:
            return ExtractedMemoryBatch()
        data = json.loads(match.group(0))
    try:
        return ExtractedMemoryBatch.model_validate(data)
    except ValidationError:
        return ExtractedMemoryBatch()


async def extract_memories_from_turn(
    *,
    user_message: str,
    assistant_reply: str,
    llm_client: LLMClient,
) -> list[ExtractedMemoryItem]:
    """Use a fast JSON LLM call to extract durable facts, preferences, and goals."""
    if not llm_client.is_configured():
        return []

    settings = get_settings()
    system = (
        "You extract durable, long-term career memories from a user's latest chat message. "
        "Ignore greetings, transient questions, and assistant suggestions unless the user confirmed them. "
        "Classify each item strictly as:\n"
        "- 'fact': background, skills, degree, projects, experience level\n"
        "- 'preference': city, remote/hybrid preference, salary expectation (monthly INR), dislikes (e.g., hates sales)\n"
        "- 'goal': target roles, timeline, career objectives\n"
        "Return ONLY valid JSON: {\"memories\": [{\"type\": \"fact|preference|goal\", \"text\": \"concise 1-sentence memory\"}]}. "
        "If nothing durable is stated, return {\"memories\": []}."
    )
    prompt = f"User message: {user_message}\n\nAssistant reply (context only): {assistant_reply[:400]}"

    resp = await llm_client.complete(
        system=system,
        messages=[{"role": "user", "content": prompt}],
        model=settings.active_memory_model,
        max_tokens=1024,
        temperature=0.0,
        json_mode=True,
    )
    return _parse_memory_batch(resp.text).memories


def merge_memory_item(
    existing_memories: list[Memory],
    new_item: ExtractedMemoryItem,
    new_embedding: list[float],
    user_id: uuid.UUID,
    now: datetime | None = None,
) -> tuple[Literal["deduped", "updated", "inserted"], Memory]:
    """Decide whether a new memory deduplicates, updates a conflict, or inserts a new row."""
    ts = now or datetime.now(UTC)
    new_topic = detect_conflict_topic(new_item.text)

    best_same_type: tuple[float, Memory] | None = None
    topic_conflict_target: tuple[float, Memory] | None = None

    for mem in existing_memories:
        sim = cosine_similarity(list(mem.embedding) if mem.embedding is not None else None, new_embedding)

        if mem.type == new_item.type and (best_same_type is None or sim > best_same_type[0]):
            best_same_type = (sim, mem)

        if (
            new_topic is not None
            and detect_conflict_topic(mem.text) == new_topic
            and mem.type == new_item.type
            and (topic_conflict_target is None or sim > topic_conflict_target[0])
        ):
            topic_conflict_target = (sim, mem)

    # 1. Near-exact duplicate -> touch last_seen
    if best_same_type and best_same_type[0] >= DEDUPE_SIMILARITY_THRESHOLD:
        target = best_same_type[1]
        target.last_seen = ts
        return "deduped", target

    # 2. Conflict on same durable dimension (e.g. salary 50K -> 70K, city Bengaluru -> Pune)
    if topic_conflict_target and topic_conflict_target[0] >= 0.35:
        target = topic_conflict_target[1]
        target.text = new_item.text.strip()
        target.embedding = new_embedding
        target.last_seen = ts
        return "updated", target

    if best_same_type and best_same_type[0] >= CONFLICT_SIMILARITY_THRESHOLD and new_topic is not None:
        target = best_same_type[1]
        target.text = new_item.text.strip()
        target.embedding = new_embedding
        target.last_seen = ts
        return "updated", target

    # 3. Brand new durable memory
    created = Memory(
        id=uuid.uuid4(),
        user_id=user_id,
        type=new_item.type,
        text=new_item.text.strip(),
        embedding=new_embedding,
        last_seen=ts,
    )
    existing_memories.append(created)
    return "inserted", created


async def upsert_user_memories(
    session: AsyncSession,
    user_id: uuid.UUID,
    items: list[ExtractedMemoryItem],
) -> dict[str, int]:
    """Persist extracted memories with cosine dedupe and conflict-aware updates."""
    counts = {"inserted": 0, "updated": 0, "deduped": 0}
    if not items:
        return counts

    res = await session.execute(select(Memory).where(Memory.user_id == user_id))
    existing = list(res.scalars().all())

    for item in items:
        emb = embed_text(item.text)
        action, mem = merge_memory_item(existing, item, emb, user_id=user_id)
        if action == "inserted":
            session.add(mem)
        counts[action] += 1

    await session.flush()
    return counts


async def refresh_rolling_summary(
    session: AsyncSession,
    conversation: Conversation,
    llm_client: LLMClient,
    min_messages_for_summary: int = 6,
) -> str | None:
    """Update conversations.summary once a thread exceeds min_messages_for_summary messages."""
    res = await session.execute(
        select(Message)
        .where(Message.conversation_id == conversation.id, Message.role.in_(["user", "assistant"]))
        .order_by(Message.created_at.asc())
    )
    msgs = list(res.scalars().all())
    if len(msgs) < min_messages_for_summary:
        return conversation.summary

    if not llm_client.is_configured():
        return conversation.summary

    settings = get_settings()
    recent_excerpt = "\n".join(
        f"{m.role.upper()}: {m.content[:260]}" for m in msgs[-10:]
    )
    prior = conversation.summary or "None yet."
    resp = await llm_client.complete(
        system=(
            "Summarize this career mentoring conversation in 2 to 4 concise sentences. "
            "Keep user goals, constraints, jobs discussed, and next steps. Plain text only."
        ),
        messages=[
            {
                "role": "user",
                "content": f"Prior summary: {prior}\n\nRecent messages:\n{recent_excerpt}",
            }
        ],
        model=settings.active_memory_model,
        max_tokens=180,
        temperature=0.1,
    )
    summary = resp.text.strip()
    if summary:
        conversation.summary = summary
        await session.flush()
    return conversation.summary


async def update_post_turn_memory(
    *,
    session: AsyncSession,
    user_id: uuid.UUID,
    conversation: Conversation,
    user_message: str,
    assistant_reply: str,
    llm_client: LLMClient,
) -> dict[str, int]:
    """Run post-turn long-term memory extraction and rolling summary refresh."""
    extracted = await extract_memories_from_turn(
        user_message=user_message,
        assistant_reply=assistant_reply,
        llm_client=llm_client,
    )
    counts = await upsert_user_memories(session, user_id, extracted)
    await refresh_rolling_summary(session, conversation, llm_client)
    return counts
