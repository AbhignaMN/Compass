"""Deterministic generator for 320 realistic India fresher/intern sample job postings.

Marks every generated posting with source='seed' and clearly synthetic company domains so
sample data is transparent in the database and README.
"""

import json
import random
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

SEED_OUTPUT_PATH = Path("data/jobs_seed.json")

# Synthetic Indian tech startups, product companies, and engineering studios (sample data)
COMPANIES: list[tuple[str, str, str]] = [
    ("KaveriPay", "fintech", "UPI and merchant payments platform"),
    ("Nakshatra AI", "ai_saas", "applied LLM and enterprise search startup"),
    ("VayuCloud", "cloud", "cloud observability and developer infrastructure startup"),
    ("BanyanCart", "ecommerce", "quick-commerce and supply-chain platform"),
    ("PranaHealth", "healthtech", "digital diagnostics and clinic SaaS platform"),
    ("Chanakya Analytics", "data", "retail demand-forecasting and BI platform"),
    ("Sahyadri Security", "cybersecurity", "cloud security and managed AppSec startup"),
    ("IndusDev Labs", "devtools", "API testing and CI automation studio"),
    ("ZestGrid Mobility", "mobility", "EV fleet telemetry and routing platform"),
    ("Deccan FinServe", "fintech", "credit underwriting and lending API company"),
    ("Aranya EdTech", "edtech", "interactive coding and skill-assessment platform"),
    ("Trident Logistics", "logistics", "warehouse automation and freight tracking platform"),
    ("Surya Robotics", "ai_saas", "vision and edge-AI automation company"),
    ("Meghna SaaS", "saas", "B2B workflow automation and CRM platform"),
    ("Kora Commerce", "ecommerce", "D2C storefront and checkout infrastructure"),
    ("TuringBridge India", "ai_saas", "conversational AI agents and voice-bot studio"),
    ("Neelgiri Cyber", "cybersecurity", "SOC automation and vulnerability management firm"),
    ("PulseMetric", "data", "product analytics and experimentation SaaS"),
    ("Vidyut Grid", "climate", "smart energy analytics and IoT backend startup"),
    ("Aarambh Digital", "saas", "SMB accounting and GST compliance platform"),
    ("LumenStack", "devtools", "Next.js and Postgres developer tooling company"),
    ("HarborShield Sec", "cybersecurity", "API security and zero-trust identity platform"),
    ("GatiFlow", "logistics", "real-time last-mile delivery orchestration startup"),
    ("Sankhya Labs", "data", "modern data warehouse and dbt consultancy"),
]

LOCATIONS: list[tuple[str, bool, float]] = [
    ("Bengaluru, Karnataka", False, 1.12),
    ("Bengaluru, Karnataka", True, 1.10),
    ("Hyderabad, Telangana", False, 1.02),
    ("Pune, Maharashtra", False, 0.98),
    ("Gurugram, Haryana", False, 1.05),
    ("Remote (India)", True, 1.00),
    ("Mumbai, Maharashtra", False, 1.04),
    ("Chennai, Tamil Nadu", False, 0.96),
    ("Noida, Uttar Pradesh", False, 0.95),
]

# Track definitions: role titles, core skills, must-have pools, bonus pools, base monthly INR salary
TRACKS: list[dict[str, Any]] = [
    {
        "track": "ai_ml",
        "count": 56,
        "titles": [
            "AI / LLM Engineer Intern",
            "Junior Machine Learning Engineer",
            "Applied AI Engineer (Fresher)",
            "LLM & AI Agents Intern",
            "Associate NLP Engineer",
            "GenAI Backend Engineer (Entry Level)",
            "Junior Computer Vision Engineer",
            "MLOps & Model Serving Intern",
        ],
        "must_pool": [
            ["Python", "PyTorch", "SQL", "Git"],
            ["Python", "LLMs", "RAG", "FastAPI", "PostgreSQL", "pgvector"],
            ["Python", "Machine Learning", "scikit-learn", "pandas", "NumPy"],
            ["Python", "AI Agents", "Pydantic", "REST API", "Embeddings"],
            ["Python", "Hugging Face", "NLP", "Deep Learning", "Docker"],
            ["Python", "Computer Vision", "PyTorch", "ONNX", "Linux"],
        ],
        "nice_pool": [
            ["Docker", "LLM Evaluation", "Redis", "AWS"],
            ["Fine-tuning", "vLLM", "MLOps", "Kubernetes"],
            ["Vector Databases", "Prompt Engineering", "FastAPI", "GitHub Actions"],
            ["XGBoost", "Weights & Biases", "GCP", "pytest"],
        ],
        "responsibilities": [
            "Build hybrid semantic + keyword retrieval pipelines over PostgreSQL/pgvector and benchmark Recall@10.",
            "Implement structured tool-use agent loops with Pydantic schema validation and automated failure recovery.",
            "Train, evaluate, and serve lightweight NLP/tabular models behind async FastAPI microservices.",
            "Design reproducible LLM evaluation harnesses tracking groundedness, latency, and citation accuracy.",
        ],
        "intern_salary": (25000, 50000),
        "fresher_salary": (60000, 135000),
    },
    {
        "track": "backend",
        "count": 54,
        "titles": [
            "Backend Engineer (Python / FastAPI) - Fresher",
            "Junior Backend Developer (Node.js)",
            "Associate Software Engineer - Backend (Java / Spring Boot)",
            "Backend Engineering Intern (Python)",
            "Junior API & Microservices Engineer",
            "Graduate Backend Engineer (Go / Postgres)",
            "Associate Backend Developer (Django)",
        ],
        "must_pool": [
            ["Python", "FastAPI", "PostgreSQL", "SQL", "REST API", "Git"],
            ["Python", "Django", "PostgreSQL", "Redis", "Docker", "pytest"],
            ["Node.js", "TypeScript", "Express.js", "PostgreSQL", "REST API", "OAuth2"],
            ["Java", "Spring Boot", "SQL", "MySQL", "Microservices", "Data Structures & Algorithms"],
            ["Go", "PostgreSQL", "gRPC", "Docker", "Linux", "Redis"],
            ["Python", "SQLAlchemy", "Alembic", "Celery", "RabbitMQ", "PostgreSQL"],
        ],
        "nice_pool": [
            ["Docker", "AWS", "CI/CD", "Redis"],
            ["Kubernetes", "System Design", "Prometheus", "Nginx"],
            ["GraphQL", "WebSockets", "MongoDB", "Terraform"],
        ],
        "responsibilities": [
            "Design clean relational schemas, write migrations, and optimize slow SQL queries with composite indexes.",
            "Build low-latency REST APIs with input validation, rate limiting, structured logging, and unit tests.",
            "Integrate Redis caching, async background workers, and secure OAuth2/JWT authentication flows.",
            "Collaborate with product and frontend engineers to ship reliable production services with CI/CD.",
        ],
        "intern_salary": (22000, 45000),
        "fresher_salary": (50000, 120000),
    },
    {
        "track": "fullstack",
        "count": 52,
        "titles": [
            "Full-Stack Software Engineer (Fresher)",
            "Junior Full-Stack Developer (Next.js + Python)",
            "Software Development Engineer I (SDE-1)",
            "Frontend & React Developer (Entry Level)",
            "Full-Stack Engineering Intern (React / Node.js)",
            "Associate Software Engineer (TypeScript)",
            "Junior Mobile & Web Engineer (React Native)",
        ],
        "must_pool": [
            ["TypeScript", "React", "Next.js", "Tailwind CSS", "Node.js", "PostgreSQL"],
            ["JavaScript", "React", "HTML", "CSS", "REST API", "Git"],
            ["TypeScript", "React", "FastAPI", "Python", "PostgreSQL", "Docker"],
            ["JavaScript", "Node.js", "Express.js", "MongoDB", "React", "Redux"],
            ["TypeScript", "React Native", "REST API", "Git", "Agile"],
            ["Python", "JavaScript", "SQL", "Data Structures & Algorithms", "OOP", "Git"],
        ],
        "nice_pool": [
            ["Playwright", "Accessibility", "Docker", "CI/CD"],
            ["GraphQL", "AWS", "Redis", "Vite"],
            ["Next.js", "Figma", "Tailwind CSS", "pytest"],
        ],
        "responsibilities": [
            "Ship responsive, accessible React and Next.js interfaces backed by clean REST/GraphQL APIs.",
            "Own features end-to-end from Figma specs and Postgres models through automated tests and deployment.",
            "Debug cross-browser issues, optimize page load times, and write clean, reviewable TypeScript code.",
            "Collaborate in agile sprints, participate in code reviews, and maintain high UI/API quality.",
        ],
        "intern_salary": (20000, 42000),
        "fresher_salary": (45000, 115000),
    },
    {
        "track": "data",
        "count": 48,
        "titles": [
            "Junior Data Analyst (SQL & Python)",
            "Data Science Intern",
            "Associate Business Intelligence Analyst",
            "Junior Data Engineer (Python / Spark)",
            "Product Data Analyst (Fresher)",
            "Analytics Engineer (Entry Level)",
        ],
        "must_pool": [
            ["SQL", "Python", "pandas", "Excel", "Power BI", "Statistics"],
            ["SQL", "Python", "Tableau", "A/B Testing", "Product Analytics"],
            ["Python", "SQL", "Apache Spark", "ETL", "PostgreSQL", "Apache Airflow"],
            ["SQL", "dbt", "Snowflake", "Data Modeling", "Git", "Python"],
            ["Python", "pandas", "NumPy", "scikit-learn", "XGBoost", "SQL"],
        ],
        "nice_pool": [
            ["BigQuery", "Databricks", "Apache Kafka", "Docker"],
            ["Matplotlib", "Statistics", "AWS", "Looker"],
            ["dbt", "Airflow", "Power BI", "FastAPI"],
        ],
        "responsibilities": [
            "Write complex SQL cohort, retention, and funnel queries to guide weekly product and growth decisions.",
            "Build automated Python/pandas pipelines and clean Power BI or Tableau dashboards for leadership.",
            "Design and analyze A/B experiments, validate data quality, and document clear business insights.",
            "Maintain reliable ETL/dbt transformations and partner with engineering on event instrumentation.",
        ],
        "intern_salary": (18000, 38000),
        "fresher_salary": (40000, 95000),
    },
    {
        "track": "cybersecurity",
        "count": 38,
        "titles": [
            "Junior Cybersecurity Analyst (SOC)",
            "Application Security (AppSec) Intern",
            "Associate VAPT / Penetration Testing Engineer",
            "Junior Cloud Security Analyst",
            "Security Operations Engineer (Fresher)",
        ],
        "must_pool": [
            ["Network Security", "Linux", "SIEM", "SOC Operations", "Threat Modeling"],
            ["OWASP", "Burp Suite", "Penetration Testing", "Python", "REST API"],
            ["Vulnerability Management", "Nmap", "Linux", "Bash", "Cryptography"],
            ["Cloud Security", "AWS", "IAM", "Docker", "Linux", "Python"],
        ],
        "nice_pool": [
            ["Python", "Terraform", "Kubernetes", "CI/CD"],
            ["SIEM", "Wireshark", "OWASP", "Azure"],
        ],
        "responsibilities": [
            "Monitor SIEM alerts, investigate anomalous login or network activity, and escalate validated incidents.",
            "Conduct web and API vulnerability assessments against OWASP Top 10 and write actionable developer fixes.",
            "Automate security header checks, dependency scans, and IAM posture audits using Python and Bash.",
            "Partner with engineering squads to review authentication, TLS, and cloud least-privilege policies.",
        ],
        "intern_salary": (18000, 36000),
        "fresher_salary": (40000, 92000),
    },
    {
        "track": "qa",
        "count": 36,
        "titles": [
            "Junior QA Automation Engineer (Playwright / Python)",
            "Associate SDET (Entry Level)",
            "QA Engineering Intern (API & Web Testing)",
            "Software Test Engineer (Selenium / Java)",
            "Junior Performance & QA Analyst",
        ],
        "must_pool": [
            ["Python", "pytest", "Playwright", "Postman", "SQL", "Git"],
            ["Java", "Selenium", "JUnit", "Test Automation", "REST API", "CI/CD"],
            ["TypeScript", "Playwright", "Cypress", "Manual Testing", "Agile", "Postman"],
            ["Manual Testing", "Postman", "SQL", "JMeter", "Test Automation", "Git"],
        ],
        "nice_pool": [
            ["Docker", "CI/CD", "JMeter", "Appium"],
            ["Linux", "Python", "Playwright", "AWS"],
        ],
        "responsibilities": [
            "Build and maintain reliable Playwright/Selenium end-to-end test suites using Page Object Model.",
            "Automate REST API schema, negative-case, and regression checks wired into GitHub Actions CI.",
            "Verify database state with SQL, write reproducible bug reports, and eliminate flaky test cases.",
            "Run baseline load tests with JMeter/k6 before major releases and track defect escape metrics.",
        ],
        "intern_salary": (16000, 34000),
        "fresher_salary": (38000, 88000),
    },
    {
        "track": "product",
        "count": 36,
        "titles": [
            "Associate Product Manager (APM) - Fresher",
            "Product Management Intern",
            "Junior Technical Product Manager",
            "Product Analyst & APM Trainee",
            "Associate DevOps & Cloud Engineer (Fresher)",
            "Cloud Infrastructure Intern (AWS / Docker)",
        ],
        "must_pool": [
            ["Product Strategy", "PRD Writing", "User Research", "SQL", "Product Analytics", "Figma"],
            ["PRD Writing", "A/B Testing", "Product Analytics", "Agile", "Excel", "SQL"],
            ["Docker", "Linux", "AWS", "CI/CD", "Git", "Bash"],
            ["Docker", "Kubernetes", "Terraform", "AWS", "Prometheus", "Python"],
        ],
        "nice_pool": [
            ["Python", "LLMs", "Power BI", "Data Modeling"],
            ["Helm", "Nginx", "GCP", "Ansible"],
        ],
        "responsibilities": [
            "Run user interviews, author crisp PRDs with measurable success metrics, and coordinate agile sprints.",
            "Analyze funnel drop-offs in SQL and Mixpanel/GA4 to prioritize high-impact roadmap experiments.",
            "Automate multi-stage Docker builds, CI/CD pipelines, and cloud infrastructure using Terraform and AWS.",
            "Monitor service health, latency dashboards, and release rollouts alongside backend engineering teams.",
        ],
        "intern_salary": (20000, 45000),
        "fresher_salary": (48000, 118000),
    },
]


def _is_intern_title(title: str) -> bool:
    return "intern" in title.lower()


def _is_devops_title(title: str) -> bool:
    lower = title.lower()
    return "devops" in lower or "cloud" in lower


def generate_seed_jobs(seed: int = 42) -> list[dict[str, Any]]:
    """Generate 320 deterministic, realistic fresher/intern job postings in India."""
    rng = random.Random(seed)
    base_time = datetime(2026, 11, 19, 12, 0, tzinfo=UTC)
    jobs: list[dict[str, Any]] = []
    counter = 1

    for track_cfg in TRACKS:
        track = track_cfg["track"]
        for _ in range(track_cfg["count"]):
            title = rng.choice(track_cfg["titles"])
            company, industry, company_blurb = rng.choice(COMPANIES)
            location, remote, loc_mult = rng.choice(LOCATIONS)

            if track == "product" and _is_devops_title(title):
                must_skills = rng.choice(track_cfg["must_pool"][2:])
                nice_skills = track_cfg["nice_pool"][1]
                resp_choices = track_cfg["responsibilities"][2:]
                effective_track = "devops"
            elif track == "product":
                must_skills = rng.choice(track_cfg["must_pool"][:2])
                nice_skills = track_cfg["nice_pool"][0]
                resp_choices = track_cfg["responsibilities"][:2]
                effective_track = "product"
            else:
                must_skills = rng.choice(track_cfg["must_pool"])
                nice_skills = rng.choice(track_cfg["nice_pool"])
                resp_choices = track_cfg["responsibilities"]
                effective_track = track

            is_intern = _is_intern_title(title)
            lo_base, hi_base = (
                track_cfg["intern_salary"] if is_intern else track_cfg["fresher_salary"]
            )
            band_start = int(round(rng.randint(lo_base, int((lo_base + hi_base) * 0.55)) * loc_mult, -3))
            band_width = rng.choice([10000, 15000, 20000, 25000]) if not is_intern else rng.choice([5000, 8000, 12000])
            salary_min = max(15000, band_start)
            salary_max = salary_min + band_width

            days_ago = rng.randint(0, 45)
            hours_ago = rng.randint(0, 23)
            posted_at = (base_time - timedelta(days=days_ago, hours=hours_ago)).isoformat()

            chosen_resps = rng.sample(resp_choices, k=min(2, len(resp_choices)))
            eligibility = (
                "Final-year B.Tech/BE/MCA/M.Sc students or recent graduates available for 3-6 months (PPO conversion based on performance)."
                if is_intern
                else "0-2 years experience; strong 2025/2026 freshers with deployed GitHub projects are encouraged to apply."
            )
            work_policy = (
                "Fully remote across India with async-friendly engineering rituals."
                if remote
                else f"Hybrid (3 days/week in our {location.split(',')[0]} office)."
            )

            description = (
                f"About {company}: We are a growing {industry} team building a {company_blurb}. "
                f"We are hiring a {title} to join our engineering/product group.\n\n"
                f"What You'll Build:\n"
                f"- {chosen_resps[0]}\n"
                f"- {chosen_resps[-1]}\n\n"
                f"Must-Have Skills:\n"
                f"- Hands-on experience with {', '.join(must_skills)}.\n"
                f"- {eligibility}\n"
                f"- Work mode: {work_policy}\n\n"
                f"Good to Have:\n"
                f"- Familiarity with {', '.join(nice_skills)}.\n"
                f"- Clear communication, curiosity, and ownership of end-to-end deliverables."
            )

            slug_company = company.lower().replace(" ", "-")
            jobs.append(
                {
                    "title": title,
                    "company": company,
                    "location": location,
                    "remote": remote,
                    "salary_min": salary_min,
                    "salary_max": salary_max,
                    "description": description,
                    "source": "seed",
                    "source_url": f"https://sample-jobs.compass.local/{slug_company}/{effective_track}-{counter:04d}",
                    "posted_at": posted_at,
                    "status": "active",
                    "track": effective_track,
                    "experience_level": "intern" if is_intern else "fresher",
                }
            )
            counter += 1

    return jobs


def main() -> None:
    jobs = generate_seed_jobs(seed=42)
    SEED_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    SEED_OUTPUT_PATH.write_text(json.dumps(jobs, indent=2), encoding="utf-8")
    print(f"Generated {len(jobs)} sample jobs -> {SEED_OUTPUT_PATH}")


if __name__ == "__main__":
    main()
