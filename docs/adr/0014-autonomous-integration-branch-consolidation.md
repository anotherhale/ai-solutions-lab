# ADR 0014: One authoritative autonomous integration branch and a coordinator-owned backlog catalog

- Status: Accepted
- Date: 2026-11-06

## Context

ADR 0010 made `ai-dev` the exclusive autonomous integration branch and `develop` a protected
human branch. The decision was implemented in parts of the coordinator, but the boundary leaked in
three places, and a separate failure made the queue fragile:

1. **The integration branch was hard-coded in more than one place.** The coordinator CLI, the
   worktree manager, the child-agent brief, and the automation entrypoint script each named a
   branch independently. The entrypoint script still told implementation agents to target the old
   branch, so agents opened pull requests the coordinator would refuse to auto-merge — a stale
   contradiction between what the documentation said and what the automation did.
2. **The auto-merge gate was incomplete and duplicated.** The client checked the base branch and
   the check rollup. The coordinator re-derived "is this eligible" separately. Nothing checked
   whether a pull request was a **draft**, had **unresolved review threads**, or was **not
   mergeable** (a conflict). Two implementations of one rule drift, and a conflicted pull request
   was attempted as if it could merge.
3. **`data/coordinator/backlog.yaml` was edited by many agents.** The catalog is a tracked file.
   Every implementation agent that recorded its own task's merge edited it, so each subsequent pull
   request conflicted on the file. A conflicted pull request cannot be auto-merged, so one merge
   conflict stalled the queue until a human resolved it. No code wrote the catalog; the coordinator
   only updated runtime state in PostgreSQL, so agents believed they had to edit the file.

## Decision

1. **One authoritative integration-branch value.** `development_ops.integration.py` defines
   `AUTONOMOUS_INTEGRATION_BRANCH` (`ai-dev`) and the guards around it. The worktree manager, the
   child-agent brief, the pull-request registration guard, the auto-merge gate, and the CLI all
   import it. No shell script or second module names the branch.
2. **Fail fast on an unauthorized base.** `assert_authorized_base_branch` raises
   `UnauthorizedBaseBranchError` for any branch other than `ai-dev`, and
   `CoordinatorEngine.register_pull_request_opened` calls it before recording a pull request.
   A base of `main`, `develop`, or an unknown branch is refused rather than recorded as work the
   coordinator can never merge.
3. **One auto-merge gate, expressed once.** `PullRequestState.auto_merge_blockers()` returns every
   reason a pull request is not eligible — base branch, checks, draft state, unresolved review
   threads, and merge conflicts. Both the client (`enable_squash_auto_merge` refuses before any
   mutation) and the coordinator (`_maybe_attempt_auto_merge` records the reasons) evaluate the
   same method. Unresolved threads are read through the GraphQL `reviewThreads` connection because
   `gh pr view` does not expose them; the lookup fails closed.
4. **The coordinator is the only sanctioned writer of the backlog catalog.** After GitHub confirms
   a merge, the coordinator marks the task merged in `data/coordinator/backlog.yaml` through
   `development_ops.catalog.YamlBacklogCatalogWriter`. The writer is line-preserving (comments and
   formatting survive), atomic (temp file + `os.replace`), `flock`-serialized, and idempotent.
   Implementation agents do not edit the catalog.
5. **The delegation brief is generated, not hand-written.** The CLI emits the implementation
   instruction (including the base branch) from the authoritative value, and the automation
   entrypoint prints the CLI output instead of a hard-coded string.

## Alternatives Considered

- **Keep the branch value in each module and rely on review to keep them in sync.** Rejected: the
  entrypoint script had already drifted, and the failure mode (agents targeting a branch the
  coordinator refuses) is silent until a pull request stalls.
- **Gate auto-merge only in the coordinator.** Rejected for the same reason ADR 0010 guards the
  client: the client is the last line of defence, and a future caller that forgets the check must
  still be unable to mutate an ineligible pull request.
- **Treat a draft or a conflicted pull request as "eligible, let GitHub sort it out."** Rejected:
  GitHub refuses the merge, the request errors, and the operator sees a confusing failure instead of
  the actual reason. Recording the reason is cheaper than discovering it.
- **Rewrite the catalog with a YAML library.** Rejected: re-serializing the whole file churns
  comments and ordering and conflicts with every other branch — the opposite of the goal. A
  targeted, line-preserving edit touches one task block.
- **Keep the catalog human-only and never write it from code.** Rejected: it leaves the original
  failure in place. Agents must not edit it, but *someone* must, and the coordinator is the only
  actor that knows a merge was verified.
- **A separate `backlog` database table as the only source of truth.** Deferred: the catalog is a
  deliberate, reviewable, human-readable mirror. PostgreSQL already holds the authoritative runtime
  state; the catalog is reconciled from it.

## Consequences

- The integration branch can no longer drift between the documentation, the worktree base, the
  child brief, the pull-request guard, the auto-merge gate, and the automation entrypoint.
- A pull request on an unauthorized base is refused at registration, so the coordinator never
  tracks work it cannot merge.
- Auto-merge is attempted only for green, non-draft, conflict-free pull requests targeting `ai-dev`
  with no unresolved review threads. Each distinct blocking reason is recorded once, so a blocked
  pull request does not flood the activity log, and the next tick re-arms auto-merge once the
  condition clears.
- The tracked catalog no longer becomes a merge-conflict magnet. The coordinator writes it through
  `coordinator tick --update-catalog` (opt-in); a write failure is a note, not a fatal error,
  because runtime state is already durable and the next tick retries.
- This ADR does not change the strict GitHub merge policy: agents still never use `gh pr merge`,
  the REST merge endpoint, or the GraphQL `mergePullRequest` mutation. Auto-merge is requested only
  through GraphQL `enablePullRequestAutoMerge`.
- Follow-up: promotion from `ai-dev` to `main` remains an explicit human step. The `develop`
  branch remains protected and is no longer an autonomous target.
