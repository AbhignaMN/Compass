# Compass

> *Find your true north in your career.*

**Compass** is an end-to-end conversational AI career mentor for freshers and interns in India. Built from scratch without agent frameworks, Compass combines hybrid PostgreSQL retrieval (`pgvector` HNSW + full-text search with Reciprocal Rank Fusion), deterministic skill-gap analysis, a hand-written Claude tool-use agent loop, cross-session memory, and RAG-grounded learning roadmaps.

## Current Progress

- [x] **Stage 1:** FastAPI async scaffold, structured JSON logging with request IDs, rate limiting, SQLAlchemy 2 + Alembic Postgres/pgvector schema (`docs/schema.md`), multi-stage `Dockerfile` + `docker-compose.yml`, and `GET /health`.
- [ ] **Stages 2–10:** Seed & live job ingestion, hybrid retrieval & ranking, hand-written Claude agent loop, short/long-term memory, RAG roadmaps, Next.js UI (Colourful / Midnight / Mahogany themes), evals, and Render + Neon deployment.

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
