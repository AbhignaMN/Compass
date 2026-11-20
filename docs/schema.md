# Compass Database Schema

Compass uses **PostgreSQL 16** with the **`pgvector`** extension, managed exclusively through Alembic migrations (`alembic/versions/`). All embeddings are 384-dimensional vectors generated locally by `BAAI/bge-small-en-v1.5` via `fastembed`.

## Tables

### 1. `users`
Anonymous or identified user accounts created automatically on first visit.

| Column | Type | Notes |
| --- | --- | --- |
| `id` | `UUID` (PK) | Anonymous user identifier persisted in cookie / `localStorage`. |
| `created_at` | `TIMESTAMPTZ` | Creation timestamp (`now()`). |

### 2. `profiles`
Structured career profile built incrementally during conversation and editable in the UI side panel.

| Column | Type | Notes |
| --- | --- | --- |
| `user_id` | `UUID` (PK, FK -> `users.id`, UNIQUE) | One-to-one with `users`. |
| `skills` | `JSONB` | Canonical lowercase skill array (e.g. `["python", "sql", "fastapi"]`). Joined via `jsonb_array_elements_text` in `skill_gap`. |
| `interests` | `TEXT[]` | Preferred domains/roles (e.g. `{"backend", "ai_ml"}`). |
| `location_pref` | `TEXT` | Preferred city (e.g. `"Bengaluru"`, `"Remote"`). |
| `remote_ok` | `BOOLEAN` | Whether remote roles are acceptable (default `true`). |
| `salary_min` | `INTEGER` | Minimum monthly salary in INR (e.g. `50000` = ₹50K/month = 6 LPA). |
| `experience_level` | `TEXT` | e.g. `student`, `intern`, `fresher`, `junior`. |
| `goals` | `TEXT` | Free-text career goal summary. |
| `updated_at` | `TIMESTAMPTZ` | Last profile update timestamp. |

### 3. `jobs`
Normalized job postings from seed data and live public job feeds.

| Column | Type | Notes |
| --- | --- | --- |
| `id` | `UUID` (PK) | Internal job ID referenced by agent citations (`job_id`). |
| `title`, `company`, `location` | `TEXT` | Core posting fields. |
| `remote` | `BOOLEAN` | Remote eligibility flag for SQL hard filtering. |
| `salary_min`, `salary_max` | `INTEGER` | Monthly INR salary band (nullable when undisclosed). |
| `description` | `TEXT` | Full job description text. |
| `source` | `TEXT` | Origin (`seed`, `remotive`, `arbeitnow`). |
| `source_url` | `TEXT` (UNIQUE) | Deduplication anchor across ingestion runs. |
| `posted_at` | `TIMESTAMPTZ` | Posting date used in freshness scoring. |
| `status` | `TEXT` | `'active'` or `'closed'`; hard-filtered during retrieval. |
| `content_hash` | `TEXT` | SHA-256 hash of title + company + description + location + salary; only changed rows trigger re-embedding. |
| `tsv` | `TSVECTOR` (GENERATED STORED) | Weighted full-text vector: `title` (`A`), `company` (`B`), `description` (`C`). |

### 4. `job_embeddings`
Dense semantic representations separated from `jobs` so text metadata stays compact and re-embedding is cleanly isolated.

| Column | Type | Notes |
| --- | --- | --- |
| `job_id` | `UUID` (PK, FK -> `jobs.id`) | One-to-one with `jobs` (`ON DELETE CASCADE`). |
| `embedding` | `vector(384)` | Normalized `BAAI/bge-small-en-v1.5` vector. |
| `model` | `TEXT` | Embedding model identifier for safe model migrations. |
| `created_at` | `TIMESTAMPTZ` | Timestamp when the vector was computed. |

### 5. `skills` & `job_skills`
Deterministic, normalized skill taxonomy extracted via regex (not LLM) for fast SQL skill-overlap and skill-gap queries.

- `skills(id SERIAL PK, name TEXT UNIQUE, category TEXT)`
- `job_skills(job_id UUID FK, skill_id INT FK, importance SMALLINT, PK(job_id, skill_id))` where `importance` is `3` (must-have), `2` (core), or `1` (nice-to-have).

### 6. `conversations` & `messages`
Multi-turn conversation storage with rolling summarization support.

- `conversations(id UUID PK, user_id UUID FK, summary TEXT, created_at, updated_at)`
- `messages(id UUID PK, conversation_id UUID FK, role TEXT, content TEXT, tool_calls JSONB, created_at)`

### 7. `memories`
Cross-session long-term memory extracted after each turn.

| Column | Type | Notes |
| --- | --- | --- |
| `id` | `UUID` (PK) | Memory identifier. |
| `user_id` | `UUID` (FK -> `users.id`) | Owning user. |
| `type` | `TEXT` | `CHECK (type IN ('fact', 'preference', 'goal'))`. |
| `text` | `TEXT` | Concise durable statement. |
| `embedding` | `vector(384)` | Used for top-k semantic recall and similarity-based deduplication. |
| `last_seen`, `created_at` | `TIMESTAMPTZ` | Recency tracking when a memory is reinforced or updated. |

### 8. `interactions`
Implicit and explicit user feedback on recommended jobs.

- `interactions(id UUID PK, user_id UUID FK, job_id UUID FK, event TEXT CHECK (event IN ('shown', 'clicked', 'saved', 'dismissed')), created_at)`
- Feeds a small ranking boost (`saved`) or penalty (`dismissed`) in `rank_jobs`.

### 9. `roadmaps`
Versioned, structured learning roadmaps generated via RAG over `kb_chunks`.

- `roadmaps(id UUID PK, user_id UUID FK, target_role TEXT, plan JSONB, version INT, created_at)`

### 10. `kb_chunks`
Chunked (~300-token) curated career guides used to ground roadmaps with citations.

- `kb_chunks(id UUID PK, source_url TEXT, title TEXT, text TEXT, embedding vector(384), tsv TSVECTOR GENERATED STORED, created_at)`

---

## Indexes & Rationale

| Table | Index | Type | Why |
| --- | --- | --- | --- |
| `jobs` | `ix_jobs_tsv_gin` | GIN | Sub-millisecond full-text search over weighted `title`/`company`/`description`. |
| `jobs` | `ix_jobs_status_posted_at` | B-tree | Hard filter on `status = 'active'` and sorting/decay by `posted_at`. |
| `jobs` | `ix_jobs_location`, `ix_jobs_remote`, `ix_jobs_salary_min`, `ix_jobs_salary_max` | B-tree | Fast SQL hard filtering before or alongside vector/keyword search. |
| `jobs` | `ix_jobs_content_hash` | B-tree | Instant change detection during incremental job ingestion. |
| `job_embeddings` | `ix_job_embeddings_hnsw_cosine` | HNSW (`vector_cosine_ops`, `m=16`, `ef_construction=64`) | Approximate nearest-neighbor cosine search that handles live inserts without periodic IVFFlat rebuilds. |
| `job_skills` | `ix_job_skills_skill_id` | B-tree | Reverse lookups from a skill to all jobs requiring it (PK already indexes `job_id`). |
| `conversations` | `ix_conversations_user_created` | B-tree | Fetch latest conversations for a user in descending order. |
| `messages` | `ix_messages_conv_created` | B-tree | Load the last N messages of a conversation efficiently. |
| `memories` | `ix_memories_user_type` | B-tree | Filter user memories by category (`fact`, `preference`, `goal`) during conflict updates and profile display. |
| `memories` | `ix_memories_hnsw_cosine` | HNSW (`vector_cosine_ops`) | Fast semantic recall (`recall_memory`) and cosine deduplication checks. |
| `interactions` | `ix_interactions_user_job`, `ix_interactions_user_event_created` | B-tree | Fast lookup of user `saved`/`dismissed` flags during `rank_jobs`. |
| `roadmaps` | `ix_roadmaps_user_created` | B-tree | Fetch the latest roadmap version per user (`GET /roadmap/{user_id}`). |
| `kb_chunks` | `ix_kb_chunks_tsv_gin`, `ix_kb_chunks_hnsw_cosine`, `ix_kb_chunks_source_url` | GIN, HNSW, B-tree | Hybrid RAG retrieval over career guides and idempotent re-indexing by `source_url`. |
