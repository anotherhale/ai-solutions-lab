# Development Workflow

This workflow applies to human contributors and AI coding agents. Persistent agent rules are in [AGENTS.md](../AGENTS.md).

## Branch Naming

Create branches from an updated `ai-dev`. `ai-dev` is the autonomous integration branch. `main` is the production branch. `develop` is a protected human branch and is no longer the integration branch. Do not commit directly to `ai-dev`, `develop`, or `main`. See [ADR 0010](adr/0010-autonomous-integration-branch.md).

| Prefix | Use |
|---|---|
| `feature/` | New capability or documentation set that adds behavior |
| `fix/` | Defect repair |
| `docs/` | Documentation-only changes |
| `chore/` | Tooling, CI, or repository maintenance |
| `adr/` | A focused architecture decision |

Examples: `feature/project-foundation`, `fix/ci-ruff-paths`, `docs/wasatch-profile`.

Keep branches short-lived and limited to one intent.

## Commit Conventions

Use [Conventional Commits](https://www.conventionalcommits.org/):

```text
<type>(<optional scope>): <imperative summary>
```

Common types: `feat`, `fix`, `docs`, `chore`, `test`, `refactor`, `ci`.

Guidelines:

- Explain why the change exists, not only what files moved.
- Keep secrets out of history. Never commit `.env` or credentials.
- Do not rewrite published history. Do not force-push `ai-dev`, `develop`, or `main`.
- Prefer several logical commits over one mixed commit when the work has distinct purposes.

## Pull Request Workflow

1. Inspect the current branch and working tree before editing.
2. Create a feature branch from `ai-dev` if the working tree is clean.
3. Make the smallest change that satisfies the request.
4. Run local validation.
5. Open a pull request against `ai-dev`. Do not push directly to `ai-dev`, `develop`, or `main`. Do not force-push any of them.
6. Request review. Address findings without expanding scope.
7. Merge only when CI is green and the Definition of Done is met. GitHub does not enforce that by default; see [operations/github-branch-protection.md](operations/github-branch-protection.md) for recommended rulesets on `ai-dev`.

Pull requests should describe:

- The problem or outcome
- Architectural tradeoffs, if any
- How the change was verified
- Known gaps

## Testing Expectations

- Add or update tests when behavior changes.
- Prefer unit tests for domain and application rules.
- Use `services/wasatch-api/tests/` for unit, integration, and API tests of the first host.
- Review-screen unit checks live in `apps/wasatch-review` and do not need a database or a provider key. GitHub Actions runs `npm test`, `npm run typecheck`, and `npm run build` in that app.
- Browser workflows live in `tests/e2e/` (Playwright). They need PostgreSQL and the host-run API; CI runs them in the **Review workbench browser tests** job.
- Use synthetic Wasatch Business Systems data only.
- Do not fabricate test results. If a suite cannot be run, say so.

Repository, fixture, and application tests are required for this slice.

```bash
ruff format --check .
ruff check .
python3 scripts/validate_repo.py
python3 scripts/validate_wasatch_domain.py
cd services/wasatch-api && pytest
```

GitHub Actions runs that pytest command against PostgreSQL with pgvector. The session applies Alembic migrations and loads `data/fixtures/valid/`. Integration and API tests are required on that job: a skip fails the run. Locally, pytest still skips those tests when PostgreSQL is not running.

Coordinator tests that need the development-ops schema run against the disposable
`wasatch_development_ops_test` database, never the operational
`wasatch_development_ops` database, even when `DEVELOPMENT_OPS_DATABASE_URL`
points at the operational database. Destructive helpers refuse operational and
maintenance database names before running any SQL. See
[ADR 0011](../adr/0011-test-database-isolation.md).

## First application (local)

1. Run `scripts/bootstrap_laboratory.sh` once, or manually: copy `.env.example` to `.env`, start PostgreSQL, create the API venv, and `npm ci` in `apps/wasatch-review`.
2. Start the API with `scripts/wasatch_dev.sh` (reload) or `scripts/run_wasatch_api_host.sh` (CI-style, no reload).
3. Open http://localhost:8000/docs.
4. From `apps/wasatch-review`, run `npm run dev` and open http://127.0.0.1:5173. The dev server proxies `/api` to port 8000.
5. Optional: `cd tests/e2e && npm test` after `npx playwright install chromium`.
6. Optional: `scripts/smoke_compose.sh` verifies the Compose API image and startup path.

Do not run `docker compose down -v` as part of normal shutdown; that destroys the named volume.

## Definition of Done

A change is done when all of the following are true:

- The requested behavior or documentation is present and internally consistent.
- Related ADRs, architecture, security, or roadmap documents are updated if decisions changed.
- No unrelated files were modified.
- Secrets were not introduced.
- Formatting and linting pass.
- Tests that exist were run, or the author reported why they were not.
- Incomplete work is listed explicitly.

## Architecture Decision Records

Significant choices are recorded in `docs/adr/` using the process in [adr/README.md](adr/README.md).

Write or update an ADR when the change:

- Selects or replaces a technology in the stack
- Changes deployment shape, module boundaries, or data ownership
- Adds an irreversible operational constraint
- Rejects a previously attractive option, such as Nx or microservices

Mark decisions `Proposed` until implementation or validation exists. Do not treat a written ADR as proof that the software is running.

## AI-Assisted Development Practices

- Agents must read `AGENTS.md`, this document, and the relevant ADRs before changing architecture.
- Agents must inspect existing files and preserve useful content.
- Agents must not add dependencies or infrastructure without explaining the immediate need.
- Agents must explain tradeoffs when more than one option is reasonable.
- Agents must not claim that CI passed, tests passed, or a cloud environment exists unless that was verified in the session.
- Humans remain responsible for approving consequential product and security decisions.
