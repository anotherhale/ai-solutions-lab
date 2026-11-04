# Wasatch Business Systems Workflows

**All workflows describe synthetic laboratory processes** for Wasatch Business Systems. They are not implemented application state machines yet. Status values match [WASATCH_DOMAIN_MODEL.md](WASATCH_DOMAIN_MODEL.md) and `data/schemas/v1/`.

None of these workflows is strictly linear. Dispatch, accounting, and customer service reopen, cancel, and wait on people and parts. Human approval is required before financial postings and customer-committing messages.

Dataset clock: **2026-11-03**.

## 1. Work Order

Happy path: `created` → `scheduled` → `assigned` → `in_progress` → `completed` → `invoiced`.

Exception paths include awaiting parts, cancellation, no-show rescheduling, and reopening after completion.

```mermaid
stateDiagram-v2
    [*] --> created: Customer or CS request
    created --> scheduled: Dispatch books window
    created --> cancelled: Duplicate, weather, or customer request
    scheduled --> assigned: Technician named
    scheduled --> cancelled: Customer cancels before assignment
    assigned --> in_progress: Technician on site
    assigned --> scheduled: Reassigned / slot moved
    assigned --> cancelled: Cancelled with approval when cost is incurred
    in_progress --> awaiting_parts: Parts unavailable
    in_progress --> completed: Work finished and noted
    in_progress --> cancelled: Stopped after arrival
    awaiting_parts --> in_progress: Parts received
    awaiting_parts --> cancelled: Customer declines wait
    completed --> invoiced: Accounting issues invoice
    completed --> reopened: Callback or missed defect
    reopened --> assigned: Return visit planned
    reopened --> in_progress: Same-day return
    invoiced --> [*]
    cancelled --> [*]
```

### Guards and human intervention

- Moving a booked appointment that affects field cost uses `change_schedule` approval when the visit is imminent.
- `cancelled` after assignment or progress uses `cancel_work_order` approval.
- `completed` and `invoiced` require `completed_at` and `completion_notes`.
- `invoiced` requires an `invoice_id`.
- `reopened` requires `reopen_reason` and typically a callback work type or task.
- Awaiting parts is a waiting state, not a failure. The work order remains the system of record.

## 2. Invoice

Happy path: `draft` → `issued` → `partially_paid` → `paid`.

Overdue and voided are sibling states, not required steps. A draft can be discarded by voiding before issue. An issued invoice can become overdue with or without partial payment.

```mermaid
stateDiagram-v2
    [*] --> draft: Work complete or agreement bill
    draft --> issued: Accounting issues, often after approval
    draft --> voided: Draft discarded
    issued --> partially_paid: Posted payment below total
    issued --> paid: Posted payment equals total
    issued --> overdue: Past due_on with balance remaining
    issued --> voided: Approved void
    partially_paid --> paid: Remaining balance posted
    partially_paid --> overdue: Due date passes with balance
    overdue --> partially_paid: Partial payment, still due soon after correction
    overdue --> paid: Balance cleared
    overdue --> voided: Approved write-off or billing error
    paid --> [*]
    voided --> [*]
```

In the laboratory status model, `overdue` is the status whenever the invoice is past due and unpaid as of 2026-11-03, including invoices that already have a partial payment. `partially_paid` is used when a balance remains but the invoice is not yet due.

### Guards and human intervention

- Issuing a material invoice can require `issue_invoice` approval.
- Voiding an issued invoice requires `void_invoice` approval and `void_reason`.
- `total = subtotal + tax + adjustments`.
- `amount_paid` is the sum of `posted` payments only.
- `balance = total - amount_paid`.
- Posted payments must not exceed `total`. Over-application is a reconciliation case, not a silent success.
- Price overrides on lines require `price_override` approval.

## 3. Support Ticket

Happy path: `opened` → `triaged` → `assigned` → `awaiting_customer` → `resolved` → `closed`.

`awaiting_customer` is optional. Many tickets never wait on the customer. Resolved tickets can reopen. Closed is the intended rest state.

```mermaid
stateDiagram-v2
    [*] --> opened: Phone, email, SMS, or portal
    opened --> triaged: CS classifies and links context
    opened --> closed: Spam or immediate duplicate
    triaged --> assigned: Owner named
    triaged --> awaiting_customer: Need access or serial number
    assigned --> awaiting_customer: Question sent to customer
    assigned --> resolved: Answered or work order created
    awaiting_customer --> assigned: Customer replies
    awaiting_customer --> resolved: Timeout with documented assumption
    resolved --> closed: No further action
    resolved --> reopened: Customer returns with same issue
    closed --> reopened: Reopened after close
    reopened --> assigned: Same or new owner
    closed --> [*]
```

### Guards and human intervention

- Outbound messages that commit Wasatch require `send_customer_message` approval before `sent`.
- Creating field work from a ticket does not close the ticket automatically.
- `closed` requires `closed_at`. `resolved` should record `resolved_at`.
- Emergency priority tickets skip the leisurely triage wait in practice but still pass through `triaged` or `assigned` so reporting stays consistent.

## 4. Approval Request

Happy path: `pending` → `approved` → `executed`.

Rejection and cancellation are first-class outcomes. Execution is a separate step so an approval cannot be mistaken for the side effect.

```mermaid
stateDiagram-v2
    [*] --> pending: Requester submits action
    pending --> approved: Reviewer accepts
    pending --> rejected: Reviewer declines
    pending --> cancelled: Requester or manager withdraws
    approved --> executed: System or human performs action
    approved --> cancelled: Action no longer needed
    rejected --> [*]
    executed --> [*]
    cancelled --> [*]
```

### Guards and human intervention

- `decision_history` appends every transition with actor, time, from-status, to-status, and note.
- `approved` and `rejected` require `reviewer_employee_id` and `decided_at`.
- `executed` requires `executed_at` and a prior approval.
- Reviewers should hold a role with `is_approver: true`.
- Automation may create the pending request. It may not mark `executed` without a human decision for the action types listed in the domain model.

## Cross-workflow sequences

Typical emergency repair:

1. Ticket `opened` from a phone call.
2. Work order `created` with `emergency` priority.
3. Appointment scheduled; work order `assigned` then `in_progress`.
4. Ticket `resolved` when the technician is rolling, or later when the customer is informed.
5. Work order `completed` with notes, then invoice `draft` → `issued`.

Typical document-driven vendor bill:

1. Document `uploaded` from email, `untrusted: true`.
2. Extraction `needs_review`.
3. Human accepts extraction.
4. Invoice draft created; `issue_invoice` approval if amounts are unusual.

See [WASATCH_DOMAIN_MODEL.md](WASATCH_DOMAIN_MODEL.md) for invariants and [../architecture/DATA_CONTRACTS.md](../architecture/DATA_CONTRACTS.md) for machine-readable status enumerations.
