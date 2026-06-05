#!/usr/bin/env bash
# Provision staging VPS — run once as root on a fresh Debian/Ubuntu server.
# Idempotent: safe to re-run.
set -euo pipefail

DOMAIN="${DOMAIN:?Set DOMAIN env var}"
EMAIL="${CERTBOT_EMAIL:?Set CERTBOT_EMAIL env var}"
APP_DIR=/opt/pole-emploi

# ── Docker ────────────────────────────────────────────────────────────────────
if ! command -v docker &>/dev/null; then
  curl -fsSL https://get.docker.com | sh
  systemctl enable --now docker
fi

# ── App directory ─────────────────────────────────────────────────────────────
mkdir -p "$APP_DIR"

# ── Certbot (initial certificate) ────────────────────────────────────────────
if [ ! -d "/etc/letsencrypt/live/$DOMAIN" ]; then
  docker run --rm \
    -v /etc/letsencrypt:/etc/letsencrypt \
    -v /var/www/certbot:/var/www/certbot \
    -p 80:80 \
    certbot/certbot certonly --standalone \
      --non-interactive --agree-tos \
      --email "$EMAIL" \
      -d "$DOMAIN"
fi

# ── UFW firewall ──────────────────────────────────────────────────────────────
if command -v ufw &>/dev/null; then
  ufw allow 22/tcp
  ufw allow 80/tcp
  ufw allow 443/tcp
  ufw --force enable
fi

echo "Provisioning complete. Deploy with: cd $APP_DIR && docker compose -f docker-compose.yml -f infra/docker-compose.staging.yml up -d"
