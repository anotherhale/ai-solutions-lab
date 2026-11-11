#!/usr/bin/env sh
# Build the API image, start Compose, and verify health and document routes.
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

export POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-replace-me}"
export POSTGRES_USER="${POSTGRES_USER:-wasatch}"
export POSTGRES_DB="${POSTGRES_DB:-wasatch}"
export API_PORT="${API_PORT:-8000}"

$COMPOSE build api
$COMPOSE up -d

cleanup() {
  $COMPOSE down
}
trap cleanup EXIT INT TERM

echo "Waiting for API health..."
attempt=0
until curl -sf "http://127.0.0.1:${API_PORT}/health" >/dev/null 2>&1; do
  attempt=$((attempt + 1))
  if [ "$attempt" -ge 60 ]; then
    echo "API did not become healthy in time." >&2
    $COMPOSE logs api
    exit 1
  fi
  sleep 2
done

curl -sf "http://127.0.0.1:${API_PORT}/health" | python3 -c "import json,sys; d=json.load(sys.stdin); assert d.get('status')=='ok', d"
curl -sf "http://127.0.0.1:${API_PORT}/health/ready" | python3 -c "import json,sys; d=json.load(sys.stdin); assert d.get('status')=='ready', d"

python3 <<'PY'
import json
import os
import urllib.request

port = os.environ.get("API_PORT", "8000")
base = f"http://127.0.0.1:{port}"
with urllib.request.urlopen(f"{base}/openapi.json") as response:
    paths = json.load(response)["paths"]
assert any("document-extractions" in path for path in paths), paths.keys()
for required in (
    "/api/v1/invoices",
    "/api/v1/invoices/{invoice_id}",
    "/api/v1/payments",
    "/api/v1/payments/{payment_id}",
):
    assert required in paths, f"missing {required}; have {sorted(paths)}"

actor_header = {"X-Laboratory-Actor": "emp_0001"}
request = urllib.request.Request(
    f"{base}/api/v1/invoices",
    headers=actor_header,
)
with urllib.request.urlopen(request) as response:
    body = json.load(response)
items = body.get("items")
assert isinstance(items, list) and len(items) > 0, body
PY

echo "Compose smoke checks passed."
