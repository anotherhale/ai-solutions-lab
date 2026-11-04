import { describe, expect, it } from "vitest";
import { canDecideSuggestion, suggestedReply } from "./suggestion";
import type { TicketMessage } from "./types";

function message(overrides: Partial<TicketMessage>): TicketMessage {
  return {
    id: "msg_0001",
    support_ticket_id: "tkt_0001",
    direction: "inbound",
    channel: "portal",
    body: "Please send a technician.",
    status: "sent",
    sent_at: "2026-04-08T09:30:00Z",
    created_at: "2026-04-08T09:30:00Z",
    updated_at: "2026-04-08T09:30:00Z",
    author_employee_id: null,
    author_contact_id: "con_0008",
    requires_approval: false,
    approval_request_id: null,
    approval_request: null,
    ...overrides,
  };
}

describe("suggestedReply", () => {
  it("returns null when the inquiry has no unsent outbound reply", () => {
    expect(
      suggestedReply([
        message({ id: "msg_0007", direction: "inbound", status: "sent" }),
        message({ id: "msg_0017", direction: "outbound", status: "sent" }),
      ]),
    ).toBeNull();
  });

  it("prefers a pending suggestion over a draft", () => {
    const pending = message({
      id: "msg_0016",
      direction: "outbound",
      status: "pending_approval",
    });
    const draft = message({
      id: "msg_0099",
      direction: "outbound",
      status: "draft",
    });
    expect(suggestedReply([draft, pending])?.id).toBe("msg_0016");
  });
});

describe("canDecideSuggestion", () => {
  it("allows a pending customer-message approval that has not been executed", () => {
    const suggestion = message({
      id: "msg_0016",
      direction: "outbound",
      status: "pending_approval",
      requires_approval: true,
      approval_request_id: "apr_0001",
      approval_request: {
        id: "apr_0001",
        action_type: "send_customer_message",
        status: "pending",
        requested_by_employee_id: "emp_0006",
        subject_type: "message",
        subject_id: "msg_0016",
        rationale: "Overtime commitment needs manager approval.",
        requested_at: "2026-10-28T15:06:00Z",
        created_at: "2026-09-01T10:00:00Z",
        updated_at: "2026-10-28T15:06:00Z",
        decision_history: [],
        reviewer_employee_id: null,
        decision_notes: null,
        decided_at: null,
        executed_at: null,
      },
    });
    expect(canDecideSuggestion(suggestion)).toBe(true);
  });

  it("does not offer a decision for a sent reply or a non-message approval", () => {
    const sent = message({
      direction: "outbound",
      status: "sent",
      approval_request: {
        id: "apr_0004",
        action_type: "send_customer_message",
        status: "pending",
        requested_by_employee_id: "emp_0006",
        subject_type: "message",
        subject_id: "msg_0017",
        rationale: "Already delivered in the fixture.",
        requested_at: "2026-09-12T11:00:00Z",
        created_at: "2026-09-12T11:00:00Z",
        updated_at: "2026-09-12T11:20:00Z",
        decision_history: [],
        reviewer_employee_id: null,
        decision_notes: null,
        decided_at: null,
        executed_at: null,
      },
    });
    const invoice = message({
      direction: "outbound",
      status: "pending_approval",
      approval_request: {
        id: "apr_0002",
        action_type: "void_invoice",
        status: "pending",
        requested_by_employee_id: "emp_0009",
        subject_type: "invoice",
        subject_id: "inv_0005",
        rationale: "Customer disputes duplicate visit.",
        requested_at: "2026-11-01T09:15:00Z",
        created_at: "2026-09-01T10:00:00Z",
        updated_at: "2026-11-01T09:15:00Z",
        decision_history: [],
        reviewer_employee_id: null,
        decision_notes: null,
        decided_at: null,
        executed_at: null,
      },
    });
    expect(canDecideSuggestion(sent)).toBe(false);
    expect(canDecideSuggestion(invoice)).toBe(false);
    expect(canDecideSuggestion(null)).toBe(false);
  });
});
