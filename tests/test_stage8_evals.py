"""Stage 8 eval tests runnable with pytest: retrieval metrics, grounding check, and agent memory recall."""

import json
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.agent.llm import LLMResponse, ToolCallRequest
from app.agent.loop import run_agent_turn
from app.db.models import Conversation, Memory, Profile, User
from app.services.embeddings import embed_text
from app.services.memory import ExtractedMemoryItem, merge_memory_item
from evals.generation_eval import GENERATION_PROMPTS_30, verify_recommended_ids_exist_in_db
from evals.retrieval_eval import compute_ndcg_at_k, compute_recall_at_k, run_retrieval_eval


def test_recall_and_ndcg_metric_math() -> None:
    rel = {"j1": 2, "j2": 1, "j3": 2}
    # Perfect ordering
    assert compute_recall_at_k(["j1", "j3", "j2", "j9"], rel, k=10) == pytest.approx(1.0)
    assert compute_ndcg_at_k(["j1", "j3", "j2", "j9"], rel, k=10) == pytest.approx(1.0)
    # Worse ordering lowers nDCG
    ndcg_worse = compute_ndcg_at_k(["j9", "j8", "j2", "j1"], rel, k=10)
    assert 0.0 < ndcg_worse < 1.0


def test_retrieval_eval_50_profiles_hybrid_rerank_beats_single_modalities() -> None:
    result = run_retrieval_eval(save_profiles=False)
    assert result["num_profiles"] == 50
    assert result["num_jobs"] >= 300

    methods = result["methods"]
    for key in ("vector_only", "keyword_only", "hybrid", "hybrid_rerank"):
        assert 0.5 <= methods[key]["recall_at_10"] <= 1.0
        assert 0.5 <= methods[key]["ndcg_at_10"] <= 1.0

    # Hybrid + rerank should achieve the strongest nDCG@10 overall
    assert methods["hybrid_rerank"]["ndcg_at_10"] >= methods["vector_only"]["ndcg_at_10"]
    assert methods["hybrid_rerank"]["ndcg_at_10"] >= methods["keyword_only"]["ndcg_at_10"]


def test_generation_eval_has_30_conversations_and_hard_db_id_check() -> None:
    assert len(GENERATION_PROMPTS_30) == 30
    valid_ids = {"id-1", "id-2"}
    ok, missing = verify_recommended_ids_exist_in_db(["id-1", "id-2"], valid_ids)
    assert ok is True and missing == []

    ok_bad, missing_bad = verify_recommended_ids_exist_in_db(["id-1", "hallucinated-999"], valid_ids)
    assert ok_bad is False and missing_bad == ["hallucinated-999"]


async def test_agent_eval_turn1_fact_recalled_in_new_conversation() -> None:
    """Assert fact stated in Conversation 1 is extracted and recalled in Conversation 2."""
    user_id = uuid.uuid4()
    stored_memories: list[Memory] = []

    # Turn 1 (Conversation 1): user states a durable fact + preference
    fact_item = ExtractedMemoryItem(type="fact", text="Graduating BTech CSE in 2026 with Python & FastAPI skills.")
    pref_item = ExtractedMemoryItem(type="preference", text="Strongly dislikes sales and prefers Bengaluru.")
    for item in (fact_item, pref_item):
        merge_memory_item(stored_memories, item, embed_text(item.text), user_id=user_id)
    assert len(stored_memories) == 2

    # Turn 2 (Brand-new Conversation 2 next day): system loads stored memories into agent context
    conv2_id = uuid.uuid4()
    session = AsyncMock()
    user = User(id=user_id)
    profile = Profile(user_id=user_id, skills=["python", "fastapi"], interests=[], remote_ok=True)
    conv2 = Conversation(id=conv2_id, user_id=user_id, summary=None)

    async def fake_get(model, pk):
        if model is User:
            return user
        if model is Profile:
            return profile
        if model is Conversation:
            return conv2
        return None

    session.get.side_effect = fake_get
    session.add = MagicMock()

    async def fake_execute(stmt, params=None):
        res = MagicMock()
        if "FROM memories" in str(stmt):
            res.all.return_value = [
                SimpleNamespace(id=m.id, type=m.type, text=m.text, similarity=0.92)
                for m in stored_memories
            ]
        else:
            res.all.return_value = []
        res.scalars.return_value.all.return_value = []
        return res

    session.execute.side_effect = fake_execute

    seen_prompts: list[str] = []

    async def mock_complete(**kwargs):
        seen_prompts.append(kwargs["system"])
        if len(seen_prompts) == 1:
            return LLMResponse(
                tool_calls=[
                    ToolCallRequest(
                        id="rec_1",
                        name="recall_memory",
                        arguments={"query": "city preference and dislikes"},
                    )
                ]
            )
        return LLMResponse(
            text=json.dumps(
                {
                    "reply": "Welcome back! I remember you're graduating BTech CSE in 2026 with Python/FastAPI, prefer Bengaluru, and want zero sales.",
                    "suggested_replies": ["Show matching jobs", "Build my roadmap"],
                    "referenced_job_ids": [],
                }
            )
        )

    mock_llm = AsyncMock()
    mock_llm.complete.side_effect = mock_complete

    turn = await run_agent_turn(
        session=session,
        user_id=user_id,
        conversation_id=conv2_id,
        user_message="Hey, do you remember what I told you yesterday?",
        llm_client=mock_llm,
        persist_post_turn_memory=False,
    )

    assert "Strongly dislikes sales" in seen_prompts[0]
    assert "recall_memory" in [t.tool_name for t in turn.tool_trace]
    assert "Bengaluru" in turn.reply
