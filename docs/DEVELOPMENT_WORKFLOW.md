# Development Workflow

This workflow applies to human contributors and AI coding agents. Persistent agent rules are in [AGENTS.md](../AGENTS.md).

## Branch Naming

Create branches from an updated default branch. Do not commit directly to `main`.

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
- Do not rewrite published history or force-push to `main`.
- Prefer several logical commits over one mixed commit when the work has distinct purposes.

## Pull Request Workflow

1. Inspect the current branch and working tree before editing.
2. Create a feature branch if the default branch is clean.
3. Make the smallest change that satisfies the request.
4. Run local validation.
5. Open a pull request against `main`. Do not push directly to the default branch.
6. Request review. Address findings without expanding scope.
7. Merge only when CI is green and the Definition of Done is met.

Pull requests should describe:

- The problem or outcome
- Architectural tradeoffs, if any
- How the change was verified
- Known gaps

## Testing Expectations

- Add or update tests when behavior changes.
- Prefer unit tests for domain and application rules.
- Use `tests/integration/` for adapter and API contracts once those exist.
- Use `tests/e2e/` for user-visible flows once a frontend exists.
- Use synthetic Wasatch Business Systems data only.
- Do not fabricate test results. If a suite cannot be run, say so.

Current foundation work has no application test suite. Repository validation is the required check until application code exists.

```bash
ruff format --check .
ruff check .
python3 scripts/validate_repo.py
```

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
