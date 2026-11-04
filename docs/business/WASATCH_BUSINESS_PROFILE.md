# Wasatch Business Systems

**All information in this document is synthetic.** Wasatch Business Systems is a fictional company created for laboratory design, implementation, and demonstration. It is not a real business, and none of the people, customers, or financial figures refer to actual entities.

## Company Snapshot

| Field | Synthetic value |
|---|---|
| Legal name | Wasatch Business Systems, LLC |
| Trade name | Wasatch Business Systems |
| Industry | Commercial HVAC and facilities maintenance |
| Headquarters | Salt Lake City, Utah |
| Service area | Wasatch Front: Salt Lake, Utah, Davis, and Weber counties, plus selected Summit County commercial sites |
| Approximate employees | 65 |
| Approximate customers | 450 |
| Founded | 2009 |
| Ownership | Privately held |

Wasatch Business Systems installs, services, and maintains commercial heating, ventilation, air conditioning, and related building systems. The company also sells preventive maintenance agreements and light facilities services such as filter programs, rooftop-unit inspections, and after-hours trouble calls.

## Why This Business

The company is sized to look like a real Utah SMB: large enough to have departments and system fragmentation, small enough that tribal knowledge still runs the operation. That combination is where the planned AI solutions are most testable.

## Organization

Approximate headcount is synthetic and intended to total 65 people.

| Department | Headcount | Role in the operation |
|---|---|---|
| Field operations | 30 | Technicians and lead technicians who perform installs, repairs, and maintenance |
| Dispatch and scheduling | 5 | Assigns jobs, handles route changes, and coordinates parts |
| Customer service | 8 | Answers phones and email, logs requests, and follows up on open work |
| Sales | 6 | Pursues maintenance agreements, retrofits, and competitive replacements |
| Accounting and finance | 5 | Invoicing, collections, vendor bills, payroll coordination, and job costing |
| Human resources | 2 | Hiring, onboarding, certifications, and employee records |
| Parts and warehouse | 4 | Inventory, purchasing support, and truck stock |
| Management and administration | 5 | General manager, operations manager, service manager, and office staff |

## Customers and Relationships

The synthetic book of business is about 450 commercial accounts:

- Property managers for office and retail buildings
- Light industrial and warehouse owners
- Medical and dental offices
- School and municipal facilities with limited in-house staff
- A smaller set of multi-site regional accounts

Typical relationship patterns:

- Maintenance-agreement customers expect seasonal inspections and priority response.
- Time-and-material customers call when equipment fails.
- Sales owns the quote until a job is sold; customer service and dispatch own the experience afterward.
- Accounting sees the customer again at invoice and collections time, often with incomplete job notes.

## Core Business Processes

1. **Service request intake.** A customer calls, emails, or leaves a portal message. Customer service creates or updates a request and asks dispatch for timing.
2. **Dispatch and scheduling.** Dispatch assigns a technician based on license, proximity, truck stock, and agreement priority. Same-day changes are common in summer.
3. **Field execution.** The technician completes work, captures notes, and records parts. Notes vary widely in quality.
4. **Review and invoicing.** Office staff reconcile the work order, add billable items, and send an invoice.
5. **Collections and job costing.** Accounting matches payments, vendor bills, and technician time.
6. **Maintenance sales.** Sales renews agreements, quotes replacements, and hands accepted work back to operations.
7. **People operations.** HR tracks EPA certifications, safety training, and seasonal hiring.

These processes are the source of the six planned AI solutions: customer service automation, document processing, workflow automation, knowledge management, sales qualification, and reporting.

## Current Systems Landscape

The laboratory should assume a fragmented, realistic SMB stack rather than a greenfield enterprise platform.

| Capability | Current synthetic system | Pain |
|---|---|---|
| Accounting | Desktop accounting package plus spreadsheets | Manual invoice assembly and slow month-end |
| Field service | Aging work-order tool plus shared inboxes | Incomplete history and duplicate requests |
| Documents | Email attachments and a shared drive | No reliable classification or extraction |
| Knowledge | Senior technicians and a dated procedures folder | Answers depend on who is available |
| Communications | Phone, email, and SMS | After-hours coverage is thin |
| Reporting | Manager-built spreadsheets | Numbers disagree across departments |

Future adapters should hide these systems so a real client's tools can replace them.

## Operational Challenges

- Customer service cannot consistently answer equipment or agreement questions without interrupting technicians.
- Dispatch spends too much time reconstructing job context from email threads.
- Invoices wait on unstructured work-order notes and vendor PDFs.
- Sales qualification is informal; weak leads consume technician site-visit time.
- Managers lack a single operational picture of callback rates, agreement coverage, and technician utilization.
- There is no safe way to automate customer or financial actions without human review.

## Laboratory Implications

AI work for this company must:

- Use only synthetic customers, employees, documents, and telemetry
- Prefer assistance and draft generation over autonomous action
- Require approval before customer-impacting or financial operations
- Preserve department boundaries while sharing a single modular monolith
- Produce artifacts that can later be explained in consulting case studies

Detailed process maps and synthetic datasets will be added under `data/` in later phases. They do not exist yet.
