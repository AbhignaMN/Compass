# Compass Evaluation Results

_Generated on 2026-11-21 02:48 UTC via `python -m evals.run`._

## 1. Retrieval & Ranking Benchmark (50 Labelled Fresher Profiles, 320 Seed Jobs)

### Ground-Truth Labelling Rules
- Test profiles (`evals/test_profiles.json`) span all 8 Indian fresher tracks (AI/ML, Backend, Full-Stack, Data, Cybersecurity, QA/SDET, Product, DevOps) across Bengaluru, Hyderabad, Pune, Gurugram, Mumbai, Chennai, Noida, and Remote.
- Hard SQL-equivalent filters (`status='active'`, city/remote, `salary_max >= salary_min`) are applied equally to every method.
- **Grade 2 (highly relevant):** track matches, experience level (`intern` vs `fresher`) matches, and skill overlap >= 0.35.
- **Grade 1 (relevant):** track matches and skill overlap >= 0.15 (or experience level matches with >= 1 overlapping core skill).
- Embeddings: local `BAAI/bge-small-en-v1.5` (384 dims via `fastembed`). Ranking weights: `0.50*semantic + 0.25*skill_overlap + 0.15*preference_fit + 0.10*freshness`.

| Retrieval Strategy | Recall@10 | nDCG@10 |
| --- | ---: | ---: |
| Vector-only (`bge-small-en-v1.5`) | 0.7031 | 0.7038 |
| Keyword-only (Weighted BM25) | 0.7199 | 0.7382 |
| Hybrid (RRF, `k=60`) | 0.7602 | 0.7570 |
| **Hybrid + Rerank (`rank_jobs`)** | **0.7586** | **0.8322** |

## 2. Generation Quality & Grounding Check (30 Conversations)

- **LLM Provider / Model:** `groq` / `openai/gpt-oss-120b` (Judge: `openai/gpt-oss-20b`)
- **Conversations Scored:** 30 / 30 (parse/API errors: 0)

| Metric | Result |
| --- | ---: |
| Groundedness (1–5) | **4.47 / 5.00** |
| Relevance (1–5) | **4.53 / 5.00** |
| Actionability (1–5) | **4.53 / 5.00** |
| Hard Check: Valid DB `job_id`s | **39 / 39 (100.0%)** |

## 3. Agent Tool & Cross-Session Memory Suite

Run `pytest tests/test_stage6_conversations.py tests/test_stage8_evals.py -v` to verify:
- All 16 scripted multi-turn mentor scenarios (cold start, vague user, empathy, changed mind, reference resolution, comparisons, safety).
- Correct tool selection & Pydantic validation retry-once recovery.
- Cross-session recall of facts stated in Turn 1 inside a brand-new conversation.
