#!/usr/bin/env bash
# Coordinator lifecycle shorthand over development-ops-record.
#
# Usage:
#   export DEVELOPMENT_OPS_RUN_ID=<uuid>
#   export DEVELOPMENT_OPS_GITHUB_REPOSITORY=org/repo
#   scripts/coordinator_activity.sh run-start "Phase 2 instrumentation"
#   scripts/coordinator_activity.sh task-selected DEV-42 "Implement CLI"
#   scripts/coordinator_activity.sh tests-passed "pytest green"
#   scripts/coordinator_activity.sh pr-opened 33 "Open Phase 2 PR" --github-pull-number 33
#
# Exit codes match development-ops-record (1 = persistence failed, 2 = Slack failed).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RECORD="${ROOT}/scripts/coordinator_record_activity.sh"

if [[ $# -lt 1 ]]; then
  echo "usage: $0 <milestone> [title] [extra record args...]" >&2
  exit 64
fi

MILESTONE="$1"
shift
TITLE="${1:-}"
if [[ -n "$TITLE" ]]; then
  shift
fi

case "$MILESTONE" in
  run-start)
    exec "$RECORD" record --event-type run.started --severity info \
      --title "${TITLE:-Coordinator run started}" "$@"
    ;;
  run-complete)
    exec "$RECORD" record --event-type run.completed --severity info \
      --title "${TITLE:-Coordinator run completed}" "$@"
    ;;
  run-failed)
    exec "$RECORD" record --event-type run.failed --severity error \
      --title "${TITLE:-Coordinator run failed}" "$@"
    ;;
  task-selected)
    TASK="${DEVELOPMENT_OPS_TASK_ID:-}"
    if [[ -z "$TASK" ]]; then
      echo "set DEVELOPMENT_OPS_TASK_ID for task-selected" >&2
      exit 64
    fi
    exec "$RECORD" record --event-type task.selected --severity info \
      --task-id "$TASK" --title "${TITLE:-Task selected}" "$@"
    ;;
  task-delegated)
    exec "$RECORD" record --event-type task.delegated --severity info \
      --title "${TITLE:-Task delegated}" "$@"
    ;;
  implementation)
    exec "$RECORD" record --event-type implementation.milestone --severity notice \
      --title "${TITLE:-Implementation milestone}" "$@"
    ;;
  tests-start)
    exec "$RECORD" record --event-type test.started --severity info \
      --title "${TITLE:-Tests started}" "$@"
    ;;
  tests-passed)
    exec "$RECORD" record --event-type test.completed --severity info \
      --title "${TITLE:-Tests passed}" "$@"
    ;;
  tests-failed)
    exec "$RECORD" record --event-type test.failed --severity error \
      --title "${TITLE:-Tests failed}" "$@"
    ;;
  review-start)
    exec "$RECORD" record --event-type review.started --severity info \
      --title "${TITLE:-Review started}" "$@"
    ;;
  review-complete)
    exec "$RECORD" record --event-type review.completed --severity notice \
      --title "${TITLE:-Review completed}" "$@"
    ;;
  pr-opened)
    exec "$RECORD" record --event-type pr.opened --severity notice \
      --title "${TITLE:-Pull request opened}" "$@"
    ;;
  pr-updated)
    exec "$RECORD" record --event-type pr.updated --severity info \
      --title "${TITLE:-Pull request updated}" "$@"
    ;;
  pr-merged)
    exec "$RECORD" record --event-type pr.merged --severity notice \
      --title "${TITLE:-Pull request merged}" "$@"
    ;;
  blocker)
    exec "$RECORD" record --event-type blocker.reported --severity warning \
      --title "${TITLE:-Blocker reported}" "$@"
    ;;
  progress)
    exec "$RECORD" record --event-type progress.report --severity info \
      --title "${TITLE:-Progress report}" "$@"
    ;;
  *)
    echo "unknown milestone: $MILESTONE" >&2
    exit 64
    ;;
esac
