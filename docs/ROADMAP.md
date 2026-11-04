# Roadmap

This is a 90-day laboratory roadmap. Dates are planning targets, not delivery commitments. Application services and cloud environments listed below do not exist until the corresponding phase implements them.

The simulated subject remains **Wasatch Business Systems**. All business data is synthetic.

## Phase 1: Development Foundation and Simulated Business Infrastructure

**Target window:** Days 1-15

- Establish documentation, ADRs, repository conventions, and CI validation.
- Define the Wasatch Business Systems operating profile.
- Prepare reserved directories for apps, services, libraries, data, and infrastructure.
- Design synthetic data shapes for customers, employees, work orders, and documents without building APIs yet. Domain contracts and fixtures now exist under `data/schemas/v1/` and `data/fixtures/`.

**Exit criteria:** A new contributor can explain the purpose, architecture, and working agreements from the repository alone.

## Phase 2: AI Customer Service Assistant

**Target window:** Days 16-35

- Introduce the first FastAPI module and React surface for customer-service scenarios. The FastAPI slice and `apps/wasatch-review` exist. The screen records approve or reject and does not send the message.
- Implement retrieval over synthetic policies, service notes, and customer history.
- Draft suggested replies with escalation to a human.
- Keep outbound customer messages behind an approval queue.

**Exit criteria:** A dispatcher or customer-service agent can review an inbound inquiry, inspect a suggested reply, and approve or reject it using synthetic data.

## Phase 3: Intelligent Document Processing

**Target window:** Days 36-50

- Ingest synthetic invoices, work orders, and vendor documents.
- Classify documents and extract structured fields.
- Require human review for low-confidence extractions and any financial effect.
- Store embeddings in PostgreSQL with pgvector. Procedure-page text is stored in `procedure_page_embeddings.embedding`. Document packets still have no bytes in the repository, and the embedding is not a trusted model. The review screen can accept or reject one extraction without posting money. WF-1 is a follow-up visit in the monolith. The case study is PORT-1 ([case-studies/wasatch-laboratory-slice.md](case-studies/wasatch-laboratory-slice.md)).

**Exit criteria:** A reviewer can process a document packet from upload through validated structured output without trusting the model blindly.

## Phase 4: AI Business Operations and Workflow Automation

**Target window:** Days 51-70

- Connect customer service and document outcomes to operational workflows.
- Use n8n for edge automations such as intake and notification.
- Keep canonical rules in the modular monolith.
- Add first cuts of knowledge management, sales qualification, or dispatch assistance only where they support an end-to-end Wasatch process.

**Exit criteria:** At least one multi-step business workflow runs with human approval and an audit trail.

WF-1 is that workflow for this slice: a dispatcher confirms or cancels a follow-up visit only after an approver has approved the customer message. The visit stays unscheduled until that second human decision. n8n is not connected. The case study is PORT-1 ([case-studies/wasatch-laboratory-slice.md](case-studies/wasatch-laboratory-slice.md)).

## Phase 5: Production Engineering and Cloud Deployment

**Target window:** Days 71-85

OPS-1 is the bounded slice:

- The Wasatch API host records OpenTelemetry spans. Export runs only when `OTEL_EXPORTER_OTLP_ENDPOINT` is set. An unset or blank value does not open a socket and does not require a collector.
- Laboratory notes for backup expectations and secret management are in `docs/operations/`.
- Terraform stays a placeholder. No workspace exists, so this slice adds no Azure module, backend, subscription id, tenant id, or credential.
- Docker Compose and GitHub Actions do not gain a collector, Redis, n8n, or a cloud account. GitHub Actions stays credential-free.

**Exit criteria:** The laboratory application can be deployed to Azure by a documented path. That path is not defined. Do not describe an environment as live until it exists. The case study is PORT-1 ([case-studies/wasatch-laboratory-slice.md](case-studies/wasatch-laboratory-slice.md)).

## Phase 6: Consulting Portfolio and Case Studies

**Target window:** Days 86-90, then ongoing

- Write case studies from the laboratory implementations.
- Extract reusable discovery, architecture, and delivery assets.
- Identify which capabilities are portable to real Salt Lake City SMBs.
- Record limitations honestly, including what was simulated.

PORT-1 is [case-studies/wasatch-laboratory-slice.md](case-studies/wasatch-laboratory-slice.md). That file is the case study in the exit criterion below. It does not add a deployment, a model call, or a measured business result. Reusable discovery assets and a separate portability catalog are not additional files.

**Exit criteria:** The repository contains at least one case study that a prospective client can read without being misled about production status. PORT-1 is that case study.

## Alignment

This roadmap implements the objectives and scope in [PROJECT_CHARTER.md](PROJECT_CHARTER.md). Technology choices remain those in [ARCHITECTURE.md](ARCHITECTURE.md) unless an ADR changes them.

Phase 1 documentation and domain contracts are in place. Phase 2's customer-service exit is demonstrable on the local API: the review screen opens one synthetic inquiry and approves or rejects the suggested reply. It does not send the message. Phase 3 persists the document fixtures and lets an approver accept or reject an extraction that is awaiting review through the API and review screen. That decision does not post an invoice or a payment. Procedure-page embeddings are stored with the fake port and are not a trusted model. Classification, file ingest, and cloud deployment have not started. OPS-1 records host spans and laboratory backup and secret notes. The case study is PORT-1 ([case-studies/wasatch-laboratory-slice.md](case-studies/wasatch-laboratory-slice.md)).
