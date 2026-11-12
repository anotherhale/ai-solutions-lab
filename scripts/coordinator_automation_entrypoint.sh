#!/usr/bin/env bash
# Primary entrypoint for the "AI Solutions Lab — Continue Development" automation.
# 1. Reconcile GitHub + backlog and select the next eligible task (no duplicate assign).
# 2. Print JSON for the automation agent, including delegation instructions.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_BIN="${ROOT}/services/wasatch-api/.venv/bin"
export PATH="${VENV_BIN}:${HOME}/.local/bin:${PATH}"

# Cloud agents often start on `main` while integration and the coordinator catalog
# live on `develop`. The tick reads paths from the working tree, not from GitHub.
sync_coordinator_sources_from_develop() {
  if ! git -C "${ROOT}" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    return 0
  fi
  if ! git -C "${ROOT}" remote get-url origin >/dev/null 2>&1; then
    return 0
  fi
  local branch
  branch="$(git -C "${ROOT}" rev-parse --abbrev-ref HEAD 2>/dev/null || true)"
  if [[ -z "${branch}" || "${branch}" == "develop" ]]; then
    return 0
  fi
  git -C "${ROOT}" fetch -q origin develop 2>/dev/null || true
  if ! git -C "${ROOT}" rev-parse --verify origin/develop >/dev/null 2>&1; then
    return 0
  fi
  git -C "${ROOT}" checkout -q origin/develop -- data/coordinator/backlog.yaml \
    libs/development_ops 2>/dev/null || true
}
sync_coordinator_sources_from_develop

PYTHON="${VENV_BIN}/python"
if [[ ! -x "${PYTHON}" ]]; then
  PYTHON="python3"
fi

if [[ -x "${PYTHON}" ]] && ! command -v development-ops-record >/dev/null 2>&1; then
  "${PYTHON}" -m pip install -q -e "${ROOT}/libs/development_ops"
fi

if [[ -z "${DEVELOPMENT_OPS_RUN_ID:-}" ]]; then
  export DEVELOPMENT_OPS_RUN_ID="$(python3 -c 'import uuid; print(uuid.uuid4())')"
fi
export DEVELOPMENT_OPS_AGENT_NAME="${DEVELOPMENT_OPS_AGENT_NAME:-coordinator-automation}"
export DEVELOPMENT_OPS_GITHUB_REPOSITORY="${DEVELOPMENT_OPS_GITHUB_REPOSITORY:-anotherhale/ai-solutions-lab}"

"${PYTHON}" "${ROOT}/scripts/prepare_development_ops_database.py" >/dev/null

TICK_JSON="$(mktemp)"
development-ops-record coordinator tick --notify-slack >"${TICK_JSON}"
cat "${TICK_JSON}"

SELECTED="$(python3 -c "import json,sys; d=json.load(open(sys.argv[1])); print(d.get('selected_task_id') or '')" "${TICK_JSON}")"
if [[ -z "${SELECTED}" ]]; then
  echo '{"delegation":"none","reason":"no eligible task"}'
  exit 0
fi

export DEVELOPMENT_OPS_TASK_ID="${SELECTED}"
scripts/coordinator_activity.sh task-delegated "Delegated ${SELECTED} to implementation agent" \
  --metadata "{\"task_id\":\"${SELECTED}\",\"coordinator_run_id\":\"${DEVELOPMENT_OPS_RUN_ID}\"}" \
  --no-slack || true

cat <<EOF
{"delegation":"implementation","task_id":"${SELECTED}","instruction":"Implement backlog task ${SELECTED} on a cursor/* branch from develop. Record activity milestones, run tests, open a PR to develop, then run scripts/coordinator_tick.sh again without waiting for merge."}
EOF
