# bookworm : les deps apt de playwright 1.49 (ttf-unifont, ttf-ubuntu-font-family) n existent plus sur trixie
FROM python:3.12-slim-bookworm AS base

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
 && rm -rf /var/lib/apt/lists/*

COPY workers/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY workers/ .
# Les tâches font sys.path.insert(../../backend) : le code du backend vit dans l'image, plus de montage.
COPY backend/ /backend/

# Navigateurs Playwright (scrapers indeed/linkedin/hellowork/monster/letudiant).
# Installés dans un chemin partagé lisible par l'utilisateur "worker".
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
RUN apt-get update && playwright install --with-deps chromium && chmod -R a+rX /ms-playwright && rm -rf /var/lib/apt/lists/*

# celery-data : repertoire du volume beat ; chown ici pour que le volume nomme herite des droits de "worker"
RUN useradd -m -u 1001 worker && mkdir -p /app/celery-data && chown -R worker /app
USER worker

# ── Celery worker (scraping) ─────────────────────────────────────────────────
FROM base AS worker
CMD ["celery", "-A", "tasks", "worker", "--loglevel=info", "--queues=scraping,ai,default,celery"]

# ── Celery Beat (scheduler) ──────────────────────────────────────────────────
FROM base AS scheduler
CMD ["celery", "-A", "tasks", "beat", "--loglevel=info", "--scheduler", "celery.beat:PersistentScheduler"]
