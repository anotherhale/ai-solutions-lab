#!/usr/bin/env bash
# Launcher for the persistent coordinator runner under launchd.
#
# launchd does not load ~/.zshrc or ~/.bash_profile, so this script builds the
# environment explicitly: it sets PATH, loads an optional mode-600 env file,
# and then execs the runner. It is also safe to run by hand for smoke testing.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PATH="${HOME}/.local/bin:/opt/homebrew/bin:${PATH}"

# Optional secret/runtime environment file, kept out of version control.
# Expected to contain exports such as GH_TOKEN. Never commit this file.
ENV_FILE="${DEVELOPMENT_OPS_RUNNER_ENV_FILE:-${HOME}/.config/ai-solutions-lab/coordinator-runner.env}"
if [[ -f "${ENV_FILE}" ]]; then
  # shellcheck disable=SC1090
  source "${ENV_FILE}"
fi

PYTHON="${ROOT}/services/wasatch-api/.venv/bin/python"
if [[ ! -x "${PYTHON}" ]]; then
  PYTHON="$(command -v python3)"
fi

if [[ -z "${DEVELOPMENT_OPS_RUN_ID:-}" ]]; then
  export DEVELOPMENT_OPS_RUN_ID="$("${PYTHON}" -c 'import uuid; print(uuid.uuid4())')"
fi

exec "${PYTHON}" -m development_ops.cli runner "$@"
