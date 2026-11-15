#!/usr/bin/env bash
# Primary entrypoint for the "AI Solutions Lab — Continue Development" automation.
# 1. Reconcile GitHub + backlog and select the next eligible task (no duplicate assign).
# 2. Print JSON for the automation agent, including delegation instructions.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_BIN="${ROOT}/services/wasatch-api/.venv/bin"
export PATH="${VENV_BIN}:${HOME}/.local/bin:${PATH}"
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
# One variable governs both the catalog sync source and the delegation target so a
# run never integrates on a different branch than the one it read catalog state from.
export DEVELOPMENT_OPS_INTEGRATION_BRANCH="${DEVELOPMENT_OPS_INTEGRATION_BRANCH:-develop}"

"${ROOT}/scripts/coordinator_sync_integration_backlog.sh"

"${PYTHON}" "${ROOT}/scripts/prepare_development_ops_database.py" >/dev/null

# Automation VMs may check out `main` while the catalog on `develop` is authoritative.
# Load backlog from the integration branch ref when available (override with
# DEVELOPMENT_OPS_BACKLOG_FROM_INTEGRATION=0 to use the working tree file).
BACKLOG_ARGS=()
INTEGRATION_BACKLOG=""
if [[ "${DEVELOPMENT_OPS_BACKLOG_FROM_INTEGRATION:-1}" != "0" ]]; then
  INTEGRATION_BRANCH="${DEVELOPMENT_OPS_INTEGRATION_BRANCH:-develop}"
  git -C "${ROOT}" fetch -q origin "${INTEGRATION_BRANCH}" 2>/dev/null || true
  if git -C "${ROOT}" rev-parse --verify "origin/${INTEGRATION_BRANCH}" >/dev/null 2>&1; then
    CATALOG_REF="origin/${INTEGRATION_BRANCH}:data/coordinator/backlog.yaml"
    if git -C "${ROOT}" cat-file -e "${CATALOG_REF}" 2>/dev/null; then
      INTEGRATION_BACKLOG="$(mktemp)"
      git -C "${ROOT}" show "${CATALOG_REF}" >"${INTEGRATION_BACKLOG}"
      BACKLOG_ARGS=(--backlog "${INTEGRATION_BACKLOG}")
    fi
  fi
fi
trap '[[ -n "${INTEGRATION_BACKLOG}" ]] && rm -f "${INTEGRATION_BACKLOG}"' EXIT

TICK_JSON="$(mktemp)"
development-ops-record coordinator tick --notify-slack "${BACKLOG_ARGS[@]}" >"${TICK_JSON}"
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
{"delegation":"implementation","task_id":"${SELECTED}","instruction":"Implement backlog task ${SELECTED} on a cursor/* branch from ${DEVELOPMENT_OPS_INTEGRATION_BRANCH}. Record activity milestones, run tests, open a PR to ${DEVELOPMENT_OPS_INTEGRATION_BRANCH}, then run scripts/coordinator_tick.sh again without waiting for merge."}
EOF
