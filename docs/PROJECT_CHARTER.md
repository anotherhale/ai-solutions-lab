# Project Charter

## Vision

Build a reusable AI implementation laboratory that designs, ships, and demonstrates practical systems for small and midsize businesses. The laboratory should produce both working software and a consulting portfolio that can be applied to real companies along the Wasatch Front.

## Objectives

1. Establish a professional engineering foundation before application work begins.
2. Model a realistic SMB operating environment with synthetic data.
3. Deliver six AI solution types that map to common SMB constraints: limited staff, fragmented systems, and high cost of errors.
4. Keep implementation patterns portable so they can be reused with other clients.
5. Measure outcomes in operational terms, such as response time, document cycle time, and dispatcher effort, not only model quality.

## Target Customers

The eventual real-world customers are small and midsize businesses in the Salt Lake City, Utah area, especially firms with:

- Field service or appointment-driven operations
- High inbound customer communication volume
- Document-heavy workflows
- Institutional knowledge trapped in people and shared drives
- Leadership that wants AI assistance without surrendering approval authority

The laboratory customer is **Wasatch Business Systems**, a fictional company used to design and prove those capabilities.

## Simulated Business

Wasatch Business Systems is a Utah-based commercial HVAC and facilities maintenance company.

| Attribute | Synthetic value |
|---|---|
| Headquarters | Salt Lake City, Utah |
| Service area | Wasatch Front commercial properties |
| Employees | Approximately 65 |
| Customers | Approximately 450 |
| Operating functions | Sales, customer service, field operations, dispatch and scheduling, accounting and finance, human resources, and management |

The full profile is in [business/WASATCH_BUSINESS_PROFILE.md](business/WASATCH_BUSINESS_PROFILE.md). All business data is synthetic.

## Project Scope

In scope:

- Repository standards, architecture documentation, and ADRs
- A modular monolith for Wasatch Business Systems laboratory applications
- AI solutions for customer service, document processing, workflow automation, knowledge management, sales qualification, and business intelligence
- Synthetic datasets, fixtures, and documents required to demonstrate those solutions
- Local development tooling and, later, Azure deployment automation
- Case studies and reusable delivery assets for consulting work

## Out of Scope

- Real customer data, real employee records, or production credentials
- Live work for an actual HVAC company in this repository
- Microservices or Kubernetes as the initial architecture
- Autonomous financial posting, contract changes, or customer communications without human approval
- A general-purpose AI platform unrelated to SMB operations
- Installing Nx, application frameworks, or cloud infrastructure before they are required

## Success Criteria

The foundation phase is successful when:

- The repository has coherent documentation, security rules, and validation tooling.
- Architectural decisions are written as ADRs and internally consistent.
- A new contributor can understand the purpose, stack, and working agreements from the documents alone.

Later phases are successful when:

- Each planned AI solution has a working laboratory implementation against synthetic Wasatch data.
- Consequential actions remain behind human approval.
- Deployment, testing, and observability are good enough to discuss with a real SMB buyer.
- At least one case study explains the problem, approach, and measured outcome without claiming production use that did not occur.
