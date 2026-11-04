# Secret management

No cloud deployment exists. Managed secrets apply only after a cloud deployment exists. That deployment does not exist.

## Local laboratory

Local secrets stay in an uncommitted `.env`. Copy `.env.example` and replace placeholders there. `.env` is gitignored. `.env.example` keeps empty values and obvious placeholders such as `replace-me`.

The database password, `OPENAI_API_KEY`, and any future collector credential belong in that uncommitted file or in the process environment. They do not belong in source, fixtures, ADRs, or these notes.

`OTEL_EXPORTER_OTLP_ENDPOINT` is a URL, not a secret. Leave it unset or blank unless a collector is actually running outside this repository. A blank value does not export spans and does not open a socket. Collector authentication headers (`OTEL_EXPORTER_OTLP_HEADERS`) and resource attributes (`OTEL_RESOURCE_ATTRIBUTES`) stay in the uncommitted environment. Do not put secrets in either one. Do not set `OTEL_INSTRUMENTATION_HTTP_CAPTURE_HEADERS_SERVER_REQUEST`. The host instrumentation does not copy request headers onto spans. `X-Laboratory-Actor` is a development identity simulation and stays out of spans.

Structured logs from `APP_LOG_LEVEL` record actor, action, subject, and outcome. Message bodies and secrets stay out of those logs.

## GitHub Actions

GitHub Actions stays credential-free. `.github/workflows/validate.yml` checks formatting, lint, repository conventions, domain fixtures, and the Wasatch API tests against PostgreSQL. It does not receive a cloud credential, an OpenAI key, a collector endpoint, or a Terraform token. The CI database password is the local test password already used by that workflow. It is not an Azure secret.

## After a cloud deployment exists

When a cloud deployment exists, its secrets move to a managed secret store. The repository and container images do not carry them. Terraform for that environment would read the store from the workspace, not from a committed subscription id, tenant id, or client secret.

`infrastructure/terraform/` has no workspace and no configuration. Do not add a backend, a subscription id, a tenant id, or a credential there until a workspace is ready. Do not describe Compose or these notes as that deployment.
