# Multi-stage Dockerfile for Compass API (Python 3.11, non-root)

FROM python:3.11-slim AS builder

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

# Create non-root user and writable cache directory
RUN groupadd --gid 10001 compass && \
    useradd --uid 10001 --gid compass --shell /bin/bash --create-home compass

COPY --from=builder /opt/venv /opt/venv
COPY --chown=compass:compass . /app

RUN mkdir -p /app/.fastembed_cache && \
    chown -R compass:compass /app/.fastembed_cache && \
    chmod +x /app/scripts/start.sh

USER compass

EXPOSE 8000

CMD ["/app/scripts/start.sh"]
