import { useState, type FormEvent } from "react";
import { LABORATORY_ACTORS } from "./actors";
import { decideSuggestedReply, loadInquiry, reviewErrorText } from "./api";
import { canDecideSuggestion, inboundMessages, suggestedReply } from "./suggestion";
import type { ActorChoice, InquiryView, ReviewDecision, TicketMessage } from "./types";

export function App() {
  const [actor, setActor] = useState<ActorChoice>("emp_0001");
  const [ticketId, setTicketId] = useState("tkt_0007");
  const [inquiry, setInquiry] = useState<InquiryView | null>(null);
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [outcome, setOutcome] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [deciding, setDeciding] = useState<ReviewDecision | null>(null);

  function selectActor(next: ActorChoice) {
    setActor(next);
    setInquiry(null);
    setNote("");
    setError(null);
    setOutcome(null);
  }

  async function openInquiry(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const id = ticketId.trim();
    setInquiry(null);
    setOutcome(null);
    setNote("");
    if (!id) {
      setError("Enter an inquiry id.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      setInquiry(await loadInquiry(id, actor));
    } catch (caught) {
      setError(reviewErrorText(caught));
    } finally {
      setLoading(false);
    }
  }

  async function recordDecision(decision: ReviewDecision) {
    const suggestion = inquiry ? suggestedReply(inquiry.ticket.messages) : null;
    const approval = suggestion?.approval_request;
    if (!inquiry || !approval || !canDecideSuggestion(suggestion)) {
      return;
    }
    setDeciding(decision);
    setError(null);
    setOutcome(null);
    try {
      await decideSuggestedReply(approval.id, decision, note, actor);
      const refreshed = await loadInquiry(inquiry.ticket.id, actor);
      setInquiry(refreshed);
      const verb = decision === "approved" ? "Approved" : "Rejected";
      setOutcome(`${verb}. The message was not sent.`);
      setNote("");
    } catch (caught) {
      setError(reviewErrorText(caught));
    } finally {
      setDeciding(null);
    }
  }

  const suggestion = inquiry ? suggestedReply(inquiry.ticket.messages) : null;
  const inbound = inquiry ? inboundMessages(inquiry.ticket.messages) : [];
  const decisionReady = canDecideSuggestion(suggestion);
  const busy = loading || deciding !== null;

  return (
    <div className="page">
      <header className="masthead">
        <p className="eyebrow">Wasatch Business Systems · synthetic laboratory</p>
        <h1>Suggested reply review</h1>
        <p className="lede">
          Open one inbound inquiry, read the suggested reply, and approve or
          reject it. The decision stays in the laboratory API. This screen does
          not send the message.
        </p>
      </header>

      <form className="panel controls" onSubmit={openInquiry}>
        <fieldset>
          <legend>Laboratory actor</legend>
          <div className="actor-choices">
            {LABORATORY_ACTORS.map((option) => (
              <label key={option.id} className="actor-choice">
                <input
                  type="radio"
                  name="laboratory-actor"
                  value={option.id}
                  checked={actor === option.id}
                  onChange={() => selectActor(option.id)}
                />
                <span>
                  <strong>{option.label}</strong>
                  <span className="muted">{option.detail}</span>
                </span>
              </label>
            ))}
          </div>
        </fieldset>
        <div className="inquiry-row">
          <label htmlFor="inquiry-id">
            Inquiry
            <input
              id="inquiry-id"
              name="inquiry-id"
              value={ticketId}
              autoComplete="off"
              spellCheck={false}
              onChange={(event) => setTicketId(event.target.value)}
            />
          </label>
          <button type="submit" disabled={busy}>
            {loading ? "Opening…" : "Open inquiry"}
          </button>
        </div>
        <p className="hint">
          Synthetic examples: tkt_0007 has a suggested reply waiting on
          apr_0001. tkt_0015 has an inbound message and no suggestion.
        </p>
      </form>

      <div className="status-stack" aria-live="polite">
        {error ? (
          <p className="banner banner-alert" role="alert">
            {error}
          </p>
        ) : null}
        {outcome ? <p className="banner banner-recorded">{outcome}</p> : null}
      </div>

      {inquiry ? (
        <main className="review">
          <InquiryPanel
            inquiry={inquiry}
            inbound={inbound}
          />
          <SuggestionPanel
            suggestion={suggestion}
            note={note}
            decisionReady={decisionReady}
            deciding={deciding}
            onNote={setNote}
            onDecide={recordDecision}
          />
        </main>
      ) : null}

      <footer className="colophon">
        Laboratory screen for synthetic Wasatch data. No delivery system is
        called from this page.
      </footer>
    </div>
  );
}

function InquiryPanel({
  inquiry,
  inbound,
}: {
  inquiry: InquiryView;
  inbound: TicketMessage[];
}) {
  const ticket = inquiry.ticket;
  return (
    <section className="panel" aria-labelledby="inquiry-heading">
      <h2 id="inquiry-heading">Inbound inquiry</h2>
      <p className="subject">{ticket.subject}</p>
      <dl className="facts">
        <div>
          <dt>Inquiry</dt>
          <dd>{ticket.id}</dd>
        </div>
        <div>
          <dt>Customer</dt>
          <dd>
            {inquiry.customerName ?? "Name unavailable"}
            <span className="muted"> {ticket.customer_id}</span>
          </dd>
        </div>
        <div>
          <dt>Status</dt>
          <dd>{ticket.status}</dd>
        </div>
        <div>
          <dt>Channel</dt>
          <dd>{ticket.channel}</dd>
        </div>
      </dl>
      {inbound.length === 0 ? (
        <p className="empty-copy">No inbound message is on this inquiry.</p>
      ) : (
        <ul className="messages">
          {inbound.map((message) => (
            <li key={message.id}>
              <p className="message-meta">
                <span>{message.id}</span>
                <span>{message.channel}</span>
                <span>{message.status}</span>
              </p>
              <p className="message-body">{message.body}</p>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function SuggestionPanel({
  suggestion,
  note,
  decisionReady,
  deciding,
  onNote,
  onDecide,
}: {
  suggestion: TicketMessage | null;
  note: string;
  decisionReady: boolean;
  deciding: ReviewDecision | null;
  onNote: (value: string) => void;
  onDecide: (decision: ReviewDecision) => void;
}) {
  return (
    <section className="panel suggestion" aria-labelledby="suggestion-heading">
      <h2 id="suggestion-heading">Suggested reply</h2>
      {suggestion ? (
        <SuggestionBody
          suggestion={suggestion}
          note={note}
          decisionReady={decisionReady}
          deciding={deciding}
          onNote={onNote}
          onDecide={onDecide}
        />
      ) : (
        <div className="empty-state">
          <h3>No suggested reply</h3>
          <p>
            Nothing is waiting for review on this inquiry. Inbound messages stay
            on the left. This screen does not draft a reply and does not send
            one.
          </p>
        </div>
      )}
    </section>
  );
}

function SuggestionBody({
  suggestion,
  note,
  decisionReady,
  deciding,
  onNote,
  onDecide,
}: {
  suggestion: TicketMessage;
  note: string;
  decisionReady: boolean;
  deciding: ReviewDecision | null;
  onNote: (value: string) => void;
  onDecide: (decision: ReviewDecision) => void;
}) {
  const approval = suggestion.approval_request;
  const unsent = suggestion.status !== "sent";
  return (
    <>
      <p className="message-meta">
        <span>{suggestion.id}</span>
        <span>{suggestion.status}</span>
        {approval ? <span>{approval.id}</span> : null}
      </p>
      <blockquote className="message-body">{suggestion.body}</blockquote>
      {approval ? (
        <dl className="facts">
          <div>
            <dt>Approval</dt>
            <dd>
              {approval.status} · {approval.action_type}
            </dd>
          </div>
          <div>
            <dt>Rationale</dt>
            <dd>{approval.rationale}</dd>
          </div>
          {approval.reviewer_employee_id ? (
            <div>
              <dt>Reviewer</dt>
              <dd>{approval.reviewer_employee_id}</dd>
            </div>
          ) : null}
          {approval.decision_notes ? (
            <div>
              <dt>Decision note</dt>
              <dd>{approval.decision_notes}</dd>
            </div>
          ) : null}
        </dl>
      ) : (
        <p className="empty-copy">This suggestion has no approval request.</p>
      )}
      {unsent ? (
        <p className="unsent">This reply has not been sent.</p>
      ) : (
        <p className="unsent">This reply is already marked sent.</p>
      )}
      {decisionReady ? (
        <div className="decision">
          <label htmlFor="decision-note">
            Decision note
            <textarea
              id="decision-note"
              value={note}
              rows={3}
              onChange={(event) => onNote(event.target.value)}
            />
          </label>
          <p className="hint">
            The note is stored with the approval. It is not delivered to the
            customer.
          </p>
          <div className="decision-actions">
            <button
              type="button"
              className="approve"
              disabled={deciding !== null}
              onClick={() => onDecide("approved")}
            >
              {deciding === "approved" ? "Approving…" : "Approve reply"}
            </button>
            <button
              type="button"
              className="reject"
              disabled={deciding !== null}
              onClick={() => onDecide("rejected")}
            >
              {deciding === "rejected" ? "Rejecting…" : "Reject reply"}
            </button>
          </div>
        </div>
      ) : null}
    </>
  );
}
