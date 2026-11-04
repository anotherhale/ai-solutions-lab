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
- Store embeddings in PostgreSQL with pgvector.

**Exit criteria:** A reviewer can process a document packet from upload through validated structured output without trusting the model blindly.

## Phase 4: AI Business Operations and Workflow Automation

**Target window:** Days 51-70

- Connect customer service and document outcomes to operational workflows.
- Use n8n for edge automations such as intake and notification.
- Keep canonical rules in the modular monolith.
- Add first cuts of knowledge management, sales qualification, or dispatch assistance only where they support an end-to-end Wasatch process.

**Exit criteria:** At least one multi-step business workflow runs with human approval and an audit trail.

## Phase 5: Production Engineering and Cloud Deployment

**Target window:** Days 71-85

- Add automated tests beyond repository conventions.
- Introduce OpenTelemetry instrumentation for the running modules.
- Define Terraform for a non-production Azure environment.
- Document operational runbooks, backup expectations, and secret management.

**Exit criteria:** The laboratory application can be deployed to Azure by a documented path. Do not describe this environment as live until it exists.

## Phase 6: Consulting Portfolio and Case Studies

**Target window:** Days 86-90, then ongoing

- Write case studies from the laboratory implementations.
- Extract reusable discovery, architecture, and delivery assets.
- Identify which capabilities are portable to real Salt Lake City SMBs.
- Record limitations honestly, including what was simulated.

**Exit criteria:** The repository contains at least one case study that a prospective client can read without being misled about production status.

## Alignment

This roadmap implements the objectives and scope in [PROJECT_CHARTER.md](PROJECT_CHARTER.md). Technology choices remain those in [ARCHITECTURE.md](ARCHITECTURE.md) unless an ADR changes them.

Phase 1 documentation and domain contracts are in place. Phase 2's customer-service exit is demonstrable on the local API: the review screen opens one synthetic inquiry and approves or rejects the suggested reply. It does not send the message. Phase 3 persists the document fixtures and lets an approver accept or reject an extraction that is awaiting review. That decision does not post an invoice or a payment. Embeddings are not stored. Classification, file ingest, and cloud deployment have not started.
