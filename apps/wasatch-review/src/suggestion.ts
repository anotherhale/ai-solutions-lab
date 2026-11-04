import type { TicketMessage } from "./types";

const WAITING_STATUSES = new Set(["draft", "pending_approval"]);

export function suggestedReply(messages: readonly TicketMessage[]): TicketMessage | null {
  const waiting = messages.filter(
    (message) =>
      message.direction === "outbound" && WAITING_STATUSES.has(message.status),
  );
  return (
    waiting.find((message) => message.status === "pending_approval") ??
    waiting[0] ??
    null
  );
}

export function inboundMessages(
  messages: readonly TicketMessage[],
): TicketMessage[] {
  return messages.filter((message) => message.direction === "inbound");
}

export function canDecideSuggestion(message: TicketMessage | null): boolean {
  const approval = message?.approval_request;
  if (!message || !approval) {
    return false;
  }
  if (message.status === "sent") {
    return false;
  }
  return (
    approval.status === "pending" &&
    approval.action_type === "send_customer_message" &&
    approval.executed_at === null
  );
}
