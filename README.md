# Compass

> *Find your true north in your career.*

**Compass** is an end-to-end conversational AI career mentor for freshers and interns in India. Built from scratch without agent frameworks, Compass combines hybrid PostgreSQL retrieval (`pgvector` HNSW + full-text search with Reciprocal Rank Fusion), deterministic skill-gap analysis, a hand-written Claude tool-use agent loop, cross-session memory, and RAG-grounded learning roadmaps.

## Current Progress

- [x] **Stage 1:** FastAPI async scaffold, structured JSON logging with request IDs, rate limiting, SQLAlchemy 2 + Alembic Postgres/pgvector schema (`docs/schema.md`), multi-stage `Dockerfile` + `docker-compose.yml`, and `GET /health`.
- [x] **Stage 2:** 320 sample India fresher/intern jobs (`data/jobs_seed.json`), deterministic 150-skill regex extractor, local `fastembed` embeddings (`BAAI/bge-small-en-v1.5`, 384 dims) with LRU cache, incremental live ingestion (`scripts/ingest_jobs.py` via Remotive/Arbeitnow), and 8 curated career guides (`data/kb/*.md`) chunked to ~300 tokens for RAG.
- [x] **Stage 3:** Hybrid search (`pgvector` HNSW cosine + Postgres FTS merged via RRF `k=60` with SQL hard filters), weighted reranking (`0.5*semantic + 0.25*skill_overlap + 0.15*preference_fit + 0.1*freshness` + interaction boosts/penalties), and pure SQL `skill_gap` analysis (`app/search/`).
- [x] **Stage 4:** Hand-written tool-use agent loop (`app/agent/`, max 6 iterations, zero agent frameworks), 9 Pydantic-validated tools, retry-once output validation with safe fallback, strict `job_id` grounding, and JSON + SSE streaming `POST /chat`.
- [ ] **Stages 5–10:** Short/long-term memory, RAG roadmaps, Next.js UI (Colourful / Midnight / Mahogany themes), evals, and Render + Neon deployment.

## Sample Data & Live Ingestion

- **Sample seed data (`data/jobs_seed.json`)**: Contains **320 synthetic sample postings** tailored to Indian freshers and interns across AI/ML, Backend, Full-Stack, Data, Cybersecurity, QA/SDET, DevOps, and APM roles in Bengaluru, Hyderabad, Pune, Gurugram, Mumbai, Chennai, Noida, and Remote. Companies and URLs (`sample-jobs.compass.local`) are clearly marked as sample data (`source='seed'`).
- **Live public ingestion (`scripts/ingest_jobs.py`)**: Pulls live postings from Remotive (with Arbeitnow fallback), strips HTML, normalizes fields, computes `content_hash`, upserts into `jobs`, extracts skills via regex, and re-embeds only newly added or modified rows.
- **Career knowledge base (`data/kb/*.md`)**: 8 curated India-fresher career guides chunked to ~300 tokens and embedded into `kb_chunks` for citation-grounded roadmaps.

## Architecture (Stage 1 Foundation)

- **API:** FastAPI (async) + `slowapi` rate limiting + structured JSON logs with `X-Request-ID`.
- **Database:** PostgreSQL 16 + `pgvector` (`vector(384)` with HNSW cosine indexes + stored weighted `tsvector` GIN indexes). See [docs/schema.md](docs/schema.md).
- **LLM:** Anthropic Claude (`CLAUDE_MODEL` configurable via env).
- **Embeddings:** Local `BAAI/bge-small-en-v1.5` (384 dims) via `fastembed` — zero extra API keys.

## Running Locally

### With Docker Compose
```bash
cp .env.example .env
# Add your ANTHROPIC_API_KEY in .env
docker compose up --build
```

The API will run migrations automatically and expose `GET http://localhost:8000/health`.

### Local Python Development
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
```

### Tests & Linting
```bash
ruff check .
pytest -v
```
