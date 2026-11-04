# ADR 0007: Starlette security advisories and remediation plan

- Status: Proposed
- Date: 2026-11-04

## Context

Wasatch API depends on FastAPI, which depends on Starlette. The laboratory pins FastAPI in `services/wasatch-api/pyproject.toml` as `fastapi>=0.115.6,<0.122`. That range resolves **Starlette 0.50.0** (FastAPI 0.121.3 declares `starlette>=0.40.0,<0.51.0`).

CI runs `scripts/audit_wasatch_dependencies.sh`, which installs `pip-audit==2.9.0` and audits the editable Wasatch API environment. Without temporary ignores, `pip-audit` reports **five PYSEC advisories** on Starlette 0.50.0 (and the same IDs on 0.52.1). Published fix versions point to the **Starlette 1.x** line (for example `1.0.1`, `1.1.0`, `1.3.0`, `1.3.1`). There are no fix releases on the 0.5x line in the advisory data CI uses.

The audit script currently passes only by **ignoring those five Starlette IDs**, with a comment that the ignore list stays until an upgrade path is recorded. This ADR records that path and explicitly rejects blind dependency bumps or open-ended suppressions.

Additional constraints:

- **`anyio>=4.8.0,<4.15`** is pinned because Starlette’s `TestClient` still imports `anyio.abc.BlockingPortal` until a released Starlette includes the `from_thread` alias (see pyproject comment and existing pytest warning).
- **OpenTelemetry** packages pin FastAPI instrumentation (`opentelemetry-instrumentation-fastapi==0.66b2`); a FastAPI major-line jump must be checked against instrumentation compatibility.
- The API uses FastAPI **`APIRouter(..., on_startup=...)`** in at least one module; Starlette 1.x / current FastAPI routing removed that keyword, so a naïve Starlette-only bump breaks import.

Spike results (2026-11-04, synthetic database, full pytest with PostgreSQL):

| Stack | Starlette advisories (pip-audit) | Pytest |
|---|---|---|
| Pinned lab stack (FastAPI 0.121.3, Starlette 0.50.0) | Five PYSEC IDs (ignored in CI script) | 195 passed (local) |
| Forced Starlette 1.3.1 on FastAPI 0.121.3 | None on Starlette | **Import failure** (`APIRouter` unexpected `on_startup`) |
| FastAPI 0.162.0 + Starlette 1.3.1 (manual install, not editable pin) | None on Starlette | Not fully validated against editable pin; resolver conflict with current `fastapi<0.122` |

FastAPI **0.162.0** metadata allows `starlette>=0.46.0` without an upper bound, so a supported laboratory path is to **raise the FastAPI upper bound**, **pin Starlette to a fixed 1.x patch** (for example `>=1.3.1`), and **remove router `on_startup` usage** in favor of application lifespan hooks.

## Decision

1. **Do not** merge a blind FastAPI or Starlette version bump without the validation steps in the remediation plan below.
2. **Keep** the five Starlette PYSEC ignores in `scripts/audit_wasatch_dependencies.sh` **only until** a follow-up change implements the plan and removes them; the ignore list must stay synchronized with this ADR (no additional suppressed IDs without a new ADR section).
3. **Treat** Starlette advisory remediation as a bounded engineering task (backlog item **SEC-1**), not as part of unrelated feature work.
4. **Record** that pip vulnerabilities reported against the **bootstrap `pip` inside the audit virtualenv** are out of scope for application runtime; the script upgrades `pip` before audit. CI application runtime uses the version installed by `pip install` in the Wasatch API job.

## Alternatives considered

- **Bump Starlette within 0.5x only.** Rejected. `pip-audit` still reports the same five IDs on 0.52.1; fixes are on 1.x.
- **Permanently ignore Starlette in CI.** Rejected. Ignores are a temporary bridge; ADR 0007 and SEC-1 exist to remove them.
- **Replace FastAPI with another framework.** Rejected. ADR 0002 stands; the issue is transitive HTTP stack patching, not framework choice.
- **Immediate upgrade to FastAPI 0.162 + Starlette 1.3.1 in this change.** Rejected. Requires pyproject bound changes, router lifecycle refactors, anyio pin re-evaluation, OpenTelemetry smoke checks, and full CI green—explicitly deferred to SEC-1.

## Consequences

- Security posture: known Starlette CVE-class advisories remain on the pinned stack until SEC-1 completes; risk is documented and gated in CI with explicit ignores rather than silent acceptance.
- SEC-1 implementation must: widen FastAPI pin to a tested release (for example 0.162.x), pin Starlette `>=1.3.1`, migrate `on_startup` on routers to lifespan, re-run `pip-audit` without Starlette ignores, run full pytest and Playwright jobs, and update this ADR to **Accepted** when merged.
- Until SEC-1 lands, feature work must not add new `pip-audit --ignore-vuln` entries for Starlette or FastAPI.

## Related

- ADR 0002 (Python and FastAPI backend)
- `scripts/audit_wasatch_dependencies.sh`
- `docs/operations/github-branch-protection.md` (CI must pass before merge once rulesets are configured)
