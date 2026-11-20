"""Live job ingestion from free public APIs (Remotive / Arbeitnow).

Normalizes postings, dedupes by content_hash, upserts into Postgres, extracts
deterministic regex skills, and re-embeds ONLY newly added or modified rows.
"""

import argparse
import asyncio
import json
import logging
import re
from datetime import UTC, datetime
from html import unescape
from typing import Any

import httpx

from app.db.session import async_session_factory
from app.logging_config import configure_logging
from scripts.seed_jobs import sync_skill_taxonomy, upsert_jobs_batch

logger = logging.getLogger(__name__)

REMOTIVE_URL = "https://remotive.com/api/remote-jobs"
ARBEITNOW_URL = "https://www.arbeitnow.com/api/job-board-api"

_HTML_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")
_SALARY_NUM_RE = re.compile(r"(\d[\d,]{2,})")


def strip_html(raw_html: str) -> str:
    """Convert raw HTML job descriptions to clean, readable plain text."""
    text = unescape(raw_html or "")
    text = re.sub(r"</(p|div|li|br|h[1-6])>", "\n", text, flags=re.IGNORECASE)
    text = _HTML_TAG_RE.sub(" ", text)
    lines = [_WHITESPACE_RE.sub(" ", line).strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def parse_monthly_inr_salary(salary_str: str | None) -> tuple[int | None, int | None]:
    """Best-effort parse of salary strings into approximate monthly INR (returns None if unclear)."""
    if not salary_str:
        return None, None
    lower = salary_str.lower()
    raw_nums = [int(n.replace(",", "")) for n in _SALARY_NUM_RE.findall(salary_str)]
    if not raw_nums:
        return None, None

    # Handle USD annual salaries often found on Remotive (convert to rough monthly INR)
    is_usd = "$" in salary_str or "usd" in lower
    is_eur = "€" in salary_str or "eur" in lower
    is_annual = any(tok in lower for tok in ("year", "yr", "annual", "pa", "lpa")) or raw_nums[0] >= 30000

    converted: list[int] = []
    for num in raw_nums[:2]:
        val = num
        if is_usd:
            val = int(num * 84)
        elif is_eur:
            val = int(num * 90)
        if is_annual:
            val = int(val / 12)
        if 10000 <= val <= 1500000:
            converted.append(val)

    if not converted:
        return None, None
    if len(converted) == 1:
        return converted[0], converted[0]
    return min(converted), max(converted)


def normalize_remotive_job(item: dict[str, Any]) -> dict[str, Any]:
    sal_min, sal_max = parse_monthly_inr_salary(item.get("salary"))
    location = (item.get("candidate_required_location") or "Remote (Global)").strip()
    return {
        "title": (item.get("title") or "Software Engineer").strip(),
        "company": (item.get("company_name") or "Unknown Company").strip(),
        "location": location,
        "remote": True,
        "salary_min": sal_min,
        "salary_max": sal_max,
        "description": strip_html(item.get("description") or "")[:6000],
        "source": "remotive",
        "source_url": str(item["url"]).strip(),
        "posted_at": item.get("publication_date") or datetime.now(UTC).isoformat(),
        "status": "active",
    }


def normalize_arbeitnow_job(item: dict[str, Any]) -> dict[str, Any]:
    created_ts = item.get("created_at")
    if isinstance(created_ts, int | float):
        posted_at = datetime.fromtimestamp(created_ts, tz=UTC).isoformat()
    else:
        posted_at = datetime.now(UTC).isoformat()
    return {
        "title": (item.get("title") or "Software Engineer").strip(),
        "company": (item.get("company_name") or "Unknown Company").strip(),
        "location": (item.get("location") or "Remote").strip(),
        "remote": bool(item.get("remote", False)),
        "salary_min": None,
        "salary_max": None,
        "description": strip_html(item.get("description") or "")[:6000],
        "source": "arbeitnow",
        "source_url": str(item["url"]).strip(),
        "posted_at": posted_at,
        "status": "active",
    }


async def fetch_public_jobs(source: str = "auto", limit: int = 40) -> list[dict[str, Any]]:
    """Fetch normalized tech jobs from Remotive (primary) or Arbeitnow (fallback)."""
    timeout = httpx.Timeout(20.0)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        sources_to_try = ["remotive", "arbeitnow"] if source == "auto" else [source]
        last_error: Exception | None = None

        for provider in sources_to_try:
            try:
                if provider == "remotive":
                    resp = await client.get(REMOTIVE_URL, params={"limit": limit})
                    resp.raise_for_status()
                    raw = resp.json().get("jobs", [])[:limit]
                    jobs = [normalize_remotive_job(item) for item in raw if item.get("url")]
                    logger.info("Fetched %d jobs from Remotive", len(jobs))
                    return jobs

                if provider == "arbeitnow":
                    resp = await client.get(ARBEITNOW_URL)
                    resp.raise_for_status()
                    raw = resp.json().get("data", [])[:limit]
                    jobs = [normalize_arbeitnow_job(item) for item in raw if item.get("url")]
                    logger.info("Fetched %d jobs from Arbeitnow", len(jobs))
                    return jobs
            except Exception as exc:
                logger.warning("Job provider %s failed: %s", provider, exc)
                last_error = exc

        if last_error:
            raise last_error
        return []


async def ingest_live_jobs(
    source: str = "auto", limit: int = 40, dry_run: bool = False
) -> dict[str, Any]:
    jobs = await fetch_public_jobs(source=source, limit=limit)
    if dry_run:
        return {
            "dry_run": True,
            "fetched": len(jobs),
            "sample_titles": [j["title"] for j in jobs[:5]],
            "provider": jobs[0]["source"] if jobs else None,
        }

    async with async_session_factory() as session:
        skill_map = await sync_skill_taxonomy(session)
        stats = await upsert_jobs_batch(session, jobs, skill_map)
        await session.commit()
    return {"fetched": len(jobs), "stats": stats}


def main() -> None:
    configure_logging()
    parser = argparse.ArgumentParser(description="Ingest live jobs from Remotive/Arbeitnow.")
    parser.add_argument("--source", choices=["auto", "remotive", "arbeitnow"], default="auto")
    parser.add_argument("--limit", type=int, default=40)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    result = asyncio.run(
        ingest_live_jobs(source=args.source, limit=args.limit, dry_run=args.dry_run)
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
