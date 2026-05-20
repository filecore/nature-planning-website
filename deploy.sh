#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if [[ ! -f .env ]]; then
  echo "Missing .env (copy .env.example and edit REMOTE_HOST / REMOTE_DIR / NATURE_DOMAIN)" >&2
  exit 1
fi

# shellcheck disable=SC1091
set -a; source .env; set +a
: "${REMOTE_HOST:?REMOTE_HOST not set in .env}"
: "${REMOTE_DIR:?REMOTE_DIR not set in .env}"
: "${NATURE_DOMAIN:?NATURE_DOMAIN not set in .env}"

echo "Syncing source to ${REMOTE_HOST}:${REMOTE_DIR}/"
ssh "$REMOTE_HOST" "mkdir -p '$REMOTE_DIR'"

rsync -av --delete \
  --exclude='.git/' \
  --exclude='.venv/' \
  --exclude='__pycache__/' \
  --exclude='*.pyc' \
  ./ "$REMOTE_HOST:$REMOTE_DIR/"

echo "Starting / restarting container"
ssh "$REMOTE_HOST" "cd '$REMOTE_DIR' && docker compose up -d"

# nginx.conf is bind-mounted, so a config edit will not be detected by
# 'compose up -d' on its own. Reload nginx in-place to pick up any changes.
ssh "$REMOTE_HOST" "docker exec nature nginx -s reload" >/dev/null 2>&1 || true

echo "Done. Site: https://${NATURE_DOMAIN}/"
