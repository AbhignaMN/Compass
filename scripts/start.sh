#!/usr/bin/env bash
set -euo pipefail

echo "[compass] Running Alembic migrations..."
alembic upgrade head

if [ "${SEED_ON_START:-false}" = "true" ] && [ -f "scripts/seed_jobs.py" ]; then
  echo "[compass] Ensuring seed jobs and KB chunks are loaded..."
  python -m scripts.seed_jobs --if-empty
fi

echo "[compass] Starting FastAPI server on port ${PORT:-8000}..."
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
