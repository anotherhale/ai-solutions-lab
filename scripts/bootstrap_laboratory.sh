#!/usr/bin/env sh
# One-time workstation setup: Postgres, Python venv, review app, and Playwright deps.
set -eu
ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$ROOT"

if docker compose version >/dev/null 2>&1; then
  COMPOSE="docker compose"
elif docker-compose version >/dev/null 2>&1; then
  COMPOSE="docker-compose"
else
  echo "Docker Compose is required." >&2
  exit 1
fi

$COMPOSE up -d postgres
echo "Waiting for PostgreSQL..."
until $COMPOSE exec -T postgres pg_isready -U "${POSTGRES_USER:-wasatch}" -d "${POSTGRES_DB:-wasatch}" >/dev/null 2>&1
do
  sleep 1
done

if [ ! -d "$ROOT/services/wasatch-api/.venv" ]; then
  python3.12 -m venv "$ROOT/services/wasatch-api/.venv"
fi
# shellcheck disable=SC1091
. "$ROOT/services/wasatch-api/.venv/bin/activate"
python -m pip install --upgrade pip
pip install -e "$ROOT/services/wasatch-api[dev]"

cd "$ROOT/apps/wasatch-review"
npm ci

cd "$ROOT/tests/e2e"
npm ci
npx playwright install chromium

echo ""
echo "Laboratory bootstrap complete."
echo "  API:    scripts/wasatch_dev.sh   (or scripts/run_wasatch_api_host.sh for non-reload)"
echo "  UI:     cd apps/wasatch-review && npm run dev"
echo "  E2E:    cd tests/e2e && npm test"
echo "  Compose smoke: scripts/smoke_compose.sh"
