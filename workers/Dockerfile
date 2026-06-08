FROM python:3.12-slim AS base

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN useradd -m -u 1001 worker && chown -R worker /app
USER worker

# ── Celery worker (scraping) ─────────────────────────────────────────────────
FROM base AS worker
CMD ["celery", "-A", "tasks", "worker", "--loglevel=info", "--queues=scraping,default"]

# ── Celery Beat (scheduler) ──────────────────────────────────────────────────
FROM base AS scheduler
# Create a dedicated data dir owned by worker so named-volume mounts inherit the right permissions
RUN mkdir -p /app/celerybeat
CMD ["celery", "-A", "tasks", "beat", "--loglevel=info", "--scheduler", "celery.beat:PersistentScheduler", "--schedule=/app/celerybeat/celerybeat-schedule"]
