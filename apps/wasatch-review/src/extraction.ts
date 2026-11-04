import type { DocumentExtraction } from "./types";

const AWAITING_REVIEW_STATUSES = new Set([
  "needs_review",
  "pending",
  "succeeded",
  "failed",
]);

export function canDecideExtraction(
  extraction: DocumentExtraction | null,
): boolean {
  if (!extraction) {
    return false;
  }
  return (
    AWAITING_REVIEW_STATUSES.has(extraction.status) &&
    extraction.reviewed_at === null &&
    extraction.reviewed_by_employee_id === null
  );
}

export function extractionFields(
  extraction: DocumentExtraction,
): string {
  return JSON.stringify(extraction.extracted_fields ?? {}, null, 2);
}
