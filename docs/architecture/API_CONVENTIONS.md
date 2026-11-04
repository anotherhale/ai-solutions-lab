# API Conventions

The HTTP surface is the FastAPI service `services/wasatch-api`.

OpenAPI is available at `/docs` when the process is running. `/health`, `/health/ready`, and the OpenAPI documents do not require an actor.

## Laboratory actor

Local synthetic development simulates a caller with a request header. There is no password and no identity provider. The header is not authentication.

```bash
curl -s -H 'X-Laboratory-Actor: emp_0001' \
  http://localhost:8000/api/v1/support-tickets/tkt_0007
```

`emp_0001` is the synthetic general manager (`role_0001`, `is_approver` true). `emp_0004` is the synthetic dispatcher (`role_0004`, `is_approver` false). The adapter loads the employee and reads `is_approver` from that role. Only an `active` employee is accepted. Unknown, blank, and inactive values are rejected.

Every later write in this slice can take the resolved actor from the request. Writes are denied except two commands. `POST /api/v1/support-tickets/{ticket_id}/draft-replies` lets any active laboratory actor draft a suggested reply. The reply is grounded in retrieval for that ticket. Text that would commit Wasatch is stored as `pending_approval` with `requires_approval` and a new `send_customer_message` request. Other text is stored as `draft` with no approval. `POST /api/v1/approval-requests/{approval_id}/decisions` lets an approver approve or reject a pending `send_customer_message`. The workforce application service calls `authorize_approval_decision` before that command writes. A non-approver is denied. The command appends `decision_history`, sets `reviewer_employee_id` and `decided_at`, and inserts an audit event. Neither command sends the message or marks it `sent`. Rejecting the approval leaves the draft unsent. Team membership is not required.

The process starts only when `APP_ENV` is `local`, `development`, or `test`. `APP_ENV=production` and `APP_ENV=prod` raise `UnsafeProductionConfiguration` during startup and do not serve. The same refusal applies to every other environment. A future production authenticator would be a separate `EmployeeAuthenticator` adapter, not this header, not a password system, and not an identity provider in this service. See [ADR 0006](../adr/0006-laboratory-actor-development-only.md).

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
| 401 | `unauthenticated` | `/api/v1` call without an active laboratory actor |
| 403 | `forbidden` | Authenticated write other than the suggested-reply draft or the customer-message decision, or a non-approver attempting that decision |
| 404 | `not_found` | Unknown business id |
| 422 | `invalid_parameter` | Bad query values such as an unknown status, or a reply that cites no retrieved source |
| 503 | `provider_unavailable` | `AI_PROVIDER=openai` without a usable `OPENAI_API_KEY`. The default `fake` provider does not use this response |
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
| GET | `/api/v1/support-tickets/{ticket_id}/retrieval` | That customer's history and matching procedure pages |
| GET | `/api/v1/messages` | Filter by ticket or message status |
| GET | `/api/v1/messages/{message_id}` | One ticket message |
| GET | `/api/v1/interactions` | Filter by customer or ticket |
| GET | `/api/v1/interactions/{interaction_id}` | One customer touch |
| GET | `/api/v1/approval-requests` | Filter by status or action type |
| GET | `/api/v1/approval-requests/{approval_id}` | One approval request, including decision history |
| POST | `/api/v1/support-tickets/{ticket_id}/draft-replies` | Draft an unsent suggested reply grounded in retrieval. A commitment opens `send_customer_message` |
| POST | `/api/v1/approval-requests/{approval_id}/decisions` | Approve or reject a pending customer message. The message stays unsent |
| GET | `/api/v1/audit-events` | Filter by outcome or approval request |
| GET | `/api/v1/audit-events/{audit_event_id}` | One audit event |

A message that references an approval includes that approval request on the message payload. The draft and decision routes are the writes. There is no write route that updates or deletes audit events. An authenticated write outside those commands receives `403`. An anonymous call receives `401`.

`POST /api/v1/support-tickets/{ticket_id}/draft-replies` requires `X-Laboratory-Actor`. The server builds the reply from retrieval for that ticket. The client does not submit the body. The default provider is `AI_PROVIDER=fake`, which quotes retrieved source ids and does not call the network. `AI_PROVIDER=openai` is used only with a non-placeholder `OPENAI_API_KEY`. For synthetic ticket `tkt_0015` the fake reply cites `msg_0015` and procedure `proc_0001` and promises a visit, so the message is `pending_approval`. Rejecting that approval leaves the message unsent.

`GET /api/v1/support-tickets/{ticket_id}/retrieval` is read-only and requires `X-Laboratory-Actor`. History is that ticket's customer only, ordered by source (`support_ticket`, `message`, `interaction`, `work_order`) and then business id. Procedure pages are the synthetic files under `data/documents/procedures/` whose text shares a content word with the ticket subject and message bodies. The route does not call a model.

```json
{
  "support_ticket_id": "tkt_0015",
  "customer_id": "cust_0011",
  "history": [
    {
      "source": "message",
      "source_id": "msg_0015",
      "text": "Please send a technician. Rooftop unit is down."
    }
  ],
  "procedures": [
    {
      "id": "proc_0001",
      "title": "Rooftop unit is down",
      "path": "rooftop-unit-down.txt",
      "text": "Synthetic laboratory procedure for Wasatch Business Systems.",
      "synthetic": true
    }
  ]
}
```

CORS is off unless `CORS_ORIGINS` is set. When it is set, allowed methods include `POST` for the decision command, and allowed headers include `X-Laboratory-Actor`.

## Example requests

```bash
curl -s http://localhost:8000/health
curl -s -H 'X-Laboratory-Actor: emp_0001' \
  'http://localhost:8000/api/v1/customers?q=Pioneer'
curl -s -H 'X-Laboratory-Actor: emp_0001' \
  http://localhost:8000/api/v1/customers/cust_0001
curl -s -H 'X-Laboratory-Actor: emp_0001' \
  http://localhost:8000/api/v1/service-locations/loc_0001
curl -s -H 'X-Laboratory-Actor: emp_0001' \
  'http://localhost:8000/api/v1/work-orders?status=created'
curl -s -H 'X-Laboratory-Actor: emp_0001' \
  http://localhost:8000/api/v1/work-orders/wo_0004
curl -s -H 'X-Laboratory-Actor: emp_0001' \
  http://localhost:8000/api/v1/support-tickets/tkt_0007
curl -s -H 'X-Laboratory-Actor: emp_0001' \
  http://localhost:8000/api/v1/support-tickets/tkt_0015/retrieval
curl -s -X POST -H 'X-Laboratory-Actor: emp_0001' \
  http://localhost:8000/api/v1/support-tickets/tkt_0015/draft-replies
curl -s -H 'X-Laboratory-Actor: emp_0001' \
  'http://localhost:8000/api/v1/messages?support_ticket_id=tkt_0007'
curl -s -H 'X-Laboratory-Actor: emp_0001' \
  http://localhost:8000/api/v1/interactions/ixn_0001
curl -s -H 'X-Laboratory-Actor: emp_0001' \
  http://localhost:8000/api/v1/messages/msg_0016
curl -s -H 'X-Laboratory-Actor: emp_0001' \
  http://localhost:8000/api/v1/approval-requests/apr_0001
curl -s -H 'X-Laboratory-Actor: emp_0001' \
  'http://localhost:8000/api/v1/audit-events?approval_request_id=apr_0001'
curl -s -X POST -H 'X-Laboratory-Actor: emp_0001' \
  -H 'content-type: application/json' \
  -d '{"decision":"approved","note":"Overtime approved."}' \
  http://localhost:8000/api/v1/approval-requests/apr_0001/decisions
```
