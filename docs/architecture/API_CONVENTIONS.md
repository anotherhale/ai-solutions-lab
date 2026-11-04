# API Conventions

The first HTTP surface is a **read-only** FastAPI service: `services/wasatch-api`.

OpenAPI is available at `/docs` when the process is running.

## Identifiers

Path parameters use external business identifiers from the JSON Schema contracts (`cust_0001`, `loc_0001`, `wo_0001`). Internal UUIDs are not returned.

## Versioning

All resource routes are under `/api/v1/`. Additive optional fields may appear in v1. Breaking changes require `/api/v2/`.

## Pagination

List endpoints return:

```json
{
  "items": [],
  "page": 1,
  "page_size": 20,
  "total": 0
}
```

Defaults: `page=1`, `page_size=20`, maximum `page_size=100`. Ordering is by business id, ascending.

## Errors

```json
{ "error": { "code": "not_found", "message": "customer cust_9999 was not found" } }
```

| HTTP | Code | When |
|---|---|---|
| 404 | `not_found` | Unknown business id |
| 422 | `invalid_parameter` | Bad query values such as an unknown status |
| 503 | — | Readiness probe cannot reach PostgreSQL |

## Endpoints in this slice

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Process liveness |
| GET | `/health/ready` | Database connectivity |
| GET | `/api/v1/customers` | Search, status filter, pagination |
| GET | `/api/v1/customers/{customer_id}` | Customer plus contacts and locations |
| GET | `/api/v1/service-locations/{location_id}` | Location plus owning customer |
| GET | `/api/v1/work-orders` | Filter by customer, status, employee, location |
| GET | `/api/v1/work-orders/{work_order_id}` | Work order plus tasks, appointments, equipment |

There are no write routes. CORS is off unless `CORS_ORIGINS` is set.

## Example requests

```bash
curl -s http://localhost:8000/health
curl -s 'http://localhost:8000/api/v1/customers?q=Pioneer'
curl -s http://localhost:8000/api/v1/customers/cust_0001
curl -s http://localhost:8000/api/v1/service-locations/loc_0001
curl -s 'http://localhost:8000/api/v1/work-orders?status=created'
curl -s http://localhost:8000/api/v1/work-orders/wo_0004
```
