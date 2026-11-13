#!/usr/bin/env bash
# Replace data/coordinator/backlog.yaml with origin/<integration_branch> when the remote
# catalog lists more tasks than the working tree (typical when Cloud Agents boot from main).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKLOG="${ROOT}/data/coordinator/backlog.yaml"
BRANCH="${DEVELOPMENT_OPS_INTEGRATION_BRANCH:-develop}"

if [[ ! -f "$BACKLOG" ]]; then
  exit 0
fi
if ! git -C "$ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  exit 0
fi

git -C "$ROOT" fetch origin "$BRANCH" --quiet 2>/dev/null || exit 0
if ! git -C "$ROOT" rev-parse --verify "origin/${BRANCH}" >/dev/null 2>&1; then
  exit 0
fi

REMOTE="$(git -C "$ROOT" show "origin/${BRANCH}:data/coordinator/backlog.yaml" 2>/dev/null)" || exit 0
if [[ -z "$REMOTE" ]]; then
  exit 0
fi

count_tasks() {
  printf '%s' "$1" | grep -c '^  - id:' || true
}

LOCAL_TASKS="$(count_tasks "$(<"$BACKLOG")")"
REMOTE_TASKS="$(count_tasks "$REMOTE")"

if [[ "$REMOTE_TASKS" -gt "$LOCAL_TASKS" ]]; then
  printf '%s' "$REMOTE" >"$BACKLOG"
fi
