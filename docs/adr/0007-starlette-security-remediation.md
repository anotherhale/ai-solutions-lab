# ADR 0007: Starlette security advisories and remediation plan

- Status: Accepted
- Date: 2026-11-04

## Context

Wasatch API depends on FastAPI, which depends on Starlette. Before SEC-1, the laboratory pinned FastAPI in `services/wasatch-api/pyproject.toml` as `fastapi>=0.115.6,<0.122`. That range resolved **Starlette 0.50.0** (FastAPI 0.121.3 declares `starlette>=0.40.0,<0.51.0`).

CI runs `scripts/audit_wasatch_dependencies.sh`, which installs `pip-audit==2.9.0` and audits the editable Wasatch API environment. Without temporary ignores, `pip-audit` reports **five PYSEC advisories** on Starlette 0.50.0 (and the same IDs on 0.52.1). Published fix versions point to the **Starlette 1.x** line (for example `1.0.1`, `1.1.0`, `1.3.0`, `1.3.1`). There are no fix releases on the 0.5x line in the advisory data CI uses.

Before SEC-1, the audit script passed only by **ignoring those five Starlette IDs**. This ADR records the upgrade path and explicitly rejects blind dependency bumps or open-ended suppressions. SEC-1 implemented that path and removed the ignores.

Additional constraints at proposal time:

- **`anyio>=4.8.0,<4.15`** was pinned because Starlette 0.50 `TestClient` imported `anyio.abc.BlockingPortal`. SEC-1 widened that bound after Starlette 1.10 switched to `anyio.from_thread.BlockingPortal`. See Implementation.
- **OpenTelemetry** packages pin FastAPI instrumentation (`opentelemetry-instrumentation-fastapi==0.66b2`). A FastAPI jump had to be checked against that instrumentation. SEC-1 kept the pin.
- Application route modules do not pass `on_startup` to `APIRouter`. **FastAPI 0.121.3** still forwarded lifecycle kwargs into Starlette’s `Router` during import. **Starlette 1.3.1** rejects those kwargs, so pairing FastAPI 0.121 with Starlette 1.x failed at import time (`TypeError: Router.__init__() got an unexpected keyword argument 'on_startup'`). FastAPI 0.162 keeps those handlers on its own router.

Spike results (2026-11-04, synthetic database, full pytest with PostgreSQL):

| Stack | Starlette advisories (pip-audit) | Pytest |
|---|---|---|
| Pinned lab stack (FastAPI 0.121.3, Starlette 0.50.0) | Five PYSEC IDs (ignored in CI script) | 195 passed (local) |
| Forced Starlette 1.3.1 on FastAPI 0.121.3 | None on Starlette | **Import failure** (FastAPI 0.121 `APIRouter` incompatible with Starlette 1.x `Router`) |
| FastAPI 0.162.0 + Starlette 1.3.1 (manual install, not editable pin) | None on Starlette | Not fully validated against editable pin; resolver conflict with current `fastapi<0.122` |

FastAPI **0.162.0** metadata allows `starlette>=0.46.0` without an upper bound, so a supported laboratory path is to **raise the FastAPI upper bound**, **pin Starlette to a fixed 1.x patch** (for example `>=1.3.1`), and **remove router `on_startup` usage** in favor of application lifespan hooks.

## Decision

1. **Do not** merge a FastAPI or Starlette version bump that has not passed full pytest and a clean `pip-audit`. The validated bump is in Implementation.
2. **Remove** the five Starlette PYSEC ignores once the upgraded stack is audited clean. Do not add `--ignore-vuln` entries for Starlette or FastAPI without a new ADR section.
3. **Treat** Starlette advisory remediation as a bounded engineering task (backlog item **SEC-1**), not as part of unrelated feature work. SEC-1 is that task.
4. **Record** that pip vulnerabilities reported against the **bootstrap `pip` inside the audit virtualenv** are out of scope for application runtime; the script upgrades `pip` before audit. CI application runtime uses the version installed by `pip install` in the Wasatch API job.

## Alternatives considered

- **Bump Starlette within 0.5x only.** Rejected. `pip-audit` still reports the same five IDs on 0.52.1; fixes are on 1.x.
- **Permanently ignore Starlette in CI.** Rejected. Ignores are a temporary bridge; ADR 0007 and SEC-1 exist to remove them.
- **Replace FastAPI with another framework.** Rejected. ADR 0002 stands; the issue is transitive HTTP stack patching, not framework choice.
- **Upgrade inside the proposal change, before an editable-pin pytest and a clean audit.** Rejected at proposal time and deferred to SEC-1. SEC-1 then installed FastAPI 0.162.0 with Starlette 1.10.0, not only the 1.3.1 spike, after those checks.

## Implementation

SEC-1 accepts this ADR. `services/wasatch-api/pyproject.toml` now pins:

- `fastapi>=0.162.0,<0.163` (resolved **0.162.0**)
- `starlette>=1.10.0,<1.11` (resolved **1.10.0**)

FastAPI 0.162 allows `starlette>=0.46.0` with no upper bound, so Starlette is a direct dependency. The spike's minimum patched release was 1.3.1. **1.10.0** is the 1.x release this change installed and audited. `pip-audit` reports no known vulnerabilities, and the script no longer passes `--ignore-vuln`.

Starlette 1.10 `TestClient` uses `anyio.from_thread.BlockingPortal`. The anyio pin is now `anyio>=4.8.0,<5`, matching Starlette's `<5` bound. The previous `<4.15` cap applied only while Starlette 0.50 imported `anyio.abc.BlockingPortal`.

`create_app` does not pass `on_startup` or `on_shutdown`. FastAPI 0.162 keeps those handlers on its own router instead of forwarding them into Starlette 1.x `Router`. The default lifespan still starts: `TestClient` enters it and `GET /health` returns `status` `ok` and `service` `wasatch-api`. OpenTelemetry stays `opentelemetry-instrumentation-fastapi==0.66b2`. With the exporter unset, startup still does not construct an exporter.

Laboratory actor storage writes `scope["state"]` when that value is a dict, and sets the attribute when Starlette has already placed a `State` object there. `request.state.laboratory_actor` remains visible to `require_laboratory_actor`.

## Consequences

- The five Starlette PYSEC IDs are not ignored. A future advisory fails `scripts/audit_wasatch_dependencies.sh` until a new ADR records the response.
- Feature work must not add `pip-audit --ignore-vuln` entries for Starlette or FastAPI.
- Uvicorn stays on the existing `>=0.32.1,<0.38` bound. This change did not upgrade it.

## Related

- ADR 0002 (Python and FastAPI backend)
- `scripts/audit_wasatch_dependencies.sh`
- `docs/operations/github-branch-protection.md` (CI must pass before merge once rulesets are configured)
