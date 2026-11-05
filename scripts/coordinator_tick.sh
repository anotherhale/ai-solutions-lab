#!/usr/bin/env bash
# Reconcile GitHub state, attempt auto-merge, and select the next eligible backlog task.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PATH="${HOME}/.local/bin:${PATH}"

if [[ -z "${DEVELOPMENT_OPS_RUN_ID:-}" ]]; then
  export DEVELOPMENT_OPS_RUN_ID="$(uuidgen)"
fi

python3 "${ROOT}/scripts/prepare_development_ops_database.py" >/dev/null

exec development-ops-record coordinator tick "$@"
