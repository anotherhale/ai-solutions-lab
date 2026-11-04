#!/usr/bin/env sh
# Migrate and seed PostgreSQL, then serve the API on the host (CI and browser tests).
set -eu
ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$ROOT"

export APP_ENV="${APP_ENV:-test}"
export AI_PROVIDER="${AI_PROVIDER:-fake}"
export WASATCH_DATABASE_URL="${WASATCH_DATABASE_URL:-postgresql+psycopg://wasatch:wasatch@localhost:5432/wasatch_test}"
export WASATCH_REQUIRE_DATABASE="${WASATCH_REQUIRE_DATABASE:-1}"

python3 scripts/prepare_wasatch_database.py

if [ -d "$ROOT/services/wasatch-api/.venv" ]; then
  # shellcheck disable=SC1091
  . "$ROOT/services/wasatch-api/.venv/bin/activate"
else
  python3 -m pip install -q -e "$ROOT/services/wasatch-api[dev]"
fi

cd "$ROOT/services/wasatch-api"
exec uvicorn wasatch_api.main:app --host 127.0.0.1 --port "${API_PORT:-8000}"
