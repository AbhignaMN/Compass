"""Stage 5 tests: memory dedupe, conflict overwrite, rolling summary, profile/memory API, and live extraction."""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import AsyncClient

from app.agent.llm import LLMClient, LLMResponse
from app.config import get_settings
from app.db.models import Conversation, Memory, Message, Profile, User
from app.db.session import get_db_session
from app.main import app
from app.services.embeddings import embed_text
from app.services.memory import (
    ExtractedMemoryItem,
    extract_memories_from_turn,
    merge_memory_item,
    refresh_rolling_summary,
)


def test_memory_merge_dedupes_near_duplicates_and_updates_conflicts() -> None:
    user_id = uuid.uuid4()
    t0 = datetime(2026, 11, 18, 10, 0, tzinfo=UTC)
    t1 = t0 + timedelta(hours=2)
    t2 = t0 + timedelta(days=1)

    existing: list[Memory] = []

    # 1. Insert initial salary preference
    sal_50 = ExtractedMemoryItem(type="preference", text="Wants a minimum salary of 50,000 INR per month.")
    action1, mem1 = merge_memory_item(existing, sal_50, embed_text(sal_50.text), user_id=user_id, now=t0)
    assert action1 == "inserted"
    assert len(existing) == 1

    # 2. Near-identical restatement -> deduped (updates last_seen, no duplicate row)
    sal_50_dup = ExtractedMemoryItem(type="preference", text="Wants a minimum salary of 50,000 INR per month")
    action2, mem2 = merge_memory_item(existing, sal_50_dup, embed_text(sal_50_dup.text), user_id=user_id, now=t1)
    assert action2 == "deduped"
    assert mem2.id == mem1.id
    assert mem2.last_seen == t1
    assert len(existing) == 1

    # 3. Conflict: user raises salary expectation to 75K/month -> updates existing row in place!
    sal_75 = ExtractedMemoryItem(type="preference", text="Now expects a minimum salary of 75,000 INR per month.")
    action3, mem3 = merge_memory_item(existing, sal_75, embed_text(sal_75.text), user_id=user_id, now=t2)
    assert action3 == "updated"
    assert mem3.id == mem1.id
    assert "75,000" in mem3.text
    assert len(existing) == 1

    # 4. Different category/topic -> inserted as separate memory
    city_pref = ExtractedMemoryItem(type="preference", text="Prefers working in Bengaluru or remote.")
    action4, _ = merge_memory_item(existing, city_pref, embed_text(city_pref.text), user_id=user_id, now=t2)
    assert action4 == "inserted"
    assert len(existing) == 2


async def test_refresh_rolling_summary_updates_conversation_when_long_enough() -> None:
    conv = Conversation(id=uuid.uuid4(), user_id=uuid.uuid4(), summary=None)
    msgs = [
        Message(id=uuid.uuid4(), conversation_id=conv.id, role="user" if i % 2 == 0 else "assistant", content=f"Turn {i}")
        for i in range(6)
    ]
    res = MagicMock()
    res.scalars.return_value.all.return_value = msgs
    session = AsyncMock()
    session.execute.return_value = res

    mock_llm = AsyncMock()
    mock_llm.is_configured = MagicMock(return_value=True)
    mock_llm.complete.return_value = LLMResponse(
        text="User is a Python fresher targeting Bengaluru backend roles at 50K+/mo and reviewed two matches."
    )

    updated = await refresh_rolling_summary(session, conv, mock_llm)
    assert updated is not None
    assert "Bengaluru" in updated
    assert conv.summary == updated


async def test_profile_and_memory_endpoints_crud(client: AsyncClient) -> None:
    user_id = uuid.uuid4()
    mem_id = uuid.uuid4()
    now = datetime.now(UTC)

    user = User(id=user_id)
    profile = Profile(
        user_id=user_id,
        skills=["python"],
        interests=["ai_ml"],
        location_pref="Bengaluru",
        remote_ok=True,
        salary_min=50000,
        experience_level="fresher",
        goals="Land an AI/LLM internship",
    )
    mem = Memory(
        id=mem_id,
        user_id=user_id,
        type="preference",
        text="Hates sales roles",
        embedding=[0.0] * 384,
        last_seen=now,
        created_at=now,
    )

    session = AsyncMock()

    async def fake_get(model, pk):
        if model is User:
            return user
        if model is Profile:
            return profile
        if model is Memory and pk == mem_id:
            return mem
        return None

    session.get.side_effect = fake_get
    mem_res = MagicMock()
    mem_res.scalars.return_value.all.return_value = [mem]
    session.execute.return_value = mem_res
    session.add = MagicMock()

    async def override_db():
        yield session

    app.dependency_overrides[get_db_session] = override_db
    headers = {"X-Compass-User-Id": str(user_id)}
    try:
        r_get = await client.get("/profile", headers=headers)
        assert r_get.status_code == 200
        data = r_get.json()
        assert data["profile"]["skills"] == ["python"]
        assert len(data["memories"]) == 1

        r_patch = await client.patch(
            "/profile",
            headers=headers,
            json={"skills": ["Python", "Postgres", "FastAPI"], "salary_min": 65000},
        )
        assert r_patch.status_code == 200
        assert r_patch.json()["skills"] == ["python", "postgresql", "fastapi"]
        assert r_patch.json()["salary_min"] == 65000

        r_mem = await client.patch(
            f"/memories/{mem_id}",
            headers=headers,
            json={"text": "Avoids sales and cold-calling roles"},
        )
        assert r_mem.status_code == 200
        assert "cold-calling" in r_mem.json()["text"]

        r_del = await client.delete(f"/memories/{mem_id}", headers=headers)
        assert r_del.status_code == 200
        assert r_del.json()["deleted"] is True
    finally:
        app.dependency_overrides.clear()


async def test_live_memory_extractor_when_key_configured() -> None:
    settings = get_settings()
    llm = LLMClient(settings)
    if not llm.is_configured():
        pytest.skip("No LLM API key configured")

    items = await extract_memories_from_turn(
        user_message="I'm a final-year BTech CS student who loves Python and SQL, hates sales, and wants 60K+ in Bengaluru.",
        assistant_reply="Got it! I'll focus on Bengaluru Python/SQL roles paying 60K+/mo and skip sales.",
        llm_client=llm,
    )
    assert len(items) >= 2
    types = {item.type for item in items}
    assert types.intersection({"fact", "preference", "goal"})
