import { useState, type FormEvent } from "react";
import { LABORATORY_ACTORS } from "./actors";
import {
  decideDocumentExtraction,
  decideSuggestedReply,
  extractionReviewErrorText,
  loadDocumentExtraction,
  loadInquiry,
  reviewErrorText,
} from "./api";
import { canDecideExtraction, extractionFields } from "./extraction";
import { canDecideSuggestion, inboundMessages, suggestedReply } from "./suggestion";
import type {
  ActorChoice,
  DocumentExtraction,
  ExtractionDecision,
  InquiryView,
  ReviewDecision,
  TicketMessage,
} from "./types";

export function App() {
  const [actor, setActor] = useState<ActorChoice>("emp_0001");
  const [ticketId, setTicketId] = useState("tkt_0007");
  const [extractionId, setExtractionId] = useState("dx_0003");
  const [inquiry, setInquiry] = useState<InquiryView | null>(null);
  const [extraction, setExtraction] = useState<DocumentExtraction | null>(null);
  const [note, setNote] = useState("");
  const [extractionNote, setExtractionNote] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [outcome, setOutcome] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadingExtraction, setLoadingExtraction] = useState(false);
  const [deciding, setDeciding] = useState<ReviewDecision | null>(null);
  const [decidingExtraction, setDecidingExtraction] =
    useState<ExtractionDecision | null>(null);

  function selectActor(next: ActorChoice) {
    setActor(next);
    setInquiry(null);
    setExtraction(null);
    setNote("");
    setExtractionNote("");
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

  async function openExtraction(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const id = extractionId.trim();
    setExtraction(null);
    setOutcome(null);
    setExtractionNote("");
    if (!id) {
      setError("Enter an extraction id.");
      return;
    }
    setLoadingExtraction(true);
    setError(null);
    try {
      setExtraction(await loadDocumentExtraction(id, actor));
    } catch (caught) {
      setError(extractionReviewErrorText(caught));
    } finally {
      setLoadingExtraction(false);
    }
  }

  async function recordExtractionDecision(decision: ExtractionDecision) {
    if (!extraction || !canDecideExtraction(extraction)) {
      return;
    }
    setDecidingExtraction(decision);
    setError(null);
    setOutcome(null);
    try {
      const recorded = await decideDocumentExtraction(
        extraction.id,
        decision,
        extractionNote,
        actor,
      );
      setExtraction(recorded);
      const verb = decision === "accepted" ? "Accepted" : "Rejected";
      setOutcome(`${verb}. No invoice or payment was posted.`);
      setExtractionNote("");
    } catch (caught) {
      setError(extractionReviewErrorText(caught));
    } finally {
      setDecidingExtraction(null);
    }
  }

  const suggestion = inquiry ? suggestedReply(inquiry.ticket.messages) : null;
  const inbound = inquiry ? inboundMessages(inquiry.ticket.messages) : [];
  const decisionReady = canDecideSuggestion(suggestion);
  const extractionDecisionReady = canDecideExtraction(extraction);
  const busy =
    loading ||
    loadingExtraction ||
    deciding !== null ||
    decidingExtraction !== null;

  return (
    <div className="page">
      <header className="masthead">
        <p className="eyebrow">Wasatch Business Systems · synthetic laboratory</p>
        <h1>Human review workbench</h1>
        <p className="lede">
          Open one inbound inquiry, read the suggested reply, and approve or
          reject it. Or inspect one extracted document payload and accept or
          reject it. Decisions stay in the laboratory API. This screen does not
          send messages or post financial records.
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

      <form className="panel controls" onSubmit={openExtraction}>
        <div className="inquiry-row">
          <label htmlFor="extraction-id">
            Document extraction
            <input
              id="extraction-id"
              name="extraction-id"
              value={extractionId}
              autoComplete="off"
              spellCheck={false}
              onChange={(event) => setExtractionId(event.target.value)}
            />
          </label>
          <button type="submit" disabled={busy}>
            {loadingExtraction ? "Opening…" : "Open extraction"}
          </button>
        </div>
        <p className="hint">
          Synthetic examples: dx_0003 needs review. Accepting or rejecting it
          records a human decision only; no invoice or payment is posted.
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

      {extraction ? (
        <main className="review">
          <ExtractionPanel
            extraction={extraction}
            note={extractionNote}
            decisionReady={extractionDecisionReady}
            deciding={decidingExtraction}
            onNote={setExtractionNote}
            onDecide={recordExtractionDecision}
          />
        </main>
      ) : null}

      <footer className="colophon">
        Laboratory screen for synthetic Wasatch data. No delivery system is
        called from this page, and extraction decisions do not post money.
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

function ExtractionPanel({
  extraction,
  note,
  decisionReady,
  deciding,
  onNote,
  onDecide,
}: {
  extraction: DocumentExtraction;
  note: string;
  decisionReady: boolean;
  deciding: ExtractionDecision | null;
  onNote: (value: string) => void;
  onDecide: (decision: ExtractionDecision) => void;
}) {
  return (
    <section className="panel extraction" aria-labelledby="extraction-heading">
      <h2 id="extraction-heading">Document extraction</h2>
      <dl className="facts">
        <div>
          <dt>Extraction</dt>
          <dd>{extraction.id}</dd>
        </div>
        <div>
          <dt>Document</dt>
          <dd>{extraction.document_id}</dd>
        </div>
        <div>
          <dt>Status</dt>
          <dd>{extraction.status}</dd>
        </div>
        <div>
          <dt>Confidence</dt>
          <dd>
            {extraction.confidence === null ? "not scored" : extraction.confidence}
          </dd>
        </div>
        <div>
          <dt>Extractor</dt>
          <dd>{extraction.extractor}</dd>
        </div>
        {extraction.reviewed_by_employee_id ? (
          <div>
            <dt>Reviewer</dt>
            <dd>{extraction.reviewed_by_employee_id}</dd>
          </div>
        ) : null}
        {extraction.review_notes ? (
          <div>
            <dt>Review note</dt>
            <dd>{extraction.review_notes}</dd>
          </div>
        ) : null}
      </dl>
      <p className="unsent">Extracted fields are untrusted until reviewed.</p>
      <pre className="json-fields">{extractionFields(extraction)}</pre>
      {decisionReady ? (
        <div className="decision">
          <label htmlFor="extraction-decision-note">
            Review note
            <textarea
              id="extraction-decision-note"
              value={note}
              rows={3}
              onChange={(event) => onNote(event.target.value)}
            />
          </label>
          <p className="hint">
            The decision is stored for review. It does not post an invoice,
            mark a payment, or trust future extraction output.
          </p>
          <div className="decision-actions">
            <button
              type="button"
              className="approve"
              disabled={deciding !== null}
              onClick={() => onDecide("accepted")}
            >
              {deciding === "accepted" ? "Accepting…" : "Accept extraction"}
            </button>
            <button
              type="button"
              className="reject"
              disabled={deciding !== null}
              onClick={() => onDecide("rejected")}
            >
              {deciding === "rejected" ? "Rejecting…" : "Reject extraction"}
            </button>
          </div>
        </div>
      ) : (
        <p className="empty-copy">This extraction is not awaiting review.</p>
      )}
    </section>
  );
}
