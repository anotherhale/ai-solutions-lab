#!/usr/bin/env sh
# Audit Wasatch API dependencies in an isolated virtual environment.
set -eu
ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
AUDIT_VENV="${TMPDIR:-/tmp}/wasatch-pip-audit-venv"
python3 -m venv "$AUDIT_VENV"
# shellcheck disable=SC1091
. "$AUDIT_VENV/bin/activate"
python -m pip install --upgrade pip "pip-audit==2.9.0"
python -m pip install -e "$ROOT/services/wasatch-api[dev]"

# Temporary until SEC-1 implements ADR 0007 (Starlette 1.x + FastAPI bound bump).
STARLETTE_IGNORES="PYSEC-2026-161 PYSEC-2026-249 PYSEC-2026-248 PYSEC-2026-2281 PYSEC-2026-2280"
set -- python -m pip_audit --skip-editable
for id in $STARLETTE_IGNORES; do
  set -- "$@" --ignore-vuln "$id"
done
exec "$@"
