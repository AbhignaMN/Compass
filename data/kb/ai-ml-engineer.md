# AI / ML & LLM Engineer Career Guide (India Freshers)

## Role Overview
AI/ML Engineers and LLM/Agent Engineers build production machine learning pipelines, retrieval-augmented generation (RAG) systems, tool-using agents, and evaluation harnesses. For freshers in India, hiring is concentrated in Bengaluru, Hyderabad, Gurugram, Pune, and remote AI-first startups. Expect starting internships at INR 25,000 to 50,000/month and fresher full-time roles at INR 55,000 to 1,40,000/month depending on portfolio depth.

## Core Skills & Prerequisites
Must-have foundations include Python, SQL, Git, PyTorch or scikit-learn, FastAPI for serving models, embeddings and vector search (pgvector, FAISS, or Qdrant), structured outputs with Pydantic, and systematic evaluation (Recall@K, nDCG, LLM-as-judge). Nice-to-have differentiators include Docker, hybrid search with Reciprocal Rank Fusion, ONNX Runtime, fine-tuning with LoRA, and basic Linux/AWS deployment.

## 4-Week Learning Roadmap
- **Week 1 — Python, SQL & ML Foundations:** Refresh clean Python typing, async HTTP calls, NumPy/pandas data cleaning, and classical ML baselines (logistic regression, gradient boosting with scikit-learn/XGBoost). Deliverable: a clean Jupyter notebook + Python package benchmarking two baselines on a real tabular or text dataset with precision/recall metrics.
- **Week 2 — Embeddings, Hybrid Retrieval & pgvector:** Learn dense embeddings (BAAI/bge-small-en-v1.5), cosine similarity, HNSW indexing, PostgreSQL full-text search, and Reciprocal Rank Fusion. Deliverable: a PostgreSQL + pgvector search API over 500+ documents with a 30-query Recall@10 benchmark comparing vector-only vs hybrid search.
- **Week 3 — Hand-Written Tool-Use Agents & Structured Outputs:** Build an agent loop directly with the Anthropic or OpenAI SDK without heavy frameworks. Enforce Pydantic v2 validation, retry-on-error, grounded citations, and short/long-term memory. Deliverable: a working FastAPI agent with 4+ typed tools and automated multi-turn unit tests.
- **Week 4 — Evals, Docker Deployment & Portfolio Polish:** Containerize the service with a multi-stage Dockerfile, deploy to Render or Railway with Neon Postgres, write an automated evaluation script with a results table, and publish a crisp README with an architecture diagram.

## Free Courses & Resources
- **Fast.ai — Practical Deep Learning for Coders** (https://course.fast.ai): Best code-first introduction to PyTorch and deep learning.
- **Hugging Face NLP & Agents Courses** (https://huggingface.co/learn): Free hands-on modules on transformers, embeddings, and tool-using agents.
- **Anthropic Prompt Engineering & Tool Use Docs** (https://docs.anthropic.com): Authoritative guide on structured tool schemas, citations, and evals.
- **Stanford CS229 / Andrej Karpathy Neural Networks: Zero to Hero** (https://karpathy.ai/zero-to-hero.html): Deep conceptual intuition for transformers and backpropagation.
- **Eugene Yan & Hamel Husain Blogs on LLM Evals** (https://eugeneyan.com): Practical production RAG and evaluation patterns.

## Portfolio Projects & Interview Prep
Avoid generic "PDF chatbot with LangChain" repos. Build one end-to-end deployed system with real Postgres storage, deterministic hybrid search, and measured evaluation numbers (Recall@10, groundedness). In interviews, expect Python coding, SQL queries, cosine similarity vs BM25 trade-offs, HNSW vs IVFFlat indexing, hallucination mitigation, and walking through your eval rubric.

## Adjacent Roles & Trade-Offs
- **Backend Engineer (Python/FastAPI):** Easier fresher hiring volume; stronger emphasis on databases, APIs, and distributed systems rather than modeling.
- **Data Scientist / ML Analyst:** More statistics, experimentation (A/B testing), and business storytelling; less production software engineering.
- **Data Engineer:** Focuses on ETL pipelines, Airflow, dbt, and Spark; great stepping stone into MLOps.
