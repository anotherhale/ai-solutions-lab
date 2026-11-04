# Wasatch API

FastAPI service for synthetic Wasatch Business Systems data.

This is the modular-monolith slice. It does not include a React UI or stored embeddings. Reads under `/api/v1` require a laboratory actor. An active employee may draft a suggested reply. An approver may approve or reject a pending customer message. Neither command sends the message. Other writes are denied. The model provider defaults to `AI_PROVIDER=fake` and does not need an API key.

`GET /api/v1/support-tickets/{ticket_id}/retrieval` reads persisted ticket, message, interaction, and work-order text for that ticket's customer, then matches synthetic procedure pages under `data/documents/procedures/`. It does not call a model and does not store embeddings.

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

An anonymous call to `/api/v1` returns 401. An authenticated write other than the suggested-reply draft or the customer-message decision returns 403. `APP_LOG_LEVEL` controls structured logs of the actor, action, subject, and outcome. Message bodies and secrets are not logged.

Seed loads only `data/fixtures/valid/`, including roles, teams, support tickets, messages, interactions, approval requests, and audit events. It refuses `quality-issues/`. The procedure corpus under `data/documents/procedures/` is not seeded and does not replace those fixtures. Approval rows are updated on a later seed. Audit rows are insert-only: a later seed skips an audit event that already exists and does not update or delete it. `employees.role_id` references `roles`. `is_approver` stays on the role.
