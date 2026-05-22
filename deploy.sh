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

# Stage to a tempdir and rewrite the __BUILD__ cache-buster placeholder
# in index.html with the current epoch seconds so every deploy
# invalidates Cloudflare + browser caches for the static asset list.
STAGE_DIR="$(mktemp -d)"
trap 'rm -rf "${STAGE_DIR}"' EXIT
rsync -a \
  --exclude='.git/' \
  --exclude='.venv/' \
  --exclude='__pycache__/' \
  --exclude='*.pyc' \
  --exclude='data/cache/' \
  ./ "${STAGE_DIR}/"
BUILD_ID="$(date +%s)"
sed -i "s/__BUILD__/${BUILD_ID}/g" "${STAGE_DIR}/src/index.html"

rsync -av --delete \
  --exclude='data/cache/' \
  "${STAGE_DIR}/" "$REMOTE_HOST:$REMOTE_DIR/"

echo "Build id: ${BUILD_ID}"

echo "Starting / restarting container"
ssh "$REMOTE_HOST" "cd '$REMOTE_DIR' && docker compose up -d"

# rsync replaces files via tmp + rename, which gives nginx.conf a new
# inode. The bind mount in the container still points at the old one,
# so 'nginx -s reload' would re-read the old contents. Restart the
# container to pick up the freshly-written file.
ssh "$REMOTE_HOST" "docker restart nature" >/dev/null

echo "Done. Site: https://${NATURE_DOMAIN}/"
