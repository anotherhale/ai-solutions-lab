# ADR 0010: Autonomous integration on `ai-dev` and merge safety

- Status: Accepted
- Date: 2026-11-06

## Context

The coordinator's `data/coordinator/backlog.yaml` declared `integration_branch: develop`, and
[../architecture/AGENT_OPERATING_MODEL.md](../architecture/AGENT_OPERATING_MODEL.md) treated
`develop` as the integration branch. Autonomous runs open pull requests and attempt GraphQL
squash auto-merge.

Two problems follow from routing autonomy through `develop`:

1. **`develop` was also the protected human integration branch.** Mixing autonomous and human
   integration on one branch made it impossible to reason about what was machine-produced.
2. **The auto-merge gate was too weak.** The GitHub client only refused a request when the pull
   request was already merged. It did not check the base branch, so a green pull request opened
   against `main` could receive an auto-merge request, and it could request auto-merge before any
   check had reported. `main` is meant to be human-controlled.

The coordinator also had no notion of which pull requests were safe to integrate automatically,
and no way to distinguish "PR closed without merge" from "PR merged" when a PR left the open list.

## Decision

1. **`ai-dev` is the exclusive autonomous integration branch.** Autonomous runs open pull requests
   against `ai-dev` and auto-merge only into `ai-dev`.
2. **`main` is the stable release branch, exclusively human-controlled.** No autonomous process
   opens, requests auto-merge for, or merges a pull request into `main`.
3. **`develop` remains protected but is no longer the autonomous integration branch.**
4. **The auto-merge gate is enforced in the client, not only the caller.** `enable_squash_auto_merge`
   refuses a request when:
   - the pull request is merged or closed;
   - the base branch is not `ai-dev`;
   - the status check rollup is empty (unknown), pending, or failed.
5. **Status checks are classified, not assumed.** `CheckRun` (GitHub Actions) and `StatusContext`
   (legacy commit statuses) are both evaluated. Passing conclusions are `SUCCESS`, `NEUTRAL`, and
   `SKIPPED`; `PENDING`, `QUEUED`, `IN_PROGRESS`, `WAITING`, and `EXPECTED` are pending; anything
   else is failed. An empty rollup is `none` and is never treated as green.
6. **A pull request that leaves the open list is reconciled by fetching it directly.** Merged
   pull requests are terminal; closed-without-merge pull requests block the task for human
   attention instead of being recorded as merged.

## Alternatives Considered

- **Keep `develop` as the autonomous integration branch.** Rejected: it couples machine merges to
  the branch humans integrate through and removes the ability to isolate autonomous output.
- **Auto-merge into `main` behind a green CI gate.** Rejected: a green CI status does not authorize
  a machine merge to the release branch. `main` stays human-controlled.
- **Enforce the base-branch and check gates only in the coordinator tick.** Rejected: the client is
  the last line of defence. Guarding both the caller and the client means a future caller that
  forgets the check cannot merge into `main`.
- **Treat an empty check rollup as green.** Rejected: no checks means the state is unknown, not
  passing. Auto-merge must wait.

## Consequences

- The coordinator's merge path is narrower and safer: only green pull requests targeting `ai-dev`
  receive an auto-merge request.
- `data/coordinator/backlog.yaml` must declare `integration_branch: ai-dev`, and feature branches
  must be cut from `ai-dev` and opened against it.
- `main` promotion becomes an explicit human step (a release pull request or merge performed by a
  human), which is the intended control point.
- Tasks whose pull requests are closed without merge now surface as `blocked` rather than silently
  `merged`, so a human sees them.
- This ADR does not change the strict GitHub merge policy: agents never use `gh pr merge`, the REST
  merge endpoint, or the GraphQL `mergePullRequest` mutation. Auto-merge is still requested only
  through GraphQL `enablePullRequestAutoMerge`.
