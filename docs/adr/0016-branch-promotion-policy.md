# ADR 0016: Branch roles and deliberate promotion flow

- Status: Accepted
- Date: 2026-11-13

## Context

ADR 0010 and ADR 0014 made `ai-dev` the exclusive autonomous integration branch and stopped
`develop` from being the autonomous target. Those ADRs define where autonomous pull requests land,
but they do not define the promotion relationship between the three long-lived branches. In
practice the roles drifted:

- `ai-dev` and `develop` are both protected, both carry a `data/coordinator/backlog.yaml` catalog,
  and have **diverged** (`git rev-list --left-right --count develop...ai-dev` reported `18` then
  `21` on 2026-11-13). They are parallel lines, not a promotion chain.
- Some automation synced catalog state from `develop` into `ai-dev`, which is the wrong direction
  for an authoritative autonomous branch and silently mixed laboratory state into autonomous state.
- A pull request targeted `main` to pick up coordinator automation on the default branch, which
  bypasses the release process for the production branch.

The repository owner has approved an explicit policy for the three branches and their promotion
order. This ADR records it so agents and humans stop inferring the relationship from titles or from
whichever branch a script happened to name.

## Decision

1. **Branch roles.**
   - `ai-dev` — authoritative autonomous development and integration branch. Autonomous runs open
     and merge pull requests here.
   - `develop` — laboratory integration and acceptance branch. Human and laboratory work integrates
     here.
   - `main` — production branch. Exclusively human-controlled.
2. **Promotion is deliberate and validated, in one direction only:**
   `ai-dev → develop → main`.
   - Promotion from `ai-dev` to `develop` is a reviewed step, not an automatic one.
   - Promotion from `develop` to `main` is a reviewed release step.
3. **No automatic synchronization between long-lived branches.**
   - `develop` is never synchronized into `ai-dev`.
   - `ai-dev` is never automatically promoted into `develop`.
   - `develop` is never automatically promoted into `main`.
4. **The existing `ai-dev`/`develop` divergence is a separate, explicitly reviewed branch
   migration/promotion problem.** It must not be resolved by merging divergent histories as a side
   effect of unrelated work.
5. **No autonomous process opens or merges a pull request into `main`.** Enforced by the
   `assert_authorized_base_branch` guard, which only authorizes `ai-dev` for autonomous work.
6. **Coordinator catalog synchronization uses the authoritative branch.** Any catalog sync reads
   from the branch the coordinator integrates on (`ai-dev`), never from `develop`.

## Alternatives Considered

- **Keep two parallel integration branches with no defined promotion order.** Rejected: the
  divergence is already large, and without a documented direction every agent invents its own
  relationship, which is what produced cross-branch catalog sync and a `main`-targeting automation
  pull request.
- **Make `develop` the single integration branch again.** Rejected: ADR 0010 deliberately separated
  machine-produced integration (`ai-dev`) from human integration (`develop`) so autonomous output
  stays isolable.
- **Automatically fast-forward `develop` from `ai-dev`.** Rejected: `ai-dev` may carry
  coordinator-only state (schema at a newer Alembic head, autonomous tooling) that is not ready for
  laboratory acceptance. Promotion must be reviewed.
- **Reconcile the divergence now, in this change.** Rejected: the divergence involves a branch
  migration with its own review; bundling it into a documentation change would hide an irreversible
  history operation inside an unrelated PR.
- **Allow a one-off automation PR to `main`.** Rejected: `main` is human-controlled; automation
  reaches production only through a reviewed release promotion.

## Consequences

- The promotion path is explicit and one-directional, so no process needs to guess whether
  `develop` or `ai-dev` is "ahead".
- Cross-branch catalog synchronization from `develop` into `ai-dev` is a defect to be removed, not a
  feature.
- Autonomous work can never target `main`; the existing base-branch guard already enforces this for
  registration and auto-merge.
- The `ai-dev`/`develop` divergence remains open and is tracked as a separate, reviewed branch
  migration/promotion problem rather than being merged here.
- This ADR does not change the strict GitHub merge policy: agents still never use `gh pr merge`, the
  REST merge endpoint, or the GraphQL `mergePullRequest` mutation. Auto-merge is requested only
  through GraphQL `enablePullRequestAutoMerge`.

## Related

- [ADR 0010](0010-autonomous-integration-branch.md) — `ai-dev` as the autonomous integration branch
  and merge safety.
- [ADR 0014](0014-autonomous-integration-branch-consolidation.md) — one authoritative integration
  branch value and coordinator-owned backlog catalog.
