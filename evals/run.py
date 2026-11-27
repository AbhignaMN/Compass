"""CLI runner: `python -m evals.run` -> runs retrieval + generation evals and writes evals/results.md."""

import argparse
import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.logging_config import configure_logging
from evals.generation_eval import run_generation_eval
from evals.retrieval_eval import run_retrieval_eval

RESULTS_MD_PATH = Path("evals/results.md")


def format_results_markdown(
    retrieval: dict[str, Any],
    generation: dict[str, Any] | None,
) -> str:
    ts = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    methods = retrieval["methods"]

    lines = [
        "# Compass Evaluation Results",
        "",
        f"_Generated on {ts} via `python -m evals.run`._",
        "",
        "## 1. Retrieval & Ranking Benchmark (50 Labelled Fresher Profiles, 320 Seed Jobs)",
        "",
        "### Ground-Truth Labelling Rules",
        "- Test profiles (`evals/test_profiles.json`) span all 8 Indian fresher tracks (AI/ML, Backend, Full-Stack, Data, Cybersecurity, QA/SDET, Product, DevOps) across Bengaluru, Hyderabad, Pune, Gurugram, Mumbai, Chennai, Noida, and Remote.",
        "- Hard SQL-equivalent filters (`status='active'`, city/remote, `salary_max >= salary_min`) are applied equally to every method.",
        "- **Grade 2 (highly relevant):** track matches, experience level (`intern` vs `fresher`) matches, and skill overlap >= 0.35.",
        "- **Grade 1 (relevant):** track matches and skill overlap >= 0.15 (or experience level matches with >= 1 overlapping core skill).",
        "- Embeddings: local `BAAI/bge-small-en-v1.5` (384 dims via `fastembed`). Ranking weights: `0.50*semantic + 0.25*skill_overlap + 0.15*preference_fit + 0.10*freshness`.",
        "",
        "| Retrieval Strategy | Recall@10 | nDCG@10 |",
        "| --- | ---: | ---: |",
        f"| Vector-only (`bge-small-en-v1.5`) | {methods['vector_only']['recall_at_10']:.4f} | {methods['vector_only']['ndcg_at_10']:.4f} |",
        f"| Keyword-only (Weighted BM25) | {methods['keyword_only']['recall_at_10']:.4f} | {methods['keyword_only']['ndcg_at_10']:.4f} |",
        f"| Hybrid (RRF, `k=60`) | {methods['hybrid']['recall_at_10']:.4f} | {methods['hybrid']['ndcg_at_10']:.4f} |",
        f"| **Hybrid + Rerank (`rank_jobs`)** | **{methods['hybrid_rerank']['recall_at_10']:.4f}** | **{methods['hybrid_rerank']['ndcg_at_10']:.4f}** |",
        "",
    ]

    lines.append("## 2. Generation Quality & Grounding Check (30 Conversations)")
    lines.append("")
    if generation and not generation.get("skipped") and generation.get("evaluated", 0) > 0:
        lines.extend(
            [
                f"- **LLM Provider / Model:** `{generation['provider']}` / `{generation['model']}` (Judge: `{generation['judge_model']}`)",
                f"- **Conversations Scored:** {generation['evaluated']} / {generation['target_cases']} (parse/API errors: {generation['failures']})",
                "",
                "| Metric | Result |",
                "| --- | ---: |",
                f"| Groundedness (1–5) | **{generation['avg_groundedness']:.2f} / 5.00** |",
                f"| Relevance (1–5) | **{generation['avg_relevance']:.2f} / 5.00** |",
                f"| Actionability (1–5) | **{generation['avg_actionability']:.2f} / 5.00** |",
                f"| Hard Check: Valid DB `job_id`s | **{generation['valid_db_job_ids']} / {generation['total_referenced_job_ids']} ({generation['job_id_validity_pct']:.1f}%)** |",
                "",
            ]
        )
    else:
        lines.extend(
            [
                "_LLM generation eval skipped (no API key set or `--skip-llm` passed). Run `python -m evals.run` with an LLM API key configured to populate live judge metrics._",
                "",
            ]
        )

    lines.extend(
        [
            "## 3. Agent Tool & Cross-Session Memory Suite",
            "",
            "Run `pytest tests/test_stage6_conversations.py tests/test_stage8_evals.py -v` to verify:",
            "- All 16 scripted multi-turn mentor scenarios (cold start, vague user, empathy, changed mind, reference resolution, comparisons, safety).",
            "- Correct tool selection & Pydantic validation retry-once recovery.",
            "- Cross-session recall of facts stated in Turn 1 inside a brand-new conversation.",
            "",
        ]
    )
    return "\n".join(lines)


async def _run_all(skip_llm: bool, gen_limit: int, delay: float) -> dict[str, Any]:
    retrieval = run_retrieval_eval(save_profiles=True)
    generation: dict[str, Any] | None = None
    if not skip_llm:
        generation = await run_generation_eval(limit=gen_limit, delay_seconds=delay)
    md = format_results_markdown(retrieval, generation)
    RESULTS_MD_PATH.write_text(md, encoding="utf-8")
    return {"retrieval": retrieval, "generation": generation, "results_path": str(RESULTS_MD_PATH)}


def main() -> None:
    configure_logging("WARNING")
    parser = argparse.ArgumentParser(description="Run Compass retrieval and generation evals.")
    parser.add_argument("--skip-llm", action="store_true", help="Run retrieval evals only (no LLM cost).")
    parser.add_argument("--gen-limit", type=int, default=30, help="Number of generation conversations (default 30).")
    parser.add_argument("--delay", type=float, default=0.5, help="Delay between LLM eval calls in seconds.")
    args = parser.parse_args()
    out = asyncio.run(_run_all(skip_llm=args.skip_llm, gen_limit=args.gen_limit, delay=args.delay))
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
