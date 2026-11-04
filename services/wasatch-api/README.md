# Wasatch API

FastAPI service for synthetic Wasatch Business Systems data.

This is the modular-monolith slice. Synthetic procedure-page embeddings live in PostgreSQL. The React screen is `apps/wasatch-review`. Reads under `/api/v1` require a laboratory actor. An active employee may draft a suggested reply. An approver may approve or reject a pending customer message, and may accept or reject a document extraction that is awaiting review. A dispatcher may open a follow-up visit from an approved customer message and then confirm or cancel it. The visit stays unscheduled until that decision. Neither customer-message command sends the message. The extraction decision does not post a payment or change an invoice. The follow-up command does not either, and it does not assign a technician. Other writes are denied. The model provider defaults to `AI_PROVIDER=fake` and does not need an API key. The procedure vectors come from that fake port. They are not a trusted model.

`GET /api/v1/support-tickets/{ticket_id}/retrieval` reads persisted ticket, message, interaction, and work-order text for that ticket's customer, then matches synthetic procedure pages under `data/documents/procedures/`. When `procedure_page_embeddings` has been filled, the procedure match may use those stored vectors. The history query stays. The route does not call a network model.

## Prerequisites

- Python 3.12+
- Docker and Docker Compose
- Repository `.env` copied from `.env.example`

## Local startup

From the repository root:

```bash
cp .env.example .env
docker compose up -d postgres   # or: docker-compose up -d postgres
python3.12 -m venv services/wasatch-api/.venv
. services/wasatch-api/.venv/bin/activate
pip install -e 'services/wasatch-api[dev]'
cd services/wasatch-api
alembic upgrade head
wasatch-api seed
uvicorn wasatch_api.main:app --reload --host 0.0.0.0 --port 8000
```

Or run `scripts/wasatch_dev.sh` after the virtualenv exists.

Compose can also start the API container:

```bash
docker compose up --build
```

That path runs migrations and seed, then serves `http://localhost:8000`. Named volume `wasatch_pg_data` is not removed on `docker compose down`.

## Checks

```bash
ruff format --check .
ruff check .
pytest
```

OpenAPI: http://localhost:8000/docs

## Laboratory actor

Send the synthetic employee business id in `X-Laboratory-Actor`. That header is a local development identity simulation, not authentication. The adapter looks the employee up and reads `is_approver` from the employee's role. No password is stored, and there is no identity provider. `emp_0001` (general manager) is an approver. `emp_0004` (dispatcher) is not. Only `active` employees authenticate. Health checks do not use the header.

The adapter runs only when `APP_ENV` is `local`, `development`, or `test`. `APP_ENV=production` and `APP_ENV=prod` raise `UnsafeProductionConfiguration` during startup and do not serve. Other environments fail closed the same way. The future production authenticator is a different adapter. It is not this header.

```bash
curl -s -H 'X-Laboratory-Actor: emp_0001' \
  http://localhost:8000/api/v1/support-tickets/tkt_0007
```

An anonymous call to `/api/v1` returns 401. An authenticated write other than the suggested-reply draft, the customer-message decision, the extraction review, or the dispatcher follow-up command returns 403. `APP_LOG_LEVEL` controls structured logs of the actor, action, subject, and outcome. Message bodies and secrets are not logged.

## Observability

`create_app` records OpenTelemetry spans for HTTP requests. Export uses OTLP over HTTP only when `OTEL_EXPORTER_OTLP_ENDPOINT` is a non-empty URL. Leave that variable unset or blank and the process does not construct an exporter, does not open a collector socket, and does not require a collector. Compose does not run a collector and does not set the variable. Request headers are not copied onto spans. Domain and application modules do not import the OpenTelemetry SDK. The wiring is `wasatch_api.observability`, called from `create_app`.

Seed loads only `data/fixtures/valid/`, including roles, teams, support tickets, messages, interactions, approval requests, audit events, documents, document versions, and document extractions. It refuses `quality-issues/`. The procedure corpus under `data/documents/procedures/` is not seeded and does not replace those fixtures. Document version rows store `storage_path` and do not load file bytes. `procedure_page_embeddings.embedding` is filled by the application service from procedure text, not by seed and not from document bytes. Approval rows are updated on a later seed. Audit rows are insert-only: a later seed skips an audit event that already exists and does not update or delete it. `employees.role_id` references `roles`. `is_approver` stays on the role.
