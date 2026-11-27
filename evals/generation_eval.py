"""Generation evaluation: 30 conversations scored by LLM-as-judge + hard job_id DB check."""

import asyncio
import json
import logging
import re
import uuid
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from app.agent.llm import LLMClient
from app.agent.loop import parse_structured_reply
from app.config import get_settings
from app.search.ranking import rank_jobs
from app.search.retrieval import reciprocal_rank_fusion
from app.search.schemas import SearchCandidate
from app.services.embeddings import embed_text
from evals.retrieval_eval import (
    IndexedSeedJob,
    _passes_hard_filters,
    _to_search_candidate,
    load_indexed_seed_jobs,
)

logger = logging.getLogger(__name__)

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE | re.DOTALL)
_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


class JudgeRubricScore(BaseModel):
    groundedness: int = Field(ge=1, le=5)
    relevance: int = Field(ge=1, le=5)
    actionability: int = Field(ge=1, le=5)
    notes: str = ""


GENERATION_PROMPTS_30: list[dict[str, Any]] = [
    {"id": "c01", "skills": ["python", "sql"], "loc": "Bengaluru", "sal": 50000, "msg": "I'm a fresher, like Python and SQL, hate sales, want 50K+ in Bengaluru."},
    {"id": "c02", "skills": ["python", "pytorch"], "loc": "Bengaluru", "sal": 30000, "msg": "Looking for an AI/LLM internship in Bengaluru with PyTorch."},
    {"id": "c03", "skills": ["react", "typescript"], "loc": "Remote", "sal": 45000, "msg": "I know React and TypeScript and want a remote fresher full-stack job."},
    {"id": "c04", "skills": ["sql", "excel", "power bi"], "loc": "Gurugram", "sal": 40000, "msg": "Help me find Junior Data Analyst roles in Gurugram paying 40K+."},
    {"id": "c05", "skills": ["linux", "owasp", "python"], "loc": "Pune", "sal": 40000, "msg": "I'm interested in cybersecurity AppSec or SOC fresher roles in Pune."},
    {"id": "c06", "skills": ["python", "pytest", "postman"], "loc": "Hyderabad", "sal": 38000, "msg": "Are there QA automation or SDET fresher jobs in Hyderabad?"},
    {"id": "c07", "skills": ["docker", "aws", "linux"], "loc": "Bengaluru", "sal": 45000, "msg": "I want a DevOps / Cloud fresher role using Docker and AWS."},
    {"id": "c08", "skills": ["sql", "figma"], "loc": "Bengaluru", "sal": 50000, "msg": "Can I get an Associate Product Manager fresher job in Bengaluru?"},
    {"id": "c09", "skills": [], "loc": None, "sal": None, "msg": "Honestly I have no idea what career path to pick after BTech."},
    {"id": "c10", "skills": ["python"], "loc": "Bengaluru", "sal": 40000, "msg": "I got rejected 10 times and feel hopeless. What should I do next?"},
    {"id": "c11", "skills": ["java", "spring boot", "sql"], "loc": "Bengaluru", "sal": 55000, "msg": "Find Java Spring Boot backend fresher jobs in Bengaluru."},
    {"id": "c12", "skills": ["node.js", "express.js", "mongodb"], "loc": "Hyderabad", "sal": 45000, "msg": "Looking for Node.js backend or MERN full-stack jobs in Hyderabad."},
    {"id": "c13", "skills": ["python", "fastapi", "postgresql"], "loc": "Remote", "sal": 55000, "msg": "Show me remote Python FastAPI backend roles paying 55K+."},
    {"id": "c14", "skills": ["python", "pandas", "scikit-learn"], "loc": "Bengaluru", "sal": 25000, "msg": "I want a Data Science internship in Bengaluru."},
    {"id": "c15", "skills": ["selenium", "java"], "loc": "Pune", "sal": 38000, "msg": "Any Selenium Java test automation fresher openings in Pune?"},
    {"id": "c16", "skills": ["python", "llms", "rag"], "loc": "Remote", "sal": 60000, "msg": "I built a RAG chatbot with Python. Show me remote GenAI roles."},
    {"id": "c17", "skills": ["go", "docker"], "loc": "Gurugram", "sal": 55000, "msg": "Are there Golang backend fresher roles in Gurugram?"},
    {"id": "c18", "skills": ["sql", "dbt", "python"], "loc": "Remote", "sal": 45000, "msg": "Looking for remote Analytics Engineer or Data Engineer fresher jobs."},
    {"id": "c19", "skills": ["python", "sql"], "loc": "Bengaluru", "sal": 500000, "msg": "Find me a 5 lakh/month remote fresher quantum hardware job."},
    {"id": "c20", "skills": ["python"], "loc": "Bengaluru", "sal": 50000, "msg": "Can you guarantee me a stock tip and draft a rental agreement?"},
    {"id": "c21", "skills": ["react", "next.js", "tailwind css"], "loc": "Bengaluru", "sal": 50000, "msg": "I love building UIs with Next.js and Tailwind. What fresher jobs fit me?"},
    {"id": "c22", "skills": ["burp suite", "owasp", "nmap"], "loc": "Hyderabad", "sal": 40000, "msg": "Show me VAPT or penetration testing fresher roles in Hyderabad."},
    {"id": "c23", "skills": ["python", "django", "postgresql"], "loc": "Pune", "sal": 45000, "msg": "Find Django backend developer fresher roles in Pune."},
    {"id": "c24", "skills": ["typescript", "playwright"], "loc": "Remote", "sal": 40000, "msg": "Remote Playwright SDET fresher jobs please."},
    {"id": "c25", "skills": ["sql", "tableau", "a/b testing"], "loc": "Gurugram", "sal": 45000, "msg": "I enjoy product metrics and A/B testing—find Product Analyst roles."},
    {"id": "c26", "skills": ["kubernetes", "terraform", "aws"], "loc": "Bengaluru", "sal": 50000, "msg": "Cloud / SRE fresher jobs in Bengaluru with Terraform and AWS."},
    {"id": "c27", "skills": ["python", "computer vision", "pytorch"], "loc": "Bengaluru", "sal": 60000, "msg": "Any junior computer vision engineer roles in Bengaluru?"},
    {"id": "c28", "skills": ["react native", "typescript"], "loc": "Bengaluru", "sal": 50000, "msg": "Looking for entry-level React Native mobile/web roles."},
    {"id": "c29", "skills": ["python", "apache spark", "sql"], "loc": "Hyderabad", "sal": 45000, "msg": "Junior Data Engineer roles with Spark and SQL in Hyderabad."},
    {"id": "c30", "skills": ["python", "sql"], "loc": "Remote", "sal": 35000, "msg": "I changed my mind—skip Bengaluru and only show remote internships or fresher jobs."},
]


def _retrieve_top_jobs_for_case(
    case: dict[str, Any], indexed_jobs: list[IndexedSeedJob]
) -> list[SearchCandidate]:
    import numpy as np

    profile = {
        "skills": case["skills"],
        "location_pref": case["loc"],
        "remote_only": (case["loc"] or "").lower() == "remote",
        "remote_ok": True,
        "salary_min": case["sal"],
    }
    filtered = [j for j in indexed_jobs if _passes_hard_filters(j, profile)]
    if not filtered:
        return []

    q_vec = np.asarray(embed_text(case["msg"]), dtype=np.float32)
    q_norm = float(np.linalg.norm(q_vec))
    if q_norm > 0:
        q_vec = q_vec / q_norm

    scored = [(j.job_id, float(np.dot(j.vector, q_vec))) for j in filtered]
    scored.sort(key=lambda x: x[1], reverse=True)
    top_ids = [jid for jid, _ in scored[:15]]
    rrf = reciprocal_rank_fusion([top_ids], k=60)
    by_id = {j.job_id: j for j in filtered}
    sim_map = dict(scored)
    cands = [
        _to_search_candidate(by_id[jid], vec_sim=sim_map[jid], kw_score=0.0, rrf_score=rrf[jid])
        for jid in top_ids
    ]
    ranked = rank_jobs(profile, cands, top_n=15)[:3]
    ranked_ids = [r.job_id for r in ranked]
    return [c for c in cands if c.job_id in ranked_ids][:3]


def _parse_judge_score(raw_text: str) -> JudgeRubricScore:
    cleaned = _FENCE_RE.sub("", raw_text.strip()).strip()
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        match = _JSON_RE.search(cleaned)
        if not match:
            raise
        data = json.loads(match.group(0))
    return JudgeRubricScore.model_validate(data)


async def run_generation_eval(
    *,
    llm_client: LLMClient | None = None,
    limit: int = 30,
    delay_seconds: float = 0.6,
) -> dict[str, Any]:
    """Evaluate Compass replies on 30 conversations using LLM-as-judge + hard DB job_id check."""
    settings = get_settings()
    llm = llm_client or LLMClient(settings)
    indexed = load_indexed_seed_jobs()
    valid_db_job_ids = {str(j.job_id) for j in indexed}

    cases = GENERATION_PROMPTS_30[:limit]
    if not llm.is_configured():
        return {
            "evaluated": 0,
            "skipped": True,
            "reason": "No LLM API key configured",
        }

    grounded_scores: list[int] = []
    relevance_scores: list[int] = []
    actionability_scores: list[int] = []
    total_referenced_ids = 0
    valid_referenced_ids = 0
    invalid_id_examples: list[str] = []
    failures = 0

    for case in cases:
        top_cands = _retrieve_top_jobs_for_case(case, indexed)
        cand_context = [
            {
                "job_id": str(c.job_id),
                "title": c.title,
                "company": c.company,
                "location": c.location,
                "remote": c.remote,
                "salary_min": c.salary_min,
                "salary_max": c.salary_max,
                "skills": [s.name for s in c.skills[:6]],
            }
            for c in top_cands
        ]

        mentor_system = (
            "You are Compass, a warm, concise career mentor for freshers in India. "
            "Recommend ONLY jobs present in the tool_candidates JSON below and NEVER invent jobs or salaries. "
            "If tool_candidates is empty or irrelevant to the request, say honestly you don't have a strong match. "
            "Politely decline non-career requests (stocks/legal). "
            "Return ONLY JSON: {\"reply\": \"2-5 short sentences\", \"suggested_replies\": [\"chip1\", \"chip2\"], \"referenced_job_ids\": [\"exact uuid from tool_candidates\"]}"
        )
        mentor_prompt = (
            f"User profile skills: {case['skills']}, preferred location: {case['loc']}, min salary: {case['sal']}\n"
            f"User message: {case['msg']}\n\n"
            f"tool_candidates:\n{json.dumps(cand_context, indent=2)}"
        )

        try:
            gen_resp = await llm.complete(
                system=mentor_system,
                messages=[{"role": "user", "content": mentor_prompt}],
                max_tokens=900,
                temperature=0.2,
                json_mode=True,
            )
            parsed = parse_structured_reply(gen_resp.text)

            # Hard DB job_id existence check
            for jid in parsed.referenced_job_ids:
                total_referenced_ids += 1
                if jid in valid_db_job_ids:
                    valid_referenced_ids += 1
                else:
                    invalid_id_examples.append(f"{case['id']}:{jid}")

            # LLM-as-judge rubric (1-5 each)
            judge_system = (
                "You are a strict career-mentor evaluator. Score the assistant reply from 1 to 5 on:\n"
                "- groundedness (5=only cites provided jobs/facts or honestly admits no match; 1=hallucinates jobs/salaries)\n"
                "- relevance (5=directly addresses user constraints, empathy/safety if applicable)\n"
                "- actionability (5=gives clear, concrete next step or follow-up)\n"
                "Return ONLY JSON: {\"groundedness\": 1-5, \"relevance\": 1-5, \"actionability\": 1-5, \"notes\": \"short reason\"}"
            )
            judge_prompt = (
                f"User message: {case['msg']}\n"
                f"Available DB jobs: {json.dumps(cand_context)}\n"
                f"Assistant reply: {parsed.reply}\n"
                f"Referenced job_ids: {parsed.referenced_job_ids}\n"
                f"Suggested chips: {parsed.suggested_replies}"
            )
            judge_resp = await llm.complete(
                system=judge_system,
                messages=[{"role": "user", "content": judge_prompt}],
                model=settings.active_memory_model,
                max_tokens=700,
                temperature=0.0,
                json_mode=True,
            )
            score = _parse_judge_score(judge_resp.text)
            grounded_scores.append(score.groundedness)
            relevance_scores.append(score.relevance)
            actionability_scores.append(score.actionability)
        except (ValidationError, json.JSONDecodeError, Exception) as exc:
            logger.warning("Generation eval case %s failed: %s", case["id"], exc)
            failures += 1

        if delay_seconds > 0:
            await asyncio.sleep(delay_seconds)

    evaluated = len(grounded_scores)
    return {
        "evaluated": evaluated,
        "target_cases": len(cases),
        "failures": failures,
        "provider": settings.llm_provider,
        "model": settings.active_llm_model,
        "judge_model": settings.active_memory_model,
        "avg_groundedness": round(sum(grounded_scores) / max(1, evaluated), 2),
        "avg_relevance": round(sum(relevance_scores) / max(1, evaluated), 2),
        "avg_actionability": round(sum(actionability_scores) / max(1, evaluated), 2),
        "total_referenced_job_ids": total_referenced_ids,
        "valid_db_job_ids": valid_referenced_ids,
        "job_id_validity_pct": round(
            (valid_referenced_ids / total_referenced_ids) * 100.0, 2
        )
        if total_referenced_ids > 0
        else 100.0,
        "invalid_id_examples": invalid_id_examples,
    }


def verify_recommended_ids_exist_in_db(
    recommended_ids: list[str], valid_db_ids: set[str]
) -> tuple[bool, list[str]]:
    """Hard check verifying every recommended job_id exists in the database."""
    missing = [jid for jid in recommended_ids if jid not in valid_db_ids]
    return len(missing) == 0, missing


# Keep uuid cleanly referenced
_ = uuid.NAMESPACE_URL
