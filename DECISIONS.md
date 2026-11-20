# Architecture & Engineering Decisions

One-line log of non-obvious choices made while building **Compass** (for easy reference in interviews).

- **Hand-written agent loop over LangChain**: Keeps control flow, tool schemas, retries, and streaming explicit and easy to debug/explain.
- **Monthly INR for `salary_min` / `salary_max`**: Indian fresher/intern queries naturally express compensation per month (e.g. "50K+ in Bengaluru" = ₹50,000/month = ₹6 LPA); storing monthly INR avoids unit ambiguity.
- **Single async Postgres driver (`asyncpg`) for both FastAPI and Alembic**: Avoids dual-driver dependency drift and normalizes Neon/Render `sslmode=require` URLs cleanly in `app/db/session.py`.
- **`BAAI/bge-small-en-v1.5` (384-dim) via `fastembed`**: Runs locally on ONNX Runtime with zero extra API keys, fast cold starts, and compact `vector(384)` storage for HNSW indexes.
- **HNSW cosine index (`m=16, ef_construction=64`) over IVFFlat**: Works accurately even on dynamically updated tables without needing periodic index retraining as jobs are ingested.
- **Stored generated `tsvector` with weighted fields (`title` A, `company` B, `description` C)**: Keeps full-text search automatically in sync on every insert/update with zero trigger boilerplate.
- **JSONB string list for `profiles.skills`**: Enables pure SQL set-difference joins against `job_skills` via `jsonb_array_elements_text` for deterministic, fast `skill_gap` queries.
- **Single `CLAUDE_MODEL` config variable**: Allows switching between Claude Haiku/Sonnet/Opus without touching application code.
- **Anonymous UUID identity via cookie + header (`X-Compass-User-Id`)**: Preserves cross-session memory immediately without login friction while supporting both browser and API clients.
- **Neon `-pooler.` `statement_cache_size=0` handling**: Disables asyncpg prepared statement caching automatically when using PgBouncer transaction poolers on Neon.
- **Deterministic 150-skill regex taxonomy over LLM skill extraction**: Guarantees zero cost, fast reproducible seeding, boundary-safe matching (`c++`, `node.js`, `ci/cd`), and consistent `skill_gap` SQL joins.
- **`content_hash` SHA-256 change detection in `seed_jobs.py` and `ingest_jobs.py`**: Ensures re-runs only compute embeddings and refresh `job_skills` for newly added or modified rows.
- **Heading-aware ~300-token markdown chunking for `kb_chunks`**: Preserves role and section context in each chunk's title for cleaner RAG citations in roadmaps.
