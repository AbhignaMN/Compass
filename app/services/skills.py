"""Deterministic ~150-skill taxonomy with regex extraction and synonym normalization."""

import re
from dataclasses import dataclass

# Curated taxonomy of 150 canonical skills with category and synonym patterns.
# Tuple format: (canonical_name, category, tuple_of_synonyms)
SKILL_TAXONOMY: list[tuple[str, str, tuple[str, ...]]] = [
    # Languages (18)
    ("python", "language", ("python", "python3", "py")),
    ("java", "language", ("java", "core java", "java 17", "java 21")),
    ("javascript", "language", ("javascript", "ecmascript", "es6", "js")),
    ("typescript", "language", ("typescript", "ts")),
    ("c++", "language", ("c++", "cpp")),
    ("c", "language", ("c programming", "ansi c", "embedded c")),
    ("c#", "language", ("c#", "csharp", "c-sharp")),
    ("go", "language", ("golang", "go lang", "go programming")),
    ("rust", "language", ("rust", "rustlang")),
    ("kotlin", "language", ("kotlin",)),
    ("swift", "language", ("swift",)),
    ("ruby", "language", ("ruby",)),
    ("php", "language", ("php",)),
    ("scala", "language", ("scala",)),
    ("r", "language", ("r programming", "r language", "rstudio")),
    ("sql", "language", ("sql", "structured query language", "t-sql", "pl/sql")),
    ("bash", "language", ("bash", "shell scripting", "shell script", "sh")),
    ("dart", "language", ("dart",)),
    # Backend & APIs (18)
    ("fastapi", "backend", ("fastapi", "fast api")),
    ("django", "backend", ("django", "django rest framework", "drf")),
    ("flask", "backend", ("flask",)),
    ("spring boot", "backend", ("spring boot", "springboot", "spring framework", "spring")),
    ("node.js", "backend", ("node.js", "nodejs", "node js")),
    ("express.js", "backend", ("express.js", "expressjs", "express")),
    ("nestjs", "backend", ("nestjs", "nest.js")),
    ("graphql", "backend", ("graphql", "graph ql")),
    ("rest api", "backend", ("rest api", "restful", "rest apis", "restful apis", "http apis")),
    ("grpc", "backend", ("grpc", "protobuf", "protocol buffers")),
    ("microservices", "backend", ("microservices", "microservice")),
    ("celery", "backend", ("celery",)),
    ("sqlalchemy", "backend", ("sqlalchemy", "sql alchemy")),
    ("alembic", "backend", ("alembic",)),
    ("pydantic", "backend", ("pydantic",)),
    ("websockets", "backend", ("websockets", "websocket")),
    ("oauth2", "backend", ("oauth", "oauth2", "oauth 2.0", "jwt", "oidc")),
    ("asp.net", "backend", ("asp.net", ".net", "dotnet", ".net core")),
    # Frontend & Mobile (14)
    ("react", "frontend", ("react", "reactjs", "react.js")),
    ("next.js", "frontend", ("next.js", "nextjs", "next js")),
    ("angular", "frontend", ("angular", "angularjs")),
    ("vue.js", "frontend", ("vue", "vue.js", "vuejs")),
    ("html", "frontend", ("html", "html5")),
    ("css", "frontend", ("css", "css3")),
    ("tailwind css", "frontend", ("tailwind", "tailwind css", "tailwindcss")),
    ("redux", "frontend", ("redux", "redux toolkit")),
    ("webpack", "frontend", ("webpack",)),
    ("vite", "frontend", ("vite",)),
    ("react native", "frontend", ("react native",)),
    ("flutter", "frontend", ("flutter",)),
    ("android", "frontend", ("android", "android sdk", "jetpack compose")),
    ("accessibility", "frontend", ("accessibility", "wcag", "a11y")),
    # AI / ML / LLMs (24)
    ("machine learning", "ai_ml", ("machine learning", "ml")),
    ("deep learning", "ai_ml", ("deep learning", "neural networks")),
    ("pytorch", "ai_ml", ("pytorch", "torch")),
    ("tensorflow", "ai_ml", ("tensorflow", "tf2")),
    ("keras", "ai_ml", ("keras",)),
    ("scikit-learn", "ai_ml", ("scikit-learn", "sklearn", "scikit learn")),
    ("nlp", "ai_ml", ("nlp", "natural language processing")),
    ("computer vision", "ai_ml", ("computer vision", "opencv")),
    ("llms", "ai_ml", ("llm", "llms", "large language models", "large language model", "genai", "generative ai")),
    ("rag", "ai_ml", ("rag", "retrieval augmented generation", "retrieval-augmented generation")),
    ("prompt engineering", "ai_ml", ("prompt engineering", "prompt design")),
    ("ai agents", "ai_ml", ("ai agents", "agentic", "tool use", "function calling")),
    ("hugging face", "ai_ml", ("hugging face", "huggingface", "transformers")),
    ("embeddings", "ai_ml", ("embeddings", "vector search", "semantic search")),
    ("pgvector", "ai_ml", ("pgvector", "pg_vector")),
    ("vector databases", "ai_ml", ("vector database", "vector databases", "pinecone", "qdrant", "weaviate", "chromadb", "faiss")),
    ("fine-tuning", "ai_ml", ("fine-tuning", "fine tuning", "lora", "peft", "qlora")),
    ("llm evaluation", "ai_ml", ("llm evals", "evals", "model evaluation", "ragas")),
    ("mlops", "ai_ml", ("mlops", "mlflow", "kubeflow", "weights & biases", "wandb")),
    ("xgboost", "ai_ml", ("xgboost", "lightgbm", "catboost")),
    ("onnx", "ai_ml", ("onnx", "onnx runtime", "onnxruntime")),
    ("vllm", "ai_ml", ("vllm", "tgi", "model serving")),
    ("langchain", "ai_ml", ("langchain", "langgraph", "llamaindex")),
    ("reinforcement learning", "ai_ml", ("reinforcement learning", "rlhf")),
    # Data Engineering & Analytics (18)
    ("pandas", "data", ("pandas",)),
    ("numpy", "data", ("numpy",)),
    ("scipy", "data", ("scipy",)),
    ("matplotlib", "data", ("matplotlib", "seaborn")),
    ("power bi", "data", ("power bi", "powerbi")),
    ("tableau", "data", ("tableau",)),
    ("excel", "data", ("excel", "ms excel", "advanced excel", "google sheets")),
    ("apache spark", "data", ("spark", "pyspark", "apache spark")),
    ("apache kafka", "data", ("kafka", "apache kafka")),
    ("apache airflow", "data", ("airflow", "apache airflow")),
    ("dbt", "data", ("dbt", "data build tool")),
    ("etl", "data", ("etl", "elt", "data pipelines", "data pipeline")),
    ("statistics", "data", ("statistics", "statistical analysis", "hypothesis testing")),
    ("a/b testing", "data", ("a/b testing", "ab testing", "experimentation")),
    ("data modeling", "data", ("data modeling", "dimensional modeling", "star schema")),
    ("snowflake", "data", ("snowflake",)),
    ("bigquery", "data", ("bigquery", "big query")),
    ("databricks", "data", ("databricks",)),
    # Databases & Caching (10)
    ("postgresql", "database", ("postgresql", "postgres", "psql")),
    ("mysql", "database", ("mysql", "mariadb")),
    ("mongodb", "database", ("mongodb", "mongo")),
    ("redis", "database", ("redis",)),
    ("elasticsearch", "database", ("elasticsearch", "opensearch")),
    ("sqlite", "database", ("sqlite",)),
    ("dynamodb", "database", ("dynamodb",)),
    ("cassandra", "database", ("cassandra",)),
    ("clickhouse", "database", ("clickhouse",)),
    ("neo4j", "database", ("neo4j", "graph database")),
    # Cloud & DevOps (16)
    ("docker", "cloud_devops", ("docker", "containers", "containerization")),
    ("kubernetes", "cloud_devops", ("kubernetes", "k8s")),
    ("aws", "cloud_devops", ("aws", "amazon web services", "ec2", "s3", "lambda")),
    ("gcp", "cloud_devops", ("gcp", "google cloud", "google cloud platform")),
    ("azure", "cloud_devops", ("azure", "microsoft azure")),
    ("linux", "cloud_devops", ("linux", "ubuntu", "unix")),
    ("git", "cloud_devops", ("git", "github", "gitlab", "version control")),
    ("ci/cd", "cloud_devops", ("ci/cd", "cicd", "github actions", "jenkins", "gitlab ci")),
    ("terraform", "cloud_devops", ("terraform", "infrastructure as code", "iac")),
    ("ansible", "cloud_devops", ("ansible",)),
    ("nginx", "cloud_devops", ("nginx", "reverse proxy")),
    ("prometheus", "cloud_devops", ("prometheus", "grafana", "observability")),
    ("opentelemetry", "cloud_devops", ("opentelemetry", "otel", "distributed tracing")),
    ("rabbitmq", "cloud_devops", ("rabbitmq", "message queues", "sqs")),
    ("serverless", "cloud_devops", ("serverless", "aws lambda", "cloud functions")),
    ("helm", "cloud_devops", ("helm",)),
    # Cybersecurity (12)
    ("network security", "security", ("network security", "firewalls", "tcp/ip", "wireshark")),
    ("owasp", "security", ("owasp", "owasp top 10", "application security", "appsec")),
    ("penetration testing", "security", ("penetration testing", "pentesting", "vapt", "ethical hacking")),
    ("siem", "security", ("siem", "splunk", "qradar", "microsoft sentinel")),
    ("soc operations", "security", ("soc", "security operations", "incident response")),
    ("burp suite", "security", ("burp suite", "burpsuite")),
    ("nmap", "security", ("nmap", "metasploit", "nessus")),
    ("cryptography", "security", ("cryptography", "tls", "ssl", "pki")),
    ("iam", "security", ("iam", "identity and access management", "zero trust")),
    ("cloud security", "security", ("cloud security", "devsecops", "cspm")),
    ("threat modeling", "security", ("threat modeling", "threat intelligence", "mitre att&ck")),
    ("vulnerability management", "security", ("vulnerability assessment", "vulnerability management", "cve")),
    # QA & Testing (10)
    ("pytest", "qa_testing", ("pytest", "unittest")),
    ("selenium", "qa_testing", ("selenium", "webdriver")),
    ("playwright", "qa_testing", ("playwright",)),
    ("cypress", "qa_testing", ("cypress",)),
    ("postman", "qa_testing", ("postman", "api testing", "rest assured")),
    ("jmeter", "qa_testing", ("jmeter", "load testing", "performance testing", "k6")),
    ("test automation", "qa_testing", ("test automation", "automation testing", "sdet")),
    ("manual testing", "qa_testing", ("manual testing", "test cases", "test plans", "regression testing")),
    ("junit", "qa_testing", ("junit", "testng", "jest")),
    ("appium", "qa_testing", ("appium", "mobile testing")),
    # Product & Fundamentals (10)
    ("product strategy", "product", ("product strategy", "product roadmap", "roadmapping")),
    ("user research", "product", ("user research", "customer interviews", "usability testing")),
    ("prd writing", "product", ("prd", "product requirements", "user stories")),
    ("product analytics", "product", ("product analytics", "mixpanel", "amplitude", "ga4", "google analytics")),
    ("figma", "product", ("figma", "wireframing", "prototyping")),
    ("agile", "product", ("agile", "scrum", "jira", "kanban")),
    ("data structures & algorithms", "fundamentals", ("dsa", "data structures", "algorithms", "problem solving")),
    ("system design", "fundamentals", ("system design", "distributed systems", "scalability")),
    ("oop", "fundamentals", ("oop", "object oriented", "object-oriented", "design patterns")),
    ("operating systems", "fundamentals", ("operating systems", "os concepts", "concurrency", "multithreading")),
]


@dataclass(frozen=True)
class ExtractedSkill:
    name: str
    category: str
    importance: int  # 3 = must-have, 2 = core, 1 = nice-to-have


def _compile_term_pattern(term: str) -> re.Pattern[str]:
    """Compile a boundary-aware case-insensitive regex for a skill synonym."""
    escaped = re.escape(term)
    # Word boundaries break around +, #, . (e.g., c++, c#, .net); use alphanumeric lookarounds.
    return re.compile(rf"(?<![A-Za-z0-9_]){escaped}(?![A-Za-z0-9_])", re.IGNORECASE)


_COMPILED_TAXONOMY: list[tuple[str, str, list[re.Pattern[str]]]] = [
    (name, category, [_compile_term_pattern(syn) for syn in synonyms])
    for name, category, synonyms in SKILL_TAXONOMY
]

_SYNONYM_TO_CANONICAL: dict[str, str] = {}
for _name, _cat, _syns in SKILL_TAXONOMY:
    _SYNONYM_TO_CANONICAL[_name.lower()] = _name
    for _syn in _syns:
        _SYNONYM_TO_CANONICAL[_syn.lower()] = _name

_NICE_TO_HAVE_SPLIT = re.compile(
    r"(good to have|nice to have|bonus|preferred|plus points?|optional)",
    re.IGNORECASE,
)
_MUST_HAVE_SECTION = re.compile(
    r"(must[- ]have|required skills?|requirements?|what you bring|qualifications?)",
    re.IGNORECASE,
)


def normalize_skill_name(raw_skill: str) -> str:
    """Map a user-provided skill string to its canonical taxonomy name when known."""
    cleaned = raw_skill.strip().lower()
    if cleaned in _SYNONYM_TO_CANONICAL:
        return _SYNONYM_TO_CANONICAL[cleaned]
    for name, _, patterns in _COMPILED_TAXONOMY:
        if any(p.fullmatch(cleaned) for p in patterns):
            return name
    return cleaned


def extract_skills(title: str, description: str) -> list[ExtractedSkill]:
    """Deterministically extract canonical skills and importance (1-3) via regex."""
    nice_split = _NICE_TO_HAVE_SPLIT.split(description, maxsplit=1)
    core_text = nice_split[0]
    nice_text = nice_split[1] + nice_split[2] if len(nice_split) >= 3 else ""

    must_split = _MUST_HAVE_SECTION.split(core_text, maxsplit=1)
    must_text = must_split[2] if len(must_split) >= 3 else core_text

    extracted: list[ExtractedSkill] = []
    for name, category, patterns in _COMPILED_TAXONOMY:
        in_title = any(p.search(title) for p in patterns)
        core_hits = sum(len(p.findall(core_text)) for p in patterns)
        must_hits = sum(len(p.findall(must_text)) for p in patterns)
        nice_hits = sum(len(p.findall(nice_text)) for p in patterns)

        if not (in_title or core_hits or nice_hits):
            continue

        if in_title or core_hits >= 2 or (must_hits >= 1 and core_hits >= 1 and len(must_split) >= 3):
            importance = 3
        elif core_hits >= 1:
            importance = 2
        else:
            importance = 1

        extracted.append(ExtractedSkill(name=name, category=category, importance=importance))

    extracted.sort(key=lambda s: (-s.importance, s.name))
    return extracted
