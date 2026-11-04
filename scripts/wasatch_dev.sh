#!/usr/bin/env sh
# Start PostgreSQL, wait until healthy, migrate, seed, and run the API on the host.
set -eu
ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$ROOT"

if docker compose version >/dev/null 2>&1; then
  COMPOSE="docker compose"
elif docker-compose version >/dev/null 2>&1; then
  COMPOSE="docker-compose"
else
  echo "Docker Compose is required (docker compose or docker-compose)." >&2
  exit 1
fi

$COMPOSE up -d postgres

echo "Waiting for PostgreSQL health..."
until $COMPOSE exec -T postgres pg_isready -U "${POSTGRES_USER:-wasatch}" -d "${POSTGRES_DB:-wasatch}" >/dev/null 2>&1
do
  sleep 1
done

if [ ! -d "$ROOT/services/wasatch-api/.venv" ]; then
  echo "Create services/wasatch-api/.venv and install the package first." >&2
  echo "  python3.12 -m venv services/wasatch-api/.venv" >&2
  echo "  . services/wasatch-api/.venv/bin/activate" >&2
  echo "  pip install -e 'services/wasatch-api[dev]'" >&2
  exit 1
fi

# shellcheck disable=SC1091
. "$ROOT/services/wasatch-api/.venv/bin/activate"
cd "$ROOT/services/wasatch-api"
alembic upgrade head
wasatch-api seed
exec uvicorn wasatch_api.main:app --reload --host 0.0.0.0 --port "${API_PORT:-8000}"
