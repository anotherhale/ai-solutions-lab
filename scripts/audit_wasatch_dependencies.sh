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

# SEC-1 removed the Starlette PYSEC ignores. Do not add --ignore-vuln
# entries for Starlette or FastAPI without a new ADR section.
exec python -m pip_audit --skip-editable
