#!/usr/bin/env bash
# Record a development activity event via development-ops-record.
# Requires: pip install -e libs/development_ops, WASATCH_DATABASE_URL, DEVELOPMENT_OPS_RUN_ID
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PATH="${HOME}/.local/bin:${PATH}"

if ! command -v development-ops-record >/dev/null 2>&1; then
  python3 -m pip install -q -e "${ROOT}/libs/development_ops" >/dev/null
fi

exec development-ops-record "$@"
