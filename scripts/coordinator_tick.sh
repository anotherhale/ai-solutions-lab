#!/usr/bin/env bash
# Reconcile GitHub state, attempt auto-merge, and select the next eligible backlog task.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PATH="${HOME}/.local/bin:${PATH}"

if [[ -z "${DEVELOPMENT_OPS_RUN_ID:-}" ]]; then
  export DEVELOPMENT_OPS_RUN_ID="$(python3 -c 'import uuid; print(uuid.uuid4())')"
fi

PYTHON="${ROOT}/services/wasatch-api/.venv/bin/python"
if [[ ! -x "${PYTHON}" ]]; then PYTHON=python3; fi
"${PYTHON}" "${ROOT}/scripts/prepare_development_ops_database.py" >/dev/null

exec development-ops-record coordinator tick "$@"
