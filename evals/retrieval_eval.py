"""Retrieval evaluation over 50 labelled fresher profiles comparing 4 ranking strategies.

Evaluates Recall@10 and nDCG@10 for:
1. vector-only (384-dim BAAI/bge-small-en-v1.5 cosine similarity)
2. keyword-only (weighted BM25 over title A / company B / description C)
3. hybrid (Reciprocal Rank Fusion, k=60)
4. hybrid+rerank (RRF top-50 reranked by app.search.ranking.rank_jobs)
"""

import json
import math
import re
import uuid
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

from app.search.ranking import rank_jobs
from app.search.retrieval import reciprocal_rank_fusion
from app.search.schemas import JobSkillInfo, SearchCandidate
from app.services.embeddings import build_job_embedding_text, embed_text, embed_texts
from app.services.skills import extract_skills, normalize_skill_name

SEED_PATH = Path("data/jobs_seed.json")
PROFILES_OUT_PATH = Path("evals/test_profiles.json")

_TOKEN_RE = re.compile(r"[a-z0-9\+\#\.]{2,}")


@dataclass
class IndexedSeedJob:
    job_id: uuid.UUID
    raw: dict[str, Any]
    skills: list[JobSkillInfo]
    skill_set: set[str]
    vector: np.ndarray
    title_tokens: Counter[str]
    body_tokens: Counter[str]
    doc_len: int


def _tokenize(text_val: str) -> list[str]:
    return _TOKEN_RE.findall(text_val.lower())


def load_indexed_seed_jobs(seed_path: Path = SEED_PATH) -> list[IndexedSeedJob]:
    """Load the 320 seed jobs, extract deterministic skills, and compute local 384-dim embeddings."""
    raw_jobs = json.loads(seed_path.read_text(encoding="utf-8"))
    extracted_all = [extract_skills(j["title"], j["description"]) for j in raw_jobs]

    embed_inputs = [
        build_job_embedding_text(
            title=j["title"],
            company=j["company"],
            location=j["location"],
            remote=bool(j.get("remote", False)),
            description=j["description"],
            skills=[s.name for s in ext],
        )
        for j, ext in zip(raw_jobs, extracted_all, strict=True)
    ]
    vectors = embed_texts(embed_inputs, batch_size=4)

    indexed: list[IndexedSeedJob] = []
    for raw, ext, vec in zip(raw_jobs, extracted_all, vectors, strict=True):
        # Deterministic UUID5 from source_url so labelled eval IDs are 100% reproducible
        job_id = uuid.uuid5(uuid.NAMESPACE_URL, raw["source_url"])
        skill_infos = [
            JobSkillInfo(name=s.name, category=s.category, importance=s.importance) for s in ext
        ]
        arr = np.asarray(vec, dtype=np.float32)
        norm = float(np.linalg.norm(arr))
        if norm > 0:
            arr = arr / norm

        t_tokens = _tokenize(raw["title"] + " " + raw["company"])
        b_tokens = _tokenize(raw["description"])
        indexed.append(
            IndexedSeedJob(
                job_id=job_id,
                raw=raw,
                skills=skill_infos,
                skill_set={s.name for s in skill_infos},
                vector=arr,
                title_tokens=Counter(t_tokens),
                body_tokens=Counter(b_tokens),
                doc_len=max(1, len(t_tokens) + len(b_tokens)),
            )
        )
    return indexed


def _passes_hard_filters(job: IndexedSeedJob, profile: dict[str, Any]) -> bool:
    if job.raw.get("status", "active") != "active":
        return False
    loc_pref = (profile.get("location_pref") or "").strip().lower()
    remote_only = bool(profile.get("remote_only", False))
    if remote_only and not job.raw.get("remote", False):
        return False
    if loc_pref:
        if loc_pref == "remote":
            if not job.raw.get("remote", False) and "remote" not in job.raw["location"].lower():
                return False
        elif loc_pref not in job.raw["location"].lower() and not job.raw.get("remote", False):
            return False
    sal_min = profile.get("salary_min")
    if sal_min:
        job_hi = job.raw.get("salary_max") or job.raw.get("salary_min") or 0
        if job_hi < sal_min:
            return False
    return True


def build_50_labelled_profiles(indexed_jobs: list[IndexedSeedJob]) -> list[dict[str, Any]]:
    """Create 50 diverse Indian fresher test profiles with rule-based graded relevance labels.

    Labelling rules (transparent & deterministic):
    - Candidate job must pass the profile's hard location/remote and salary_min filters.
    - Grade 2 (highly relevant): job track matches target_track, experience_level matches
      ('intern' vs 'fresher'), and skill overlap >= 0.35.
    - Grade 1 (relevant): job track matches target_track and skill overlap >= 0.15 (or
      experience_level matches with >= 1 overlapping core skill).
    - Grade 0: everything else.
    """
    archetypes: list[dict[str, Any]] = [
        # AI / ML (8 profiles)
        {"track": "ai_ml", "exp": "intern", "loc": "Bengaluru", "sal": 25000, "skills": ["python", "pytorch", "sql", "git"], "query": "Python PyTorch AI LLM engineer internship Bengaluru"},
        {"track": "ai_ml", "exp": "fresher", "loc": "Bengaluru", "sal": 60000, "skills": ["python", "llms", "rag", "fastapi", "postgresql", "pgvector"], "query": "Applied AI LLM RAG FastAPI pgvector fresher engineer Bengaluru"},
        {"track": "ai_ml", "exp": "fresher", "loc": "Hyderabad", "sal": 55000, "skills": ["python", "machine learning", "scikit-learn", "pandas", "numpy"], "query": "Junior machine learning engineer scikit-learn pandas Hyderabad"},
        {"track": "ai_ml", "exp": "intern", "loc": "Remote", "sal": 25000, "skills": ["python", "ai agents", "pydantic", "rest api", "embeddings"], "query": "Remote LLM AI agents internship Python Pydantic embeddings"},
        {"track": "ai_ml", "exp": "fresher", "loc": "Pune", "sal": 55000, "skills": ["python", "hugging face", "nlp", "deep learning", "docker"], "query": "Associate NLP engineer Hugging Face deep learning Pune"},
        {"track": "ai_ml", "exp": "fresher", "loc": "Gurugram", "sal": 60000, "skills": ["python", "computer vision", "pytorch", "onnx", "linux"], "query": "Junior computer vision PyTorch ONNX fresher Gurugram"},
        {"track": "ai_ml", "exp": "fresher", "loc": "Remote", "sal": 60000, "skills": ["python", "llms", "rag", "fastapi", "docker"], "query": "GenAI backend engineer RAG FastAPI remote India"},
        {"track": "ai_ml", "exp": "intern", "loc": "Bengaluru", "sal": 30000, "skills": ["python", "pytorch", "docker", "linux"], "query": "MLOps model serving intern PyTorch Bengaluru"},
        # Backend (8 profiles)
        {"track": "backend", "exp": "fresher", "loc": "Bengaluru", "sal": 50000, "skills": ["python", "fastapi", "postgresql", "sql", "rest api", "git"], "query": "Python FastAPI PostgreSQL backend engineer fresher Bengaluru"},
        {"track": "backend", "exp": "fresher", "loc": "Pune", "sal": 45000, "skills": ["python", "django", "postgresql", "redis", "docker", "pytest"], "query": "Django Python PostgreSQL Redis backend developer Pune"},
        {"track": "backend", "exp": "fresher", "loc": "Hyderabad", "sal": 50000, "skills": ["node.js", "typescript", "express.js", "postgresql", "rest api", "oauth2"], "query": "Junior Node.js TypeScript Express PostgreSQL backend Hyderabad"},
        {"track": "backend", "exp": "fresher", "loc": "Bengaluru", "sal": 55000, "skills": ["java", "spring boot", "sql", "mysql", "microservices"], "query": "Java Spring Boot microservices backend fresher Bengaluru"},
        {"track": "backend", "exp": "fresher", "loc": "Gurugram", "sal": 55000, "skills": ["go", "postgresql", "grpc", "docker", "linux", "redis"], "query": "Graduate Golang PostgreSQL gRPC backend engineer Gurugram"},
        {"track": "backend", "exp": "intern", "loc": "Bengaluru", "sal": 22000, "skills": ["python", "fastapi", "sql", "git"], "query": "Backend engineering intern Python REST API Bengaluru"},
        {"track": "backend", "exp": "fresher", "loc": "Remote", "sal": 50000, "skills": ["python", "sqlalchemy", "alembic", "celery", "postgresql"], "query": "Remote Python SQLAlchemy Alembic Celery backend developer"},
        {"track": "backend", "exp": "fresher", "loc": "Mumbai", "sal": 50000, "skills": ["node.js", "typescript", "rest api", "postgresql"], "query": "Junior API microservices backend developer Mumbai"},
        # Fullstack (8 profiles)
        {"track": "fullstack", "exp": "fresher", "loc": "Bengaluru", "sal": 50000, "skills": ["typescript", "react", "next.js", "tailwind css", "node.js", "postgresql"], "query": "Full-stack Next.js TypeScript React Tailwind Node.js Bengaluru"},
        {"track": "fullstack", "exp": "fresher", "loc": "Pune", "sal": 45000, "skills": ["javascript", "react", "html", "css", "rest api", "git"], "query": "Frontend React JavaScript HTML CSS fresher Pune"},
        {"track": "fullstack", "exp": "fresher", "loc": "Hyderabad", "sal": 50000, "skills": ["typescript", "react", "fastapi", "python", "postgresql", "docker"], "query": "Junior full-stack Next.js Python FastAPI Postgres Hyderabad"},
        {"track": "fullstack", "exp": "fresher", "loc": "Gurugram", "sal": 48000, "skills": ["javascript", "node.js", "express.js", "mongodb", "react", "redux"], "query": "MERN full-stack React Node Express MongoDB Gurugram"},
        {"track": "fullstack", "exp": "intern", "loc": "Remote", "sal": 20000, "skills": ["react", "javascript", "node.js", "git"], "query": "Remote full-stack engineering intern React Node.js"},
        {"track": "fullstack", "exp": "fresher", "loc": "Bengaluru", "sal": 55000, "skills": ["typescript", "react native", "rest api", "git", "agile"], "query": "Junior mobile web engineer React Native TypeScript Bengaluru"},
        {"track": "fullstack", "exp": "fresher", "loc": "Chennai", "sal": 45000, "skills": ["python", "javascript", "sql", "data structures & algorithms", "oop", "git"], "query": "SDE-1 software development engineer DSA OOP fresher Chennai"},
        {"track": "fullstack", "exp": "fresher", "loc": "Remote", "sal": 50000, "skills": ["typescript", "react", "next.js", "postgresql"], "query": "Associate software engineer TypeScript React remote"},
        # Data (7 profiles)
        {"track": "data", "exp": "fresher", "loc": "Bengaluru", "sal": 40000, "skills": ["sql", "python", "pandas", "excel", "power bi", "statistics"], "query": "Junior data analyst SQL Python pandas Power BI Bengaluru"},
        {"track": "data", "exp": "fresher", "loc": "Gurugram", "sal": 45000, "skills": ["sql", "python", "tableau", "a/b testing", "product analytics"], "query": "Product data analyst SQL Tableau A/B testing Gurugram"},
        {"track": "data", "exp": "fresher", "loc": "Hyderabad", "sal": 45000, "skills": ["python", "sql", "apache spark", "etl", "postgresql", "apache airflow"], "query": "Junior data engineer Python Spark Airflow ETL Hyderabad"},
        {"track": "data", "exp": "fresher", "loc": "Remote", "sal": 45000, "skills": ["sql", "dbt", "snowflake", "data modeling", "git", "python"], "query": "Analytics engineer dbt Snowflake SQL data modeling remote"},
        {"track": "data", "exp": "intern", "loc": "Bengaluru", "sal": 20000, "skills": ["python", "pandas", "numpy", "scikit-learn", "sql"], "query": "Data science intern Python pandas scikit-learn Bengaluru"},
        {"track": "data", "exp": "fresher", "loc": "Pune", "sal": 40000, "skills": ["sql", "power bi", "excel", "statistics", "python"], "query": "Associate business intelligence analyst Power BI SQL Pune"},
        {"track": "data", "exp": "fresher", "loc": "Mumbai", "sal": 45000, "skills": ["python", "pandas", "xgboost", "scikit-learn", "sql"], "query": "Junior data analyst machine learning XGBoost Mumbai"},
        # Cybersecurity (6 profiles)
        {"track": "cybersecurity", "exp": "fresher", "loc": "Bengaluru", "sal": 40000, "skills": ["network security", "linux", "siem", "soc operations", "threat modeling"], "query": "Junior cybersecurity SOC analyst SIEM Linux Bengaluru"},
        {"track": "cybersecurity", "exp": "intern", "loc": "Pune", "sal": 18000, "skills": ["owasp", "burp suite", "penetration testing", "python", "rest api"], "query": "Application security AppSec intern OWASP Burp Suite Pune"},
        {"track": "cybersecurity", "exp": "fresher", "loc": "Hyderabad", "sal": 40000, "skills": ["vulnerability management", "nmap", "linux", "bash", "cryptography"], "query": "Associate VAPT penetration testing engineer Nmap Linux Hyderabad"},
        {"track": "cybersecurity", "exp": "fresher", "loc": "Remote", "sal": 45000, "skills": ["cloud security", "aws", "iam", "docker", "linux", "python"], "query": "Junior cloud security analyst AWS IAM DevSecOps remote"},
        {"track": "cybersecurity", "exp": "fresher", "loc": "Gurugram", "sal": 40000, "skills": ["siem", "soc operations", "network security", "linux"], "query": "Security operations engineer SIEM incident response Gurugram"},
        {"track": "cybersecurity", "exp": "fresher", "loc": "Chennai", "sal": 40000, "skills": ["owasp", "burp suite", "python", "vulnerability management"], "query": "Junior AppSec VAPT security engineer Chennai"},
        # QA / SDET (6 profiles)
        {"track": "qa", "exp": "fresher", "loc": "Bengaluru", "sal": 38000, "skills": ["python", "pytest", "playwright", "postman", "sql", "git"], "query": "Junior QA automation engineer Playwright Python pytest Bengaluru"},
        {"track": "qa", "exp": "fresher", "loc": "Pune", "sal": 38000, "skills": ["java", "selenium", "junit", "test automation", "rest api", "ci/cd"], "query": "Software test engineer Selenium Java JUnit Pune"},
        {"track": "qa", "exp": "fresher", "loc": "Hyderabad", "sal": 40000, "skills": ["typescript", "playwright", "cypress", "manual testing", "postman"], "query": "Associate SDET Playwright Cypress automation Hyderabad"},
        {"track": "qa", "exp": "intern", "loc": "Remote", "sal": 16000, "skills": ["manual testing", "postman", "sql", "pytest", "git"], "query": "QA engineering intern API web testing remote"},
        {"track": "qa", "exp": "fresher", "loc": "Gurugram", "sal": 38000, "skills": ["manual testing", "postman", "sql", "jmeter", "test automation"], "query": "Junior performance QA analyst JMeter Postman SQL Gurugram"},
        {"track": "qa", "exp": "fresher", "loc": "Noida", "sal": 35000, "skills": ["selenium", "java", "test automation", "postman"], "query": "QA automation SDET fresher Noida"},
        # Product & DevOps (7 profiles)
        {"track": "product", "exp": "fresher", "loc": "Bengaluru", "sal": 50000, "skills": ["product strategy", "prd writing", "user research", "sql", "product analytics", "figma"], "query": "Associate product manager APM PRD SQL Figma Bengaluru"},
        {"track": "product", "exp": "intern", "loc": "Gurugram", "sal": 20000, "skills": ["prd writing", "a/b testing", "product analytics", "sql", "excel"], "query": "Product management intern A/B testing analytics Gurugram"},
        {"track": "product", "exp": "fresher", "loc": "Remote", "sal": 48000, "skills": ["product strategy", "prd writing", "sql", "agile", "figma"], "query": "Junior technical product manager remote India"},
        {"track": "product", "exp": "fresher", "loc": "Mumbai", "sal": 45000, "skills": ["product analytics", "sql", "a/b testing", "prd writing"], "query": "Product analyst APM trainee Mumbai"},
        {"track": "devops", "exp": "fresher", "loc": "Bengaluru", "sal": 50000, "skills": ["docker", "kubernetes", "terraform", "aws", "prometheus", "python"], "query": "Associate DevOps cloud engineer Docker Kubernetes Terraform AWS Bengaluru"},
        {"track": "devops", "exp": "intern", "loc": "Remote", "sal": 20000, "skills": ["docker", "linux", "aws", "ci/cd", "git", "bash"], "query": "Cloud infrastructure intern AWS Docker CI/CD remote"},
        {"track": "devops", "exp": "fresher", "loc": "Pune", "sal": 45000, "skills": ["docker", "linux", "aws", "terraform", "ci/cd"], "query": "DevOps cloud engineer fresher AWS Docker Linux Pune"},
    ]
    assert len(archetypes) == 50

    profiles: list[dict[str, Any]] = []
    for idx, arch in enumerate(archetypes, start=1):
        prof = {
            "id": f"profile_{idx:02d}",
            "query": arch["query"],
            "target_track": arch["track"],
            "skills": [normalize_skill_name(s) for s in arch["skills"]],
            "interests": [arch["track"], *arch["skills"][:2]],
            "location_pref": arch["loc"],
            "remote_only": arch["loc"].lower() == "remote",
            "remote_ok": True,
            "salary_min": arch["sal"],
            "experience_level": arch["exp"],
        }
        user_skills = set(prof["skills"])
        relevance: dict[str, int] = {}

        for job in indexed_jobs:
            if not _passes_hard_filters(job, prof):
                continue
            if job.raw.get("track") != arch["track"]:
                continue
            overlap = len(user_skills & job.skill_set) / max(1, len(job.skill_set))
            exp_match = job.raw.get("experience_level") == arch["exp"]
            if exp_match and overlap >= 0.35:
                relevance[str(job.job_id)] = 2
            elif overlap >= 0.15 or (exp_match and len(user_skills & job.skill_set) >= 1):
                relevance[str(job.job_id)] = 1

        prof["relevant_jobs"] = relevance
        profiles.append(prof)

    return profiles


def compute_recall_at_k(ranked_ids: list[str], relevance: dict[str, int], k: int = 10) -> float:
    relevant_set = {jid for jid, grade in relevance.items() if grade > 0}
    if not relevant_set:
        return 1.0
    hits = sum(1 for jid in ranked_ids[:k] if jid in relevant_set)
    # Standard capped recall@k: hits / min(k, |relevant|) so perfect top-10 scores 1.0
    denom = min(k, len(relevant_set))
    return hits / denom


def compute_ndcg_at_k(ranked_ids: list[str], relevance: dict[str, int], k: int = 10) -> float:
    def dcg(grades: list[int]) -> float:
        return sum((2**g - 1) / math.log2(i + 2) for i, g in enumerate(grades))

    actual_grades = [relevance.get(jid, 0) for jid in ranked_ids[:k]]
    ideal_grades = sorted((g for g in relevance.values() if g > 0), reverse=True)[:k]
    idcg = dcg(ideal_grades)
    if idcg == 0:
        return 1.0
    return dcg(actual_grades) / idcg


def _bm25_scores(
    query: str,
    candidates: list[IndexedSeedJob],
    idf: dict[str, float],
    avg_len: float,
) -> dict[uuid.UUID, float]:
    q_terms = _tokenize(query)
    if not q_terms or not candidates:
        return {}
    k1, b = 1.5, 0.75
    scores: dict[uuid.UUID, float] = {}
    for job in candidates:
        score = 0.0
        for term in q_terms:
            tf = 3.0 * job.title_tokens.get(term, 0) + 1.0 * job.body_tokens.get(term, 0)
            if tf <= 0:
                continue
            term_idf = idf.get(term, 0.5)
            score += term_idf * ((tf * (k1 + 1)) / (tf + k1 * (1 - b + b * (job.doc_len / avg_len))))
        if score > 0:
            scores[job.job_id] = score
    return scores


def _to_search_candidate(
    job: IndexedSeedJob,
    vec_sim: float,
    kw_score: float,
    rrf_score: float,
) -> SearchCandidate:
    return SearchCandidate(
        job_id=job.job_id,
        title=job.raw["title"],
        company=job.raw["company"],
        location=job.raw["location"],
        remote=bool(job.raw.get("remote", False)),
        salary_min=job.raw.get("salary_min"),
        salary_max=job.raw.get("salary_max"),
        description=job.raw["description"],
        source=job.raw.get("source", "seed"),
        source_url=job.raw["source_url"],
        posted_at=datetime.fromisoformat(job.raw["posted_at"].replace("Z", "+00:00")),
        skills=job.skills,
        vector_similarity=vec_sim,
        keyword_score=kw_score,
        rrf_score=rrf_score,
    )


def run_retrieval_eval(save_profiles: bool = True) -> dict[str, Any]:
    """Run all 4 retrieval methods across 50 labelled fresher profiles and return metrics."""
    indexed = load_indexed_seed_jobs()
    profiles = build_50_labelled_profiles(indexed)
    if save_profiles:
        PROFILES_OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        PROFILES_OUT_PATH.write_text(json.dumps(profiles, indent=2), encoding="utf-8")

    # Precompute corpus IDF for BM25 keyword search
    n_docs = len(indexed)
    avg_len = sum(j.doc_len for j in indexed) / max(1, n_docs)
    df: Counter[str] = Counter()
    for job in indexed:
        for term in set(job.title_tokens.keys()) | set(job.body_tokens.keys()):
            df[term] += 1
    idf = {term: math.log(1 + (n_docs - freq + 0.5) / (freq + 0.5)) for term, freq in df.items()}

    ref_now = datetime(2026, 11, 20, 12, 0, tzinfo=UTC)
    by_id = {j.job_id: j for j in indexed}

    metrics: dict[str, dict[str, list[float]]] = {
        "vector_only": {"recall10": [], "ndcg10": []},
        "keyword_only": {"recall10": [], "ndcg10": []},
        "hybrid": {"recall10": [], "ndcg10": []},
        "hybrid_rerank": {"recall10": [], "ndcg10": []},
    }

    for prof in profiles:
        rel: dict[str, int] = prof["relevant_jobs"]
        filtered = [j for j in indexed if _passes_hard_filters(j, prof)]
        if not filtered:
            continue

        q_vec = np.asarray(embed_text(prof["query"]), dtype=np.float32)
        q_norm = float(np.linalg.norm(q_vec))
        if q_norm > 0:
            q_vec = q_vec / q_norm

        vec_scored = [(j.job_id, float(np.dot(j.vector, q_vec))) for j in filtered]
        vec_scored.sort(key=lambda x: x[1], reverse=True)
        vec_top50 = vec_scored[:50]
        vec_sim_map = dict(vec_scored)

        kw_map = _bm25_scores(prof["query"], filtered, idf, avg_len)
        kw_top50 = sorted(kw_map.items(), key=lambda x: x[1], reverse=True)[:50]

        vec_ids = [jid for jid, _ in vec_top50]
        kw_ids = [jid for jid, _ in kw_top50]
        rrf_scores = reciprocal_rank_fusion([vec_ids, kw_ids], k=60)
        hybrid_ids = sorted(
            rrf_scores.keys(),
            key=lambda jid: (rrf_scores[jid], vec_sim_map.get(jid, 0.0)),
            reverse=True,
        )[:50]

        # Hybrid + Rerank via production rank_jobs()
        hybrid_cands = [
            _to_search_candidate(
                by_id[jid],
                vec_sim=vec_sim_map.get(jid, 0.0),
                kw_score=kw_map.get(jid, 0.0),
                rrf_score=rrf_scores.get(jid, 0.0),
            )
            for jid in hybrid_ids
        ]
        reranked = rank_jobs(prof, hybrid_cands, now=ref_now, top_n=50)
        rerank_ids = [r.job_id for r in reranked]

        for name, ordered in [
            ("vector_only", vec_ids),
            ("keyword_only", kw_ids),
            ("hybrid", hybrid_ids),
            ("hybrid_rerank", rerank_ids),
        ]:
            str_ids = [str(jid) for jid in ordered]
            metrics[name]["recall10"].append(compute_recall_at_k(str_ids, rel, k=10))
            metrics[name]["ndcg10"].append(compute_ndcg_at_k(str_ids, rel, k=10))

    summary: dict[str, dict[str, float]] = {}
    for name, vals in metrics.items():
        summary[name] = {
            "recall_at_10": round(sum(vals["recall10"]) / max(1, len(vals["recall10"])), 4),
            "ndcg_at_10": round(sum(vals["ndcg10"]) / max(1, len(vals["ndcg10"])), 4),
        }

    return {
        "num_profiles": len(profiles),
        "num_jobs": len(indexed),
        "methods": summary,
    }
