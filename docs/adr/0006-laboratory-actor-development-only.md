# ADR 0006: Laboratory actor adapter is development-only

- Status: Accepted
- Date: 2026-11-04

## Context

The Wasatch API exposes synthetic customer and employee records. Callers in local development present an employee business id in the `X-Laboratory-Actor` header. `emp_0001` is an approver. `emp_0004` is not. There is no password.

That header is an identity simulation for the laboratory. Anyone who can send `emp_0001` is treated as the synthetic general manager. It is not authentication, and it must not become the production authenticator by being left on when `APP_ENV` changes.

No production environment is deployed. No password system and no identity provider exist in this repository. Business reads still have to require an actor, and writes stay denied until a later command explicitly allows one.

## Decision

Restrict `LocalEmployeeAuthenticator` to local synthetic development. The process may start only when `APP_ENV` is `local`, `development`, or `test`.

`APP_ENV=production` and `APP_ENV=prod` are production configurations. `create_app` raises `UnsafeProductionConfiguration` before it returns an application, and constructing the adapter raises the same exception before it loads an employee. The header does not activate.

Any other environment, including `staging`, also fails startup. The adapter stays inactive there, and the API must not boot with unauthenticated business reads. No second authenticator is configured.

Role rules stay in the workforce application service. An active synthetic employee may read. Every write is denied. An approval decision requires `is_approver` on the actor's role. The decision command is not part of this change.

The future production authentication boundary is a different implementation of `EmployeeAuthenticator`. That adapter is not this header. It is not implemented. It will not be a password table in this service, and this change does not add an identity-provider client. Until that adapter exists, production configuration does not start.

Wasatch Business Systems records remain synthetic.

## Alternatives Considered

- **Accept `X-Laboratory-Actor` whenever the process is running.** Rejected. A production configuration would treat a spoofable employee id as the general manager.
- **Disable the header in production and leave `/api/v1` open.** Rejected. Business reads stay authenticated.
- **Add passwords or a local user table.** Rejected. The laboratory does not need a password system, and a password store would be a second identity design.
- **Integrate an identity provider now.** Rejected. No production identity provider is in scope, and none is configured.

## Consequences

- `uvicorn wasatch_api.main:app` with `APP_ENV=production` or `APP_ENV=prod` exits during startup and does not serve traffic.
- Local Compose keeps `APP_ENV` at `local`. The header, the read requirement, and the write denial are unchanged for that environment.
- A later approval command calls the workforce application service. It still has to append decision history itself. This decision does not record an approval.
- Replacing the header in production requires a new adapter and a new decision. Turning this adapter on is not that replacement.
