import type { ChatMessage, MemoryItem, ProfileSnapshot, RankedJob, RoadmapPlan } from "./types";

export const DEMO_PROFILE: ProfileSnapshot = {
  user_id: "11111111-1111-4111-8111-111111111111",
  skills: ["python", "sql", "fastapi", "git", "pandas"],
  interests: ["ai_ml", "backend"],
  location_pref: "Bengaluru",
  remote_ok: true,
  salary_min: 50000,
  experience_level: "fresher",
  goals: "AI/LLM or Python backend fresher role; no sales",
};

export const DEMO_MEMORIES: MemoryItem[] = [
  {
    id: "m-1",
    type: "fact",
    text: "Final-year CS fresher with hands-on Python, SQL, and FastAPI projects.",
    last_seen: "2026-11-20T05:00:00Z",
    created_at: "2026-11-19T09:00:00Z",
  },
  {
    id: "m-2",
    type: "preference",
    text: "Prefers Bengaluru or Remote roles paying ₹50K+/month; dislikes sales roles.",
    last_seen: "2026-11-20T05:00:00Z",
    created_at: "2026-11-19T09:00:00Z",
  },
  {
    id: "m-3",
    type: "goal",
    text: "Targeting an applied AI/LLM or Python backend internship/fresher offer in 4 weeks.",
    last_seen: "2026-11-20T05:00:00Z",
    created_at: "2026-11-19T09:00:00Z",
  },
];

export const DEMO_JOBS: RankedJob[] = [
  {
    job_id: "22222222-2222-4222-8222-222222222201",
    title: "Applied AI Engineer (Fresher)",
    company: "Nakshatra AI",
    location: "Bengaluru, Karnataka",
    remote: true,
    salary_min: 65000,
    salary_max: 85000,
    source: "seed",
    source_url: "https://sample-jobs.compass.local/nakshatra-ai/ai_ml-0001",
    posted_at: "2026-11-18T12:00:00Z",
    fit_score_pct: 86,
    fit_label: "True North",
    scores: {
      semantic: 0.91,
      skill_overlap: 0.78,
      preference_fit: 0.95,
      freshness: 0.94,
      interaction_adjustment: 0.0,
      final_score: 0.86,
    },
    matched_skills: ["python", "fastapi", "sql"],
    missing_skills: ["pgvector", "docker"],
    why_it_fits:
      "Matches your python, fastapi, sql skills; remote-friendly in Bengaluru; pays ₹65K–85K/mo.",
  },
  {
    job_id: "22222222-2222-4222-8222-222222222202",
    title: "Backend Engineer (Python / FastAPI) - Fresher",
    company: "KaveriPay",
    location: "Bengaluru, Karnataka",
    remote: false,
    salary_min: 55000,
    salary_max: 75000,
    source: "seed",
    source_url: "https://sample-jobs.compass.local/kaveripay/backend-0062",
    posted_at: "2026-11-16T09:00:00Z",
    fit_score_pct: 79,
    fit_label: "True North",
    scores: {
      semantic: 0.84,
      skill_overlap: 0.75,
      preference_fit: 0.88,
      freshness: 0.87,
      interaction_adjustment: 0.0,
      final_score: 0.79,
    },
    matched_skills: ["python", "fastapi", "sql", "git"],
    missing_skills: ["postgresql", "redis"],
    why_it_fits:
      "Strong Python + FastAPI alignment in Bengaluru hybrid; pays ₹55K–75K/mo.",
  },
  {
    job_id: "22222222-2222-4222-8222-222222222203",
    title: "MLOps & Model Serving Intern",
    company: "VayuCloud",
    location: "Remote (India)",
    remote: true,
    salary_min: 35000,
    salary_max: 45000,
    source: "seed",
    source_url: "https://sample-jobs.compass.local/vayucloud/ai_ml-0018",
    posted_at: "2026-11-10T10:00:00Z",
    fit_score_pct: 61,
    fit_label: "Heading right",
    scores: {
      semantic: 0.76,
      skill_overlap: 0.45,
      preference_fit: 0.62,
      freshness: 0.72,
      interaction_adjustment: 0.0,
      final_score: 0.61,
    },
    matched_skills: ["python", "git"],
    missing_skills: ["docker", "kubernetes", "aws"],
    why_it_fits:
      "Great remote stepping stone for production ML serving; stretch on Docker/Kubernetes.",
  },
];

export const DEMO_ROADMAP: RoadmapPlan = {
  target_role: "Applied AI / LLM Engineer (Fresher)",
  fit_score: 82,
  ranked_gaps: ["pgvector", "docker", "llm evaluation"],
  weeks: [
    {
      week: 1,
      goal: "Master pgvector cosine indexing and Postgres hybrid retrieval",
      resource: "pgvector Docs + PostgreSQL Exercises (pgexercises.com)",
      project: "Build a 500-doc hybrid vector + FTS search API with RRF (k=60)",
      outcome: "Measured Recall@10 benchmark table comparing vector vs hybrid",
    },
    {
      week: 2,
      goal: "Write a clean tool-use agent loop with Pydantic v2 validation",
      resource: "Anthropic Tool Use & Structured Outputs Guide",
      project: "Implement 4 typed tools with retry-once validation and grounding checks",
      outcome: "15+ automated multi-turn pytest scenarios passing cleanly",
    },
    {
      week: 3,
      goal: "Add LLM evaluation harnesses and short/long-term memory",
      resource: "Eugene Yan & Hamel Husain Production LLM Evals",
      project: "Run a 30-case rubric checking groundedness and citation accuracy",
      outcome: "Reproducible evals/results.md committed to GitHub",
    },
    {
      week: 4,
      goal: "Containerize with non-root Docker and deploy live",
      resource: "FastAPI Docker & Render + Neon Deployment Docs",
      project: "Ship public URL with /health smoke test and architecture diagram",
      outcome: "Live demo link ready for Bengaluru AI/backend applications",
    },
  ],
  apply_when:
    "Start applying at the end of Week 2 once your hybrid search + tool-use repo has passing tests, then attach your live URL in Week 4.",
  alternatives: [
    {
      role: "Backend Engineer (Python / FastAPI)",
      tradeoff: "Much higher fresher hiring volume in Bengaluru; focuses on APIs and SQL rather than LLMs.",
    },
    {
      role: "Junior Data Analyst",
      tradeoff: "Faster entry ramp with your SQL + pandas skills, though lower ceiling on software engineering.",
    },
  ],
  sources: [
    { source_url: "kb://ai-ml-engineer.md", title: "AI / ML & LLM Engineer Career Guide" },
    { source_url: "kb://backend-engineer.md", title: "Backend Software Engineer Career Guide" },
  ],
};

export const DEMO_MESSAGES: ChatMessage[] = [
  {
    id: "demo-1",
    role: "user",
    content:
      "I'm a fresher, love Python and SQL, hate sales, and want ₹50K+/month in Bengaluru or remote. Show me my best matches and a 4-week plan!",
  },
  {
    id: "demo-2",
    role: "assistant",
    content:
      "You've already got a strong foundation with **Python, SQL, and FastAPI**. I filtered out sales and pulled your top grounded matches in Bengaluru and Remote—**Nakshatra AI** and **KaveriPay** are both **True North** fits, and closing **pgvector + Docker** will unlock almost every applied AI role on your list.",
    recommended_jobs: DEMO_JOBS,
    roadmap: DEMO_ROADMAP,
    suggested_replies: [
      "Compare Nakshatra AI vs KaveriPay",
      "Tailor my resume for Nakshatra AI",
      "Give me AI interview prep tips",
    ],
  },
];
