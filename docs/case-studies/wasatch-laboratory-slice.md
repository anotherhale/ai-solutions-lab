# Wasatch Business Systems laboratory slice

PORT-1. This file is a case study. It does not add a service, a model call, a measurement, or a deployment.

Wasatch Business Systems is fictional. It is not a client. Every customer, employee, and financial figure in this repository is synthetic. The names below are fixture records, not real people or real companies.

If this page and the code disagree, the code wins. The inventory of what was run is [PROJECT_STATUS.md](../../PROJECT_STATUS.md). This study does not replace that file, and it does not re-run the checks recorded there.

## What you can conclude

On the integration branch `develop`, the repository contains a local laboratory slice:

- Customer-service reads, retrieval, draft replies, human approval, and the review screen
- Document reads and extraction review
- Procedure-page embeddings
- A follow-up visit after an approved customer message
- Host traces

`main` is not the deployed product. Approving a customer message does not send it. Confirming a follow-up does not dispatch a technician and does not change invoices. No Azure environment is running.

## What you must not conclude

This study does not report return on investment, model accuracy, time saved, fewer truck rolls, or a count of real customers. Those figures are not in the repository. Fixture sizes and test totals are copied from `PROJECT_STATUS.md`. The branch comparison is the git command in the next section. Pull request numbers identify merged changes. This change did not re-run the API suite and did not read a GitHub Actions log.

## The fictional company

[WASATCH_BUSINESS_PROFILE.md](../business/WASATCH_BUSINESS_PROFILE.md) describes Wasatch Business Systems, LLC as a privately held commercial HVAC and facilities maintenance company headquartered in Salt Lake City. The profile states approximate synthetic figures of 65 employees and 450 customers. Those figures describe the fiction. They are not a count of records the software served, and they are not a market result.

The API loads a smaller slice of that same fiction. `PROJECT_STATUS.md`, "Phase 1 — foundation," records the domain validator counts from `scripts/validate_wasatch_domain.py`: 15 customers and 15 employees, with the other entity counts in that file's "Verification in this session" table. That section calls the fixture set a laboratory slice of the synthetic company, not a second dataset.

The profile's office pattern — an inbound request, a suggested reply, a person before any promise, and a later look at documents — is the shape this slice implements. The profile's account of fragmented systems is a design premise. This repository does not measure that premise.

## Where the code is

Pull requests integrate on `develop`. [DEVELOPMENT_WORKFLOW.md](../DEVELOPMENT_WORKFLOW.md) keeps `main` as the production branch name and forbids force-pushes to either branch. A merge to `main` is not a deployment, and this study does not perform one.

On 2026-11-04 the remotes compared as follows. The command was `git rev-list --left-right --count origin/main...origin/develop`.

| Branch | Commit | What that commit is |
|---|---|---|
| `develop` | `1be41811fb290a8c026157eeeb0456cbd02c693b` | Integration tip this study describes. Subject: `feat: trace the Wasatch API host without a collector (#20)`. |
| `main` | `881cfc08db1fc609e531a3f0be3230938d07f561` | Production branch name. Subject: `Keep the Wasatch API test database password visible (#1)`. |

The command printed `0` then `19`: nothing on `main` was missing from `develop`, and `develop` was 19 commits ahead. `main` does not contain the customer-service slice, the review screen, document review, embeddings, the follow-up visit, or host traces.

No Azure environment, Terraform module, collector, n8n workflow, or Redis instance is deployed. `infrastructure/terraform/` has no module, backend, subscription id, tenant id, or credential. [docs/operations/](../operations/) records backup expectations and secret notes and says those notes are not a deployment.

## What is in the repository

Each row is already on `develop` at the commit above. Pull request numbers are the ones recorded in `PROJECT_STATUS.md`.

| Capability | Where a reader can see it | Limit that stays in force |
|---|---|---|
| Customer, location, and work-order reads | `GET /api/v1/customers`, service locations, and work orders | Read-only operational slice. |
| Customer-service reads | `GET /api/v1/support-tickets`, messages, and interactions | Read-only. Pull request [#7](https://github.com/anotherhale/ai-solutions-lab/pull/7). |
| Retrieval | `GET /api/v1/support-tickets/{ticket_id}/retrieval` | One customer's history and matching procedure pages. No model call. Pull request [#12](https://github.com/anotherhale/ai-solutions-lab/pull/12). |
| Draft replies | `POST /api/v1/support-tickets/{ticket_id}/draft-replies` | The message is not marked sent. Pull request [#14](https://github.com/anotherhale/ai-solutions-lab/pull/14). |
| Human approval | `POST /api/v1/approval-requests/{approval_id}/decisions` | Does not send the message. Pull request [#13](https://github.com/anotherhale/ai-solutions-lab/pull/13). |
| Review screen | `apps/wasatch-review` | Approve or reject. No send control. Pull request [#15](https://github.com/anotherhale/ai-solutions-lab/pull/15). |
| Document reads | `GET /api/v1/documents`, document versions, and document extractions | Version paths are not files. Pull request [#16](https://github.com/anotherhale/ai-solutions-lab/pull/16). |
| Extraction review | `POST /api/v1/document-extractions/{extraction_id}/decisions` | Does not post an invoice or a payment. Pull request [#17](https://github.com/anotherhale/ai-solutions-lab/pull/17). |
| Procedure-page embeddings | `procedure_page_embeddings.embedding`, type `vector(8)` | Fake port. Not a trusted semantic model. Pull request [#18](https://github.com/anotherhale/ai-solutions-lab/pull/18). |
| Follow-up visit | `POST /api/v1/approval-requests/{approval_id}/follow-up-visits` | Does not dispatch a technician or change invoices. Pull request [#19](https://github.com/anotherhale/ai-solutions-lab/pull/19). |
| Host traces | `wasatch_api.observability`, called from `create_app` | Export only when `OTEL_EXPORTER_OTLP_ENDPOINT` is a non-empty URL. Pull request [#20](https://github.com/anotherhale/ai-solutions-lab/pull/20). |

`.github/workflows/validate.yml` was read for this study. On push to `main` or `develop`, and on pull requests, it runs Ruff, both validators, and the Wasatch API tests against PostgreSQL. It sets `WASATCH_REQUIRE_DATABASE=1`. It does not set `OPENAI_API_KEY`, `AI_PROVIDER`, or `OTEL_EXPORTER_OTLP_ENDPOINT`. It does not receive a cloud credential. CI does not call a model. The review-screen checks are not part of that workflow. Source for the last point: `PROJECT_STATUS.md`, "Verification for CS-7."

## The laboratory actor is not production authentication

`X-Laboratory-Actor` resolves to an active synthetic employee when `APP_ENV` is `local`, `development`, or `test`. `APP_ENV=production` and `APP_ENV=prod` fail startup before a request is served. There is no password system and no identity provider. ADR 0006 records a future production authenticator as a different adapter. This header is not that adapter.

In the fixtures, Jordan Hale (`emp_0001`) is General Manager, role `role_0001`, and `is_approver` is true. Elena Voss (`emp_0004`) is Dispatcher, role `role_0004`, and `is_approver` is false. Both use `@wasatch-business-systems.test` addresses. Anonymous callers receive 401 on `/api/v1`. Health probes stay open.

## A draft reply stays unsent

Synthetic ticket `tkt_0015` is for Oquirrh Distribution Center LLC (`cust_0011`). Inbound message `msg_0015` says: "Please send a technician. Rooftop unit is down."

Retrieval for that ticket returns the customer's persisted history and procedure page `proc_0001`. The page is in `data/documents/procedures/rooftop-unit-down.txt`. The file says it is synthetic and untrusted. It tells the reader to ask whether the disconnect is on and whether the thermostat is calling for cooling, and not to promise an arrival time in the first reply. `data/documents/procedures/catalog.json` lists three pages: `proc_0001`, `proc_0002`, and `proc_0003`. Those pages do not replace `data/fixtures/valid/`.

`PROJECT_STATUS.md` records that a draft for `tkt_0015` cites `msg_0015` and `proc_0001`. The default provider is the in-process fake. `AI_PROVIDER` defaults to `fake`. The chat model name is `fake-chat`. The fake port does not open a socket and does not read an API key. It quotes source ids it finds in the prompt, then appends: "We will send a technician on Thursday at 08:00." That sentence exists so the approval guard can be exercised. It is not evidence that a model followed the procedure page. The commitment rule treats "we will" and a clock time as a company commitment, so that draft is `pending_approval`, with `requires_approval` and a new `send_customer_message` request. Other text stays `draft` and opens no approval. Neither result sets status `sent`, and neither calls a delivery system.

`AI_PROVIDER=openai` with the placeholder key `replace-me` fails before an OpenAI client is constructed. Tests and CI keep the fake provider. They do not call the network.

## Approving the message does not send it

Synthetic ticket `tkt_0007` is for Cottonwood Office Commons LLC (`cust_0004`). Outbound `msg_0016` is `pending_approval`, `requires_approval` is true, and the approval is `apr_0001`. The body is: "We can be on site Thursday at 08:00 if you approve overtime."

An approver can approve or reject that pending request. The command appends decision history, sets the reviewer and `decided_at`, and inserts one audit event. Audit rows are insert-only. The message body stays unchanged. The message is not marked `sent`. No email, SMS, or other delivery runs.

`PROJECT_STATUS.md`, "Verification for CS-7," records a browser check against the local API on port 8000, with the Vite dev server proxying `/api` from `http://127.0.0.1:5173`. This case study did not repeat that check. The recorded paths:

- Jordan Hale opened `tkt_0015`. The inbound rooftop message was visible. No suggested reply was waiting. Approve and reject were absent.
- An anonymous caller opened `tkt_0007`. The API returned 401. The inquiry did not load.
- Elena Voss opened `tkt_0007` and clicked Approve reply. The actor was denied. The reply stayed pending.
- Jordan Hale approved `apr_0001` with the note `Overtime approved for Thursday.` The banner said `Approved. The message was not sent.` `msg_0016` stayed `pending_approval`. The approval was `approved`, the reviewer was `emp_0001`, and `executed_at` was null.
- After a seed restored `apr_0001` to pending, Jordan Hale rejected it with the note `Customer did not approve overtime.` The banner said `Rejected. The message was not sent.` `msg_0016` stayed `pending_approval`. `executed_at` was null.

That same section records the review-screen commands, which are not in GitHub Actions: Vitest 5.1.0, 9 passed across 2 files; `tsc --noEmit`; the Vite production build succeeded. Source: `PROJECT_STATUS.md`, "Verification for CS-7." This case study did not re-run them.

The screen has no send control.

## Documents are rows, not packets

Alembic revision `0005` stores the document fixtures. `PROJECT_STATUS.md` records the seeded counts: 30 documents, 31 versions, and 18 extractions. Needs-review extractions named there are `dx_0003`, `dx_0009`, and `dx_0015`. Version `storage_path` values such as `synthetic/documents/doc_0001/v1.bin` are strings. Those files are not in the repository. There are no bytes to ingest. A classifier is not implemented.

An approver may accept or reject an extraction that is awaiting review. Awaiting review means `needs_review`, `pending`, `succeeded`, or `failed`. `emp_0001` may decide. `emp_0004` is denied. An anonymous caller receives 401. Confidence below 0.8, a missing score, `needs_review`, an invoice or money key in `extracted_fields`, or a document linked to an invoice stays untrusted until that human decision. A read, a seed, and a background job do not accept those rows. This service has no background job and does not call a model to make the decision.

The decision stores status, reviewer, `reviewed_at`, and optional `review_notes`, and it inserts an audit event. It does not post a payment, change an invoice total, or mark an invoice posted. Fixture `dx_0004` is already `accepted` in the JSON and its `review_notes` say "Accepted for posting." That sentence is fixture text. The review command still does not post.

Invoice and payment fixtures exist as JSON. They are not posted by this slice. `PROJECT_STATUS.md`, "Verification for the follow-up visit," records that `information_schema` had no `invoices`, `invoice_lines`, or `payments` table and that the invoice and payment fixture bytes were unchanged. This case study did not query a database.

## Procedure embeddings are not a semantic model

Alembic revision `0006` adds `procedure_page_embeddings.embedding` as `vector(8)`. That width is what the laboratory embedding port returns. The fake port is the default. It fills each coordinate from a hash of the page text and labels the model `fake-embedding`. Domain code does not import a vendor SDK and does not choose another width.

Only the three procedure pages are embedded. Document version bytes are not embedded. Unaccepted, `needs_review`, low-confidence, and financial extractions are not inserted into that index, and they are not posted to invoices. Accepting an extraction does not insert it and does not change an invoice.

Retrieval for `tkt_0015` still cites `proc_0001`. Customer history stays a relational query. The stored vectors may order that procedure match. They are not a trusted semantic model. There is no second vector database.

`PROJECT_STATUS.md`, "Verification for procedure embeddings," records that filling the index wrote 3 rows (`proc_0001`, `proc_0002`, `proc_0003`), column `embedding` `vector(8)`, model `fake-embedding`, and that the test then deleted those rows. Document versions stayed 31 and extractions stayed 18. No extraction id was inserted. The run did not call OpenAI. That row count is a test result, not a standing production index. This case study did not re-run it.

`AI_PROVIDER` stays `fake` for that path. The placeholder OpenAI key fails before a client is constructed, as it does for drafts.

## Confirming a follow-up does not dispatch a technician

The command is `POST /api/v1/approval-requests/{approval_id}/follow-up-visits`. Two people act, in order.

1. An approver approves a pending `send_customer_message`. That decision leaves the message unsent. It does not open the visit and does not dispatch a technician.
2. A dispatcher (`role_0004`, including Elena Voss, `emp_0004`) opens the visit from that approved request. The visit stays `unscheduled` until a dispatcher confirms or cancels it.

Each transition inserts an audit event. Audit storage stays insert-only. Confirming or canceling does not send a message, assign a technician, create an appointment, post a payment, change an invoice total, or mark an invoice posted. Alembic revision `0007` stores `follow_up_visits` and adds no vector column. No React screen was added. The review screen does not gain a send control. n8n, Redis, Kafka, and a queue are not part of this command.

`PROJECT_STATUS.md`, "Verification for the follow-up visit," records `184 passed, 0 failed, 0 skipped` for `WASATCH_REQUIRE_DATABASE=1 .venv/bin/pytest` on parent `068a185`. The recorded scenario left no follow-up row before the customer-message approval. After that approval, the dispatcher opened `fuv_0001` as `unscheduled` and then confirmed it. `msg_0016` stayed `pending_approval`. A separate case canceled instead. `emp_0001` and `emp_0006` received 403. An anonymous caller received 401. The run did not call OpenAI and did not observe GitHub Actions. This case study did not re-run that suite.

## Traces leave the process only when asked

`create_app` records OpenTelemetry spans through `wasatch_api.observability`. Domain and application code does not import the SDK. Spans export over OTLP/HTTP only when `OTEL_EXPORTER_OTLP_ENDPOINT` is a non-empty URL. An unset or blank value does not construct an exporter and does not open a socket. Compose does not run a collector. GitHub Actions does not gain one. Request headers, including `X-Laboratory-Actor`, are not copied onto spans. Metrics export and log export are not wired. `APP_LOG_LEVEL` still configures structured logs of actor, action, subject, and outcome. Message bodies and secrets stay out of those logs.

`PROJECT_STATUS.md` records the pinned direct dependencies: `opentelemetry-api==1.45.2`, `opentelemetry-sdk==1.45.2`, `opentelemetry-exporter-otlp-proto-http==1.45.2`, and `opentelemetry-instrumentation-fastapi==0.66b2`.

`PROJECT_STATUS.md`, "Verification for host traces," records the latest API suite written in that file. The command was `WASATCH_REQUIRE_DATABASE=1 .venv/bin/pytest --tb=line -rfEs` from `services/wasatch-api`, on parent `1b22eac`. The result was `188 passed, 0 failed, 0 skipped, 1 warning in 12.74s`. The warning is the existing Starlette deprecation of `anyio.abc.BlockingPortal` in `starlette/testclient.py`. `OTEL_EXPORTER_OTLP_ENDPOINT` was unset. The run did not call OpenAI, did not open a collector socket, and did not observe GitHub Actions. `terraform plan` and `terraform apply` were not run. With the exporter unset, `GET /health` still returned `status` `ok` and `service` `wasatch-api`. This case study did not re-run that command. Do not treat 188 as a new measurement from PORT-1.

## What was simulated

- The company, its customers, its employees, and its financial fixtures.
- The actor header.
- Draft replies and embeddings, through the fake provider. CI does not select OpenAI and does not call a model.
- Procedure vectors of width 8 from that fake port.
- Document version paths that are not files.

## What was measured

Only the results already written in `PROJECT_STATUS.md`. This case study adds none.

| Recorded result | Source section in `PROJECT_STATUS.md` |
|---|---|
| Domain validator counts, including 15 customers, 15 employees, 30 documents, 31 document versions, and 18 extractions | "Verification in this session" and later validator lines that repeat the document counts |
| API pytest `188 passed, 0 failed, 0 skipped` | "Verification for host traces" |
| Earlier API totals for each slice, including `184 passed` for the follow-up visit and `173 passed` for procedure embeddings | The verification section named for that slice |
| Vitest 5.1.0, 9 passed across 2 files; typecheck; production build | "Verification for CS-7" |
| Browser approve and reject paths, including the banners that the message was not sent | "Verification for CS-7" |
| Three `vector(8)` rows written and then deleted by the embedding test | "Verification for procedure embeddings" |
| `GET /health` returned `status` `ok` with the trace exporter unset | "Verification for host traces" |

## What was not measured

- Accuracy of a semantic model, or agreement with a human reviewer.
- Time saved, calls avoided, or truck rolls avoided.
- Return on investment, revenue, or cost. Invoice totals in the fixtures are synthetic records, not a measured outcome of this software.
- Production latency, availability, or a live collector.
- Any of the above on `main`.

## What is not deployed

- An Azure environment, a Terraform workspace, or a documented path that deploys this laboratory to Azure. [ROADMAP.md](../ROADMAP.md) Phase 5 says that path is not defined.
- A trace collector, n8n, or Redis.
- A production authenticator. The laboratory header is local synthetic identity.
- Delivery of a customer message. Approval does not send it.
- Dispatch of a technician. Confirming a follow-up does not do that by itself, and it does not create an appointment.
- Posting an invoice or a payment from extraction review or from the follow-up command.
- File ingest, a document classifier, or a trusted embedding model.
- A second user interface. The only screen is `apps/wasatch-review`.
- A model credential, a collector endpoint, or a cloud credential in GitHub Actions.

## What could transfer, and what does not

The boundaries are the part worth copying onto a real Salt Lake City firm: a suggested reply stays unsent until a person approves it, a low-confidence or financial extraction stays untrusted until a person decides, and a follow-up stays unscheduled until a dispatcher confirms it. Model calls sit behind a port. The laboratory default does not need an API key, and CI does not call a provider.

The running slice does not transfer as a product. A real firm would need its own identity provider, its own system of record, a model evaluation this repository does not contain, file bytes this repository does not contain, and a deployment this repository does not define. Wasatch Business Systems cannot be that reference customer. The company is fictional.

Reusable discovery worksheets and a separate portability catalog are not additional files in this change.

## This document

PORT-1 is this file. Application behavior, tests, and the CI database gate are unchanged. Commands for inspecting the slice remain the ones in the root [README.md](../../README.md) and in `PROJECT_STATUS.md`. This study does not claim they were run again.
