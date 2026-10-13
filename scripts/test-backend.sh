#!/usr/bin/env bash
# Lance pytest du backend dans l'image backend publiée, sur l'hôte pole-emploi (pas de Docker local).
# Usage : scripts/test-backend.sh [arguments pytest]   (IMAGE_TAG=<sha40> pour changer d'image)
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
tag="${IMAGE_TAG:-7887e06ce593aa5409c3b1bd55c1e0be369edbff}"
args="${*:-tests}"
tar -cf - -C "$root/backend" --exclude=__pycache__ --exclude=test.db . |
	ssh pole-emploi "set -e; d=\$(mktemp -d); trap 'rm -rf \$d' EXIT; tar --no-same-owner -xf - -C \$d; docker run --rm -u 0 -v \$d:/app -w /app ghcr.io/cilag/pole-emploi-backend:$tag sh -c 'pip install -q --disable-pip-version-check --root-user-action=ignore -r requirements-dev.txt && python -m pytest -q -p no:cacheprovider $args'"
