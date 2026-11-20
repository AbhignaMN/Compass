# Multi-stage Dockerfile for Compass (Next.js static UI + Python 3.11 FastAPI, non-root)

FROM node:22-slim AS frontend-builder

WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci || npm install
COPY frontend/ ./
RUN npm run build


FROM python:3.11-slim AS python-builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt


FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    EMBEDDING_CACHE_DIR="/app/.fastembed_cache" \
    PORT=8000

WORKDIR /app

RUN groupadd --gid 10001 compass && \
    useradd --uid 10001 --gid compass --shell /bin/bash --create-home compass

COPY --from=python-builder /opt/venv /opt/venv
COPY --chown=compass:compass . /app
COPY --from=frontend-builder --chown=compass:compass /frontend/out /app/frontend/out

RUN mkdir -p /app/.fastembed_cache && \
    chown -R compass:compass /app/.fastembed_cache && \
    chmod +x /app/scripts/start.sh

USER compass

EXPOSE 8000

CMD ["/app/scripts/start.sh"]
