import { actorHeaderValue, LABORATORY_ACTOR_HEADER } from "./actors";
import type {
  ActorChoice,
  ApprovalRequest,
  CustomerDetail,
  InquiryView,
  ReviewDecision,
  SupportTicket,
} from "./types";

const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

export function ticketPath(ticketId: string): string {
  return `/api/v1/support-tickets/${encodeURIComponent(ticketId)}`;
}

export function customerPath(customerId: string): string {
  return `/api/v1/customers/${encodeURIComponent(customerId)}`;
}

export function decisionPath(approvalId: string): string {
  return `/api/v1/approval-requests/${encodeURIComponent(approvalId)}/decisions`;
}

export function reviewErrorText(error: unknown): string {
  if (!(error instanceof ApiError)) {
    return error instanceof Error ? error.message : "The request failed.";
  }
  if (error.status === 401 || error.code === "unauthenticated") {
    return `Unauthorized. ${error.message}`;
  }
  if (error.status === 403 || error.code === "forbidden") {
    return `This actor cannot approve or reject the suggested reply. ${error.message}`;
  }
  return error.message;
}

function requestHeaders(actor: ActorChoice, jsonBody: boolean): Headers {
  const headers = new Headers({ Accept: "application/json" });
  const actorId = actorHeaderValue(actor);
  if (actorId) {
    headers.set(LABORATORY_ACTOR_HEADER, actorId);
  }
  if (jsonBody) {
    headers.set("Content-Type", "application/json");
  }
  return headers;
}

async function parseError(response: Response): Promise<ApiError> {
  let code = "request_failed";
  let message = response.statusText || "The API request failed.";
  try {
    const body = (await response.json()) as {
      error?: { code?: string; message?: string };
    };
    if (body.error?.code) {
      code = body.error.code;
    }
    if (body.error?.message) {
      message = body.error.message;
    }
  } catch {
    // The body was not the API error envelope.
  }
  return new ApiError(response.status, code, message);
}

async function requestJson<T>(
  path: string,
  actor: ActorChoice,
  init?: { method?: string; body?: string },
): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    method: init?.method ?? "GET",
    headers: requestHeaders(actor, init?.body !== undefined),
    body: init?.body,
  });
  if (!response.ok) {
    throw await parseError(response);
  }
  return (await response.json()) as T;
}

export async function loadInquiry(
  ticketId: string,
  actor: ActorChoice,
): Promise<InquiryView> {
  const ticket = await requestJson<SupportTicket>(ticketPath(ticketId), actor);
  let customerName: string | null = null;
  try {
    const customer = await requestJson<CustomerDetail>(
      customerPath(ticket.customer_id),
      actor,
    );
    customerName = customer.legal_name;
  } catch (error) {
    if (error instanceof ApiError && (error.status === 401 || error.status === 403)) {
      throw error;
    }
    customerName = null;
  }
  return { ticket, customerName };
}

export async function decideSuggestedReply(
  approvalId: string,
  decision: ReviewDecision,
  note: string,
  actor: ActorChoice,
): Promise<ApprovalRequest> {
  const trimmed = note.trim();
  return requestJson<ApprovalRequest>(decisionPath(approvalId), actor, {
    method: "POST",
    body: JSON.stringify({
      decision,
      note: trimmed.length > 0 ? trimmed : null,
    }),
  });
}
