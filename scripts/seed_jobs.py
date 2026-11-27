"""Idempotent loader for seed jobs, canonical skills, embeddings, and KB RAG chunks."""

import argparse
import asyncio
import json
import logging
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models import Job, JobEmbedding, JobSkill, KBChunk, Skill
from app.db.session import async_session_factory
from app.logging_config import configure_logging
from app.services.chunker import chunk_markdown
from app.services.embeddings import (
    build_job_embedding_text,
    compute_content_hash,
    embed_texts,
)
from app.services.skills import SKILL_TAXONOMY, extract_skills

logger = logging.getLogger(__name__)
DEFAULT_SEED_FILE = Path("data/jobs_seed.json")
DEFAULT_KB_DIR = Path("data/kb")


async def sync_skill_taxonomy(session: AsyncSession) -> dict[str, int]:
    """Ensure all ~150 canonical skills exist in `skills` and return name -> id map."""
    rows = [{"name": name, "category": category} for name, category, _ in SKILL_TAXONOMY]
    stmt = pg_insert(Skill).values(rows).on_conflict_do_nothing(index_elements=["name"])
    await session.execute(stmt)
    await session.flush()

    result = await session.execute(select(Skill.id, Skill.name))
    return {name: skill_id for skill_id, name in result.all()}


async def upsert_jobs_batch(
    session: AsyncSession,
    raw_jobs: list[dict[str, Any]],
    skill_map: dict[str, int],
) -> dict[str, int]:
    """Upsert jobs by source_url; only re-embed and re-extract skills for new/changed rows."""
    settings = get_settings()
    stats = {"inserted": 0, "updated": 0, "unchanged": 0, "embedded": 0}
    if not raw_jobs:
        return stats

    source_urls = [j["source_url"] for j in raw_jobs]
    existing_res = await session.execute(
        select(
            Job.id,
            Job.source_url,
            Job.content_hash,
            JobEmbedding.job_id.is_not(None),
        )
        .outerjoin(JobEmbedding, JobEmbedding.job_id == Job.id)
        .where(Job.source_url.in_(source_urls))
    )
    existing_by_url: dict[str, tuple[uuid.UUID, str, bool]] = {
        url: (job_id, content_hash, has_embedding)
        for job_id, url, content_hash, has_embedding in existing_res.all()
    }

    changed_jobs: list[tuple[uuid.UUID, dict[str, Any], list[Any], datetime, str, bool]] = []

    for item in raw_jobs:
        posted_at_raw = item.get("posted_at")
        if isinstance(posted_at_raw, str):
            posted_at = datetime.fromisoformat(posted_at_raw.replace("Z", "+00:00"))
        elif isinstance(posted_at_raw, datetime):
            posted_at = posted_at_raw
        else:
            posted_at = datetime.now(UTC)

        c_hash = compute_content_hash(
            title=item["title"],
            company=item["company"],
            location=item["location"],
            remote=bool(item.get("remote", False)),
            salary_min=item.get("salary_min"),
            salary_max=item.get("salary_max"),
            description=item["description"],
        )

        existing = existing_by_url.get(item["source_url"])
        if existing and existing[1] == c_hash and existing[2]:
            stats["unchanged"] += 1
            continue

        extracted = extract_skills(item["title"], item["description"])
        is_new = existing is None
        if existing:
            job_id = existing[0]
            stats["updated"] += 1
        else:
            job_id = uuid.uuid4()
            stats["inserted"] += 1

        changed_jobs.append((job_id, item, extracted, posted_at, c_hash, is_new))

    # Release the database connection while the CPU-bound model computes embeddings.
    await session.rollback()
    if not changed_jobs:
        return stats

    # Batch-embed ONLY new or changed jobs
    embed_inputs = [
        build_job_embedding_text(
            title=item["title"],
            company=item["company"],
            location=item["location"],
            remote=bool(item.get("remote", False)),
            description=item["description"],
            skills=[s.name for s in extracted],
        )
        for _, item, extracted, _, _, _ in changed_jobs
    ]
    vectors = embed_texts(embed_inputs, batch_size=4)
    stats["embedded"] = len(vectors)

    for job_id, item, _, posted_at, c_hash, is_new in changed_jobs:
        if is_new:
            session.add(
                Job(
                    id=job_id,
                    title=item["title"],
                    company=item["company"],
                    location=item["location"],
                    remote=bool(item.get("remote", False)),
                    salary_min=item.get("salary_min"),
                    salary_max=item.get("salary_max"),
                    description=item["description"],
                    source=item.get("source", "seed"),
                    source_url=item["source_url"],
                    posted_at=posted_at,
                    status=item.get("status", "active"),
                    content_hash=c_hash,
                )
            )
            continue

        job_obj = await session.get(Job, job_id)
        if job_obj is None:
            raise RuntimeError(f"Seed job {job_id} disappeared before it could be updated")
        job_obj.title = item["title"]
        job_obj.company = item["company"]
        job_obj.location = item["location"]
        job_obj.remote = bool(item.get("remote", False))
        job_obj.salary_min = item.get("salary_min")
        job_obj.salary_max = item.get("salary_max")
        job_obj.description = item["description"]
        job_obj.source = item.get("source", "seed")
        job_obj.posted_at = posted_at
        job_obj.status = item.get("status", "active")
        job_obj.content_hash = c_hash

    await session.flush()

    for (job_id, _, extracted, _, _, _), vector in zip(changed_jobs, vectors, strict=True):
        # Upsert embedding
        emb_stmt = (
            pg_insert(JobEmbedding)
            .values(job_id=job_id, embedding=vector, model=settings.embedding_model)
            .on_conflict_do_update(
                index_elements=["job_id"],
                set_={"embedding": vector, "model": settings.embedding_model},
            )
        )
        await session.execute(emb_stmt)

        # Refresh deterministic job_skills
        await session.execute(delete(JobSkill).where(JobSkill.job_id == job_id))
        skill_rows = [
            {"job_id": job_id, "skill_id": skill_map[s.name], "importance": s.importance}
            for s in extracted
            if s.name in skill_map
        ]
        if skill_rows:
            await session.execute(pg_insert(JobSkill).values(skill_rows).on_conflict_do_nothing())

    return stats


async def seed_kb_chunks(session: AsyncSession, kb_dir: Path = DEFAULT_KB_DIR) -> int:
    """Chunk markdown guides in data/kb/ to ~300 tokens, embed, and upsert into kb_chunks."""
    md_files = sorted(kb_dir.glob("*.md"))
    if not md_files:
        logger.warning("No markdown KB guides found in %s", kb_dir)
        return 0

    all_chunks = []
    source_urls: list[str] = []
    for path in md_files:
        source_url = f"kb://{path.name}"
        source_urls.append(source_url)
        content = path.read_text(encoding="utf-8")
        chunks = chunk_markdown(
            content=content,
            source_url=source_url,
            default_title=path.stem.replace("-", " ").title(),
        )
        all_chunks.extend(chunks)

    vectors = embed_texts([f"{c.title}\n{c.text}" for c in all_chunks], batch_size=4)

    await session.execute(delete(KBChunk).where(KBChunk.source_url.in_(source_urls)))
    for chunk, vector in zip(all_chunks, vectors, strict=True):
        session.add(
            KBChunk(
                id=uuid.uuid4(),
                source_url=chunk.source_url,
                title=chunk.title,
                text=chunk.text,
                embedding=vector,
            )
        )
    await session.flush()
    return len(all_chunks)


async def run_seed(
    seed_file: Path = DEFAULT_SEED_FILE,
    kb_dir: Path = DEFAULT_KB_DIR,
    if_empty: bool = False,
) -> dict[str, Any]:
    async with async_session_factory() as session:
        if if_empty:
            job_count = (await session.execute(select(func.count(Job.id)))).scalar() or 0
            kb_count = (await session.execute(select(func.count(KBChunk.id)))).scalar() or 0
            if job_count > 0 and kb_count > 0:
                logger.info(
                    "Database already seeded (%d jobs, %d kb_chunks); skipping (--if-empty).",
                    job_count,
                    kb_count,
                )
                return {"skipped": True, "jobs": job_count, "kb_chunks": kb_count}

        skill_map = await sync_skill_taxonomy(session)
        await session.commit()
        raw_jobs = json.loads(seed_file.read_text(encoding="utf-8"))
        job_stats = await upsert_jobs_batch(session, raw_jobs, skill_map)
        await session.commit()
        kb_chunks_count = await seed_kb_chunks(session, kb_dir)
        await session.commit()

        summary = {
            "skills_synced": len(skill_map),
            "jobs": job_stats,
            "kb_chunks": kb_chunks_count,
        }
        logger.info("Seed completed: %s", summary)
        return summary


def main() -> None:
    configure_logging()
    parser = argparse.ArgumentParser(description="Seed Compass jobs, skills, and KB chunks.")
    parser.add_argument("--seed-file", type=Path, default=DEFAULT_SEED_FILE)
    parser.add_argument("--kb-dir", type=Path, default=DEFAULT_KB_DIR)
    parser.add_argument(
        "--if-empty",
        action="store_true",
        help="Skip seeding if jobs and kb_chunks already contain rows.",
    )
    args = parser.parse_args()
    result = asyncio.run(
        run_seed(seed_file=args.seed_file, kb_dir=args.kb_dir, if_empty=args.if_empty)
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
