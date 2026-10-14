#!/usr/bin/env bash
# Vérifie que le backend de la branche s'importe dans l'image worker publiée après installation
# de workers/requirements.txt (sur l'hôte pole-emploi, pas de Docker local).
# Usage : scripts/check-worker-imports.sh   (IMAGE_TAG=<sha40> pour changer d'image)
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
tag="${IMAGE_TAG:-7887e06ce593aa5409c3b1bd55c1e0be369edbff}"
# Modules backend importés par workers/tasks/*.py (+ app.schemas.offre, cause du bug email-validator).
mods="app.db.session, app.models.cv, app.models.offre, app.schemas.offre, app.services.scan, app.services.scrapers, app.services.scrapers.linkedin, app.services.lettres, app.services.ai.letter_generator, app.services.email_service, tasks.ai, tasks.scraping, tasks.cv_audit, app.services.appartements.imap, app.services.appartements.pipeline, tasks.appartements"
tar -cf - -C "$root" --exclude=node_modules --exclude=frontend --exclude=.git --exclude=.superpowers --exclude=__pycache__ --exclude=test.db workers backend |
	ssh pole-emploi "set -e; d=\$(mktemp -d); trap 'rm -rf \$d' EXIT; tar --no-same-owner -xf - -C \$d; docker run --rm -u 0 -v \$d/workers:/app -v \$d/backend:/backend -w /app ghcr.io/cilag/pole-emploi-worker:$tag sh -c 'pip install -q --disable-pip-version-check --root-user-action=ignore -r requirements.txt && python -c \"import sys; sys.path.insert(0, \\\"/backend\\\"); import $mods; print(\\\"worker-imports-ok\\\")\"'"
