export interface ApprovalDecision {
  at: string;
  actor_employee_id: string;
  from_status: string;
  to_status: string;
  note: string | null;
}

export interface ApprovalRequest {
  id: string;
  action_type: string;
  status: string;
  requested_by_employee_id: string;
  subject_type: string;
  subject_id: string;
  rationale: string;
  requested_at: string;
  created_at: string;
  updated_at: string;
  decision_history: ApprovalDecision[];
  reviewer_employee_id: string | null;
  decision_notes: string | null;
  decided_at: string | null;
  executed_at: string | null;
}

export interface TicketMessage {
  id: string;
  support_ticket_id: string;
  direction: string;
  channel: string;
  body: string;
  status: string;
  sent_at: string;
  created_at: string;
  updated_at: string;
  author_employee_id: string | null;
  author_contact_id: string | null;
  requires_approval: boolean;
  approval_request_id: string | null;
  approval_request: ApprovalRequest | null;
}

export interface SupportTicket {
  id: string;
  customer_id: string;
  status: string;
  priority: string;
  channel: string;
  subject: string;
  opened_at: string;
  created_at: string;
  updated_at: string;
  contact_id: string | null;
  service_location_id: string | null;
  work_order_id: string | null;
  assigned_employee_id: string | null;
  resolved_at: string | null;
  closed_at: string | null;
  related_document_ids: string[];
  messages: TicketMessage[];
}

export interface CustomerDetail {
  id: string;
  legal_name: string;
}

export type ActorChoice = "emp_0001" | "emp_0004" | "anonymous";

export type ReviewDecision = "approved" | "rejected";

export interface InquiryView {
  ticket: SupportTicket;
  customerName: string | null;
}
