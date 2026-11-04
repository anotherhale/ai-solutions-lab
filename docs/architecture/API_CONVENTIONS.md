# API Conventions

The first HTTP surface is a **read-only** FastAPI service: `services/wasatch-api`.

OpenAPI is available at `/docs` when the process is running.

## Identifiers

Path parameters use external business identifiers from the JSON Schema contracts (`cust_0001`, `loc_0001`, `wo_0001`, `tkt_0001`, `msg_0001`, `ixn_0001`, `apr_0001`, `aud_0001`). Internal UUIDs are not returned.

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

Defaults: `page=1`, `page_size=20`, maximum `page_size=100`. Ordering is by business id, ascending. Messages nested on a ticket are ordered by `sent_at`.

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
| GET | `/api/v1/support-tickets` | Filter by customer, status, location, employee |
| GET | `/api/v1/support-tickets/{ticket_id}` | Ticket plus messages |
| GET | `/api/v1/messages` | Filter by ticket or message status |
| GET | `/api/v1/messages/{message_id}` | One ticket message |
| GET | `/api/v1/interactions` | Filter by customer or ticket |
| GET | `/api/v1/interactions/{interaction_id}` | One customer touch |
| GET | `/api/v1/approval-requests` | Filter by status or action type |
| GET | `/api/v1/approval-requests/{approval_id}` | One approval request, including decision history |
| GET | `/api/v1/audit-events` | Filter by outcome or approval request |
| GET | `/api/v1/audit-events/{audit_event_id}` | One audit event |

A message that references an approval includes that approval request on the message payload. There is no route that records an approval decision, and there is no write route for audit events.

There are no write routes. CORS is off unless `CORS_ORIGINS` is set.

## Example requests

```bash
curl -s http://localhost:8000/health
curl -s 'http://localhost:8000/api/v1/customers?q=Pioneer'
curl -s http://localhost:8000/api/v1/customers/cust_0001
curl -s http://localhost:8000/api/v1/service-locations/loc_0001
curl -s 'http://localhost:8000/api/v1/work-orders?status=created'
curl -s http://localhost:8000/api/v1/work-orders/wo_0004
curl -s http://localhost:8000/api/v1/support-tickets/tkt_0007
curl -s 'http://localhost:8000/api/v1/messages?support_ticket_id=tkt_0007'
curl -s http://localhost:8000/api/v1/interactions/ixn_0001
curl -s http://localhost:8000/api/v1/messages/msg_0016
curl -s http://localhost:8000/api/v1/approval-requests/apr_0001
curl -s 'http://localhost:8000/api/v1/audit-events?approval_request_id=apr_0001'
```
