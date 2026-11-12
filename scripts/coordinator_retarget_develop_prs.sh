#!/usr/bin/env bash
# List open pull requests targeting ``develop`` and attempt to retarget them to
# ``ai-dev`` (ADR 0010 / ADR 0014). Requires ``gh`` with permission to update
# pull requests (GraphQL updatePullRequest).
#
# Usage:
#   scripts/coordinator_retarget_develop_prs.sh          # dry-run (default)
#   scripts/coordinator_retarget_develop_prs.sh --apply  # call gh pr edit --base ai-dev
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APPLY=0
if [[ "${1:-}" == "--apply" ]]; then
  APPLY=1
elif [[ -n "${1:-}" ]]; then
  echo "usage: $0 [--apply]" >&2
  exit 64
fi

if ! command -v gh >/dev/null 2>&1; then
  echo "gh CLI is required" >&2
  exit 1
fi

TARGET_BASE="ai-dev"
JSON="$(mktemp)"
trap 'rm -f "${JSON}"' EXIT

gh pr list \
  --repo "${DEVELOPMENT_OPS_GITHUB_REPOSITORY:-anotherhale/ai-solutions-lab}" \
  --state open \
  --base develop \
  --limit 100 \
  --json number,title,headRefName,mergeable,mergeStateStatus \
  >"${JSON}"

COUNT="$(python3 -c "import json; print(len(json.load(open('${JSON}'))))")"
if [[ "${COUNT}" -eq 0 ]]; then
  echo "No open pull requests target develop."
  exit 0
fi

echo "Found ${COUNT} open pull request(s) targeting develop (retarget base → ${TARGET_BASE})."
if [[ "${APPLY}" -eq 0 ]]; then
  echo "Dry-run only. Re-run with --apply to call gh pr edit --base ${TARGET_BASE}."
fi

python3 <<PY
import json
import subprocess
import sys

apply = ${APPLY}
target = "${TARGET_BASE}"
prs = json.load(open("${JSON}"))
failed = 0
for pr in sorted(prs, key=lambda p: p["number"]):
    num = pr["number"]
    line = (
        f"#{num} {pr['headRefName']}: "
        f"mergeable={pr.get('mergeable','UNKNOWN')} "
        f"mergeState={pr.get('mergeStateStatus','UNKNOWN')}"
    )
    print(line)
    if not apply:
        continue
    result = subprocess.run(
        ["gh", "pr", "edit", str(num), "--base", target],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        failed += 1
        err = (result.stderr or result.stdout or "unknown error").strip()
        print(f"  retarget failed: {err}", file=sys.stderr)
    else:
        print("  retarget ok")
sys.exit(1 if failed and apply else 0)
PY
