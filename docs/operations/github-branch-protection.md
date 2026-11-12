# GitHub branch protection for the integration branches

This repository treats **`ai-dev`** as the **autonomous integration branch**: laboratory agents open pull requests against `ai-dev`, and the coordinator auto-merges only green pull requests whose base is `ai-dev` ([ADR 0010](../adr/0010-autonomous-integration-branch.md)). **`develop`** remains a protected branch and is no longer the autonomous integration branch; **`main`** is the stable release branch and stays human-controlled. Agents must not merge their own pull requests. Merge method on `ai-dev` is squash, only after independent review and green CI ([AGENT_OPERATING_MODEL.md](../architecture/AGENT_OPERATING_MODEL.md)).

The ruleset below applies to **`ai-dev`** (required) and should also be applied to **`develop`** and **`main`** for defense in depth.

## Why merges can land while checks are still queued

GitHub allows a merge when **no rule blocks it**. If `develop` has no required status checks (and no ruleset enforces them), a user or integration with **`contents: write`** can merge a pull request while the **Repository Validation** workflow is still `queued` or `in_progress`. That workflow (`.github/workflows/validate.yml`) runs on pull requests and on pushes to `develop` and `ai-dev`, but optional checks do not gate merges by themselves.

Observed on 2026-11-04 (Mountain Time):

- Pull requests [#26](https://github.com/anotherhale/ai-solutions-lab/pull/26) and [#27](https://github.com/anotherhale/ai-solutions-lab/pull/27) merged to `develop` while push workflows for commits `e25fb91` and `13836b8` remained **`queued`** (all five jobs waiting for runners).
- Earlier push to `develop` at `00b0fd6` (pull request #24) **completed successfully**, so the workflow definition was valid; the later runs were backlog or capacity, not a missing workflow.

Cloud-agent credentials on this repository can **list** workflow runs but cannot read branch protection (HTTP 403) or manage rulesets (empty list with the same token). **Repository administrators** must apply the settings below in the GitHub UI or with a token that has admin access.

## Recommended ruleset for `ai-dev`

Create a **branch ruleset** (Settings → Rules → Rulesets) targeting **`ai-dev`** (repeat for `develop` and `main`):

| Rule | Setting |
|---|---|
| Restrict deletions | On |
| Block force pushes | On |
| Require a pull request before merging | On (no direct pushes) |
| Required status checks | All jobs from **Repository Validation** (see below) |
| Require branches to be up to date before merging | On |
| Require linear history | Optional; squash merge already produces linear history on the branch tip |

### Required status check names

Use the **job names** exactly as GitHub reports them (these match `.github/workflows/validate.yml`):

1. `Format, lint, and conventions`
2. `Wasatch review frontend`
3. `Compose API smoke`
4. `Wasatch API tests`
5. `Review workbench browser tests`

Alternatively, require the check suite **`Repository Validation`** if your GitHub plan exposes the workflow as a single required check; prefer naming all five jobs so a disabled job cannot satisfy the rule silently.

### Pull request expectations (process, not GitHub config)

- Enable **auto-merge (squash)** only after review approval and required checks are green.
- Do not use admin bypass except for documented emergencies.
- Agents must not call merge APIs until the pull request shows success for every required job.
- The coordinator additionally refuses to arm auto-merge while a pull request is a **draft**, has
  **unresolved review threads**, or is **not mergeable** (conflicts / `DIRTY`). Resolve
  review threads and conflicts rather than re-requesting; the next coordinator tick re-evaluates and
  arms auto-merge automatically once they clear. See
  [COORDINATOR_CONTINUITY.md](COORDINATOR_CONTINUITY.md#merge-safety).
- A conflicted pull request cannot be auto-merged at all, which is why implementation agents must
  **not** hand-edit the tracked `data/coordinator/backlog.yaml`; the coordinator records merges there
  itself. See [COORDINATOR_CONTINUITY.md](COORDINATOR_CONTINUITY.md#backlog-catalog-ownership).

## What stays in the repository

Workflows, scripts, and documentation cannot replace admin-configured rulesets. This file records the intended gate so humans and agents align behavior even before GitHub enforces it.

Related: [DEVELOPMENT_WORKFLOW.md](../DEVELOPMENT_WORKFLOW.md), [AGENT_OPERATING_MODEL.md](../architecture/AGENT_OPERATING_MODEL.md).
