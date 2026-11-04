import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { App } from "./App";
import { LABORATORY_ACTOR_HEADER } from "./actors";
import type { SupportTicket } from "./types";

const SUGGESTED_BODY = "We can be on site Thursday at 08:00 if you approve overtime.";

function ticket(overrides: Partial<SupportTicket> = {}): SupportTicket {
  return {
    id: "tkt_0007",
    customer_id: "cust_0004",
    status: "awaiting_customer",
    priority: "normal",
    channel: "portal",
    subject: "Service request related to wo_0007",
    opened_at: "2026-04-08T09:30:00Z",
    created_at: "2026-04-08T09:30:00Z",
    updated_at: "2026-04-08T09:30:00Z",
    contact_id: "con_0008",
    service_location_id: "loc_0007",
    work_order_id: "wo_0007",
    assigned_employee_id: "emp_0006",
    resolved_at: null,
    closed_at: null,
    related_document_ids: [],
    messages: [
      {
        id: "msg_0007",
        support_ticket_id: "tkt_0007",
        direction: "inbound",
        channel: "portal",
        body: "Please send a technician. Rooftop unit is down.",
        status: "sent",
        sent_at: "2026-04-08T09:30:00Z",
        created_at: "2026-04-08T09:30:00Z",
        updated_at: "2026-04-08T09:30:00Z",
        author_employee_id: null,
        author_contact_id: "con_0008",
        requires_approval: false,
        approval_request_id: null,
        approval_request: null,
      },
      {
        id: "msg_0016",
        support_ticket_id: "tkt_0007",
        direction: "outbound",
        channel: "email",
        body: SUGGESTED_BODY,
        status: "pending_approval",
        sent_at: "2026-10-28T15:05:00Z",
        created_at: "2026-10-28T15:05:00Z",
        updated_at: "2026-10-28T15:05:00Z",
        author_employee_id: "emp_0006",
        author_contact_id: null,
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
      },
    ],
    ...overrides,
  };
}

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function actorOn(init: RequestInit | undefined): string | null {
  return new Headers(init?.headers).get(LABORATORY_ACTOR_HEADER);
}

function calledUrls(): string[] {
  return vi.mocked(fetch).mock.calls.map((call) => String(call[0]));
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("review screen", () => {
  it("shows an empty suggestion and does not offer a send control", async () => {
    const empty = ticket({
      id: "tkt_0015",
      customer_id: "cust_0011",
      subject: "Service request related to wo_0015",
      status: "reopened",
      messages: [
        {
          id: "msg_0015",
          support_ticket_id: "tkt_0015",
          direction: "inbound",
          channel: "portal",
          body: "Please send a technician. Rooftop unit is down.",
          status: "sent",
          sent_at: "2026-04-16T09:30:00Z",
          created_at: "2026-04-16T09:30:00Z",
          updated_at: "2026-04-16T09:30:00Z",
          author_employee_id: null,
          author_contact_id: "con_0018",
          requires_approval: false,
          approval_request_id: null,
          approval_request: null,
        },
      ],
    });
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/customers/cust_0011")) {
        return jsonResponse({ id: "cust_0011", legal_name: "Example Customer LLC" });
      }
      return jsonResponse(empty);
    });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    render(<App />);

    await user.clear(screen.getByLabelText("Inquiry"));
    await user.type(screen.getByLabelText("Inquiry"), "tkt_0015");
    await user.click(screen.getByRole("button", { name: "Open inquiry" }));

    expect(await screen.findByRole("heading", { name: "No suggested reply" })).toBeInTheDocument();
    expect(screen.getByText(/Rooftop unit is down/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /send|deliver|email|sms/i })).toBeNull();
    expect(screen.queryByRole("button", { name: "Approve reply" })).toBeNull();
    expect(calledUrls().some((url) => url.includes("draft-replies"))).toBe(false);
  });

  it.each(["approved", "rejected"] as const)(
    "records %s against the local decision route and leaves the reply unsent",
    async (decision) => {
      const pending = ticket();
      const decided = ticket();
      const approval = decided.messages[1].approval_request;
      if (!approval) {
        throw new Error("fixture approval is missing");
      }
      approval.status = decision;
      approval.reviewer_employee_id = "emp_0001";
      approval.decision_notes =
        decision === "approved" ? "Overtime approved." : "Hold the visit.";
      const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        if (init?.method === "POST") {
          return jsonResponse({ ...approval });
        }
        if (url.endsWith("/customers/cust_0004")) {
          return jsonResponse({
            id: "cust_0004",
            legal_name: "Cottonwood Office Commons LLC",
          });
        }
        const seenDecision = fetchMock.mock.calls.some(
          (call) => call[1]?.method === "POST",
        );
        return jsonResponse(seenDecision ? decided : pending);
      });
      vi.stubGlobal("fetch", fetchMock);
      const user = userEvent.setup();
      render(<App />);
      await user.click(screen.getByRole("button", { name: "Open inquiry" }));
      expect(await screen.findByText(SUGGESTED_BODY)).toBeInTheDocument();
      expect(screen.getByText("This reply has not been sent.")).toBeInTheDocument();
      await user.type(
        screen.getByLabelText("Decision note"),
        decision === "approved" ? "Overtime approved." : "Hold the visit.",
      );
      await user.click(
        screen.getByRole("button", {
          name: decision === "approved" ? "Approve reply" : "Reject reply",
        }),
      );

      const verb = decision === "approved" ? "Approved" : "Rejected";
      expect(await screen.findByText(`${verb}. The message was not sent.`)).toBeInTheDocument();
      expect(screen.getByText("This reply has not been sent.")).toBeInTheDocument();
      expect(screen.getByText(/pending_approval/)).toBeInTheDocument();
      expect(screen.queryByRole("button", { name: /send|deliver|email|sms/i })).toBeNull();

      const post = fetchMock.mock.calls.find((call) => call[1]?.method === "POST");
      expect(post).toBeTruthy();
      expect(String(post?.[0])).toBe("/api/v1/approval-requests/apr_0001/decisions");
      expect(actorOn(post?.[1])).toBe("emp_0001");
      expect(JSON.parse(String(post?.[1]?.body))).toEqual({
        decision,
        note: decision === "approved" ? "Overtime approved." : "Hold the visit.",
      });
      expect(calledUrls().some((url) => /draft-replies|smtp|twilio|sendgrid/i.test(url))).toBe(
        false,
      );
    },
  );

  it("treats anonymous access as unauthorized and omits the actor header", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      if (init?.method === "POST") {
        throw new Error(`anonymous open must not post ${String(input)}`);
      }
      return jsonResponse(
        { error: { code: "unauthenticated", message: "a laboratory actor is required" } },
        401,
      );
    });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    render(<App />);
    await user.click(screen.getByRole("radio", { name: /Anonymous/ }));
    await user.click(screen.getByRole("button", { name: "Open inquiry" }));

    expect(
      await screen.findByRole("alert"),
    ).toHaveTextContent("Unauthorized. a laboratory actor is required");
    expect(screen.queryByRole("heading", { name: "Inbound inquiry" })).toBeNull();
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(actorOn(fetchMock.mock.calls[0][1])).toBeNull();
  });

  it("shows the API denial when a non-approver tries to decide", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      if (init?.method === "POST") {
        return jsonResponse(
          { error: { code: "forbidden", message: "writes are denied" } },
          403,
        );
      }
      const url = String(input);
      if (url.endsWith("/customers/cust_0004")) {
        return jsonResponse({
          id: "cust_0004",
          legal_name: "Cottonwood Office Commons LLC",
        });
      }
      return jsonResponse(ticket());
    });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    render(<App />);
    await user.click(screen.getByRole("radio", { name: /Elena Voss/ }));
    await user.click(screen.getByRole("button", { name: "Open inquiry" }));
    await user.click(await screen.findByRole("button", { name: "Approve reply" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "This actor cannot approve or reject the suggested reply. writes are denied",
    );
    expect(screen.queryByText(/The message was not sent/)).toBeNull();
    const post = fetchMock.mock.calls.find((call) => call[1]?.method === "POST");
    expect(actorOn(post?.[1])).toBe("emp_0004");
    expect(screen.getByText(SUGGESTED_BODY)).toBeInTheDocument();
  });
});
