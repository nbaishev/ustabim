#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FRONT_DIR="${ROOT_DIR}/revit-academy-online"
NGINX_DIST="${ROOT_DIR}/nginx/dist"
ENV_FILE="${1:-${ROOT_DIR}/.env}"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Env file not found: $ENV_FILE"
  echo "Usage: ./scripts/build_frontend.sh /path/to/.env"
  exit 1
fi

if [[ ! -d "$FRONT_DIR" ]]; then
  echo "Frontend directory not found: $FRONT_DIR"
  exit 1
fi

FRONT_ENV_FILE="${FRONT_DIR}/.env.production.local"

grep -E '^[[:space:]]*VITE_' "$ENV_FILE" > "$FRONT_ENV_FILE" || true

if ! grep -q '^VITE_API_BASE_URL=' "$FRONT_ENV_FILE"; then
  echo "VITE_API_BASE_URL is missing in $ENV_FILE"
  exit 1
fi

cd "$FRONT_DIR"
npm ci
npm run build

mkdir -p "$NGINX_DIST"
cp -R "${FRONT_DIR}/dist/." "$NGINX_DIST/"

echo "Frontend build complete. Output copied to ${NGINX_DIST}"
