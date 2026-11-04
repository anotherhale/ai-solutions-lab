# Wasatch API

Read-only FastAPI service for synthetic Wasatch Business Systems data.

This is the first modular-monolith slice. It does not include AI assistants, embeddings, or a React UI.

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

Seed loads only `data/fixtures/valid/`. It is idempotent and refuses `quality-issues/`.
