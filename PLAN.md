# Compass — Implementation Plan

Building **Compass**, an end-to-end conversational AI career agent for freshers and interns in India.
Work proceeds in vertical slices: build -> test -> commit -> push to `origin/main` before starting the next stage.

## Stages

- [x] **Stage 1: Repo scaffold, Docker Compose, DB migrations, `/health`**
  - [x] Initialize repo, `.gitignore`, `.env.example`, `PLAN.md`, `DECISIONS.md`
  - [x] FastAPI app skeleton, config, structured JSON logging with request IDs, rate limiting
  - [x] SQLAlchemy 2 async models + Alembic migration (`0001_initial_schema`) with pgvector `vector(384)` & HNSW indexes
  - [x] `docs/schema.md` documenting every table, column, and index
  - [x] `Dockerfile` (multi-stage, non-root) + `docker-compose.yml` (`api` + `pgvector/pgvector:pg16`)
  - [x] `GET /health` endpoint + Stage 1 unit tests
- [x] **Stage 2: Seed jobs, skills, embeddings, KB chunks**
  - [x] Curated ~150-skill taxonomy with deterministic regex matcher (`app/services/skills.py`)
  - [x] Local embedding service via `fastembed` (`BAAI/bge-small-en-v1.5`, 384 dims) with LRU cache
  - [x] 300+ realistic India fresher/intern job postings (`data/jobs_seed.json`) + `scripts/seed_jobs.py`
  - [x] Live ingestion script `scripts/ingest_jobs.py` (Remotive/Arbeitnow) with `content_hash` dedupe & incremental re-embedding
  - [x] Curated career guides (`data/kb/*.md`, 8 roles) + chunking (~300 tokens) & embedding loader
- [x] **Stage 3: Hybrid search + ranking + skill-gap SQL, with tests**
  - [x] `hybrid_search(query, filters, k)` with pgvector cosine + Postgres FTS + RRF (`k=60`) and hard SQL filters
  - [x] `rank_jobs(profile, candidates)` with configurable weights (`0.5*semantic + 0.25*skill_overlap + 0.15*preference_fit + 0.1*freshness`) + interaction adjustments + component breakdown
  - [x] `skill_gap(user_id, job_id)` SQL query joining profile skills to `job_skills` ordered by importance
  - [x] Unit & DB retrieval tests
- [x] **Stage 4: Agent loop with tools and structured outputs**
  - [x] Hand-written Claude tool-use agent loop (no LangChain, max 6 iterations)
  - [x] Pydantic-validated tools: `update_profile`, `search_jobs`, `rank_jobs`, `skill_gap`, `compare_jobs`, `tailor_resume_summary`, `interview_prep_tips`, `recall_memory`
  - [x] Retry-once on Pydantic validation errors with safe fallback
  - [x] Mentor persona, grounded recommendations, SSE streaming `POST /chat`
- [x] **Stage 5: Memory (short-term summary + long-term extractor)**
  - [x] Rolling conversation summary + last-N messages loader
  - [x] Post-turn memory extractor (separate Claude JSON call) writing to `memories`
  - [x] Similarity-based deduplication & conflict updates (e.g., changed salary/location)
  - [x] Profile & memory view/edit/delete endpoints for UI side panel
- [x] **Stage 6: Roadmap with RAG and citations**
  - [x] `build_roadmap(target_role)` retrieving `kb_chunks` via hybrid RAG and generating schema-validated JSON roadmap with chunk citations
  - [x] `GET /roadmap/{user_id}` and milestone persistence
  - [x] 15+ scripted multi-turn conversation scenarios testing mentor quality & memory
- [x] **Stage 7: UI + feedback logging**
  - [x] `GET /jobs/{id}`, `POST /feedback` (`shown`, `clicked`, `saved`, `dismissed`), anonymous cookie/localStorage identity
  - [x] Next.js (App Router) + TypeScript + Tailwind + Framer Motion UI ("Compass" brand)
  - [x] Three themes: Colourful (light), Midnight (dark navy), Mahogany (dark leather) with animated compass toggle
  - [x] Streaming chat, compass-dial fit scores, journey roadmap timeline, editable "Your profile" panel
  - [x] Desktop & mobile screenshots across all three palettes in `docs/screenshots/`
- [x] **Stage 8: Evals + results table**
  - [x] Retrieval evals: 50 labelled test profiles, Recall@10 & nDCG@10 for vector-only, keyword-only, hybrid, hybrid+rerank -> `evals/results.md`
  - [x] Generation evals: LLM-as-judge rubric (groundedness, relevance, actionability) on 30 conversations + hard `job_id` existence check
  - [x] Agent multi-turn tool & cross-session memory recall tests
  - [x] GitHub Actions CI (lint, unit tests on push; LLM evals on manual dispatch)
- [ ] **Stage 9: Deploy + smoke test**
  - [x] Render Docker Blueprint with Neon connection settings + migrations on boot
  - [ ] Deploy live service, hit `/health`, run end-to-end smoke test against public URL
- [x] **Stage 10: README polish**
  - [x] Complete `README.md` with architecture Mermaid diagram, schema summary, hybrid search/ranking & memory explanations, real eval numbers, screenshots, Docker instructions, "What I'd improve next", and 10 interview questions
