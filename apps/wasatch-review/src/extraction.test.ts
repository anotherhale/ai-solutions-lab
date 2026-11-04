import { describe, expect, it } from "vitest";
import { canDecideExtraction, extractionFields } from "./extraction";
import type { DocumentExtraction } from "./types";

function extraction(
  overrides: Partial<DocumentExtraction> = {},
): DocumentExtraction {
  return {
    id: "dx_0003",
    document_id: "doc_0003",
    document_version_id: "dv_0003",
    status: "needs_review",
    extractor: "model",
    confidence: 0.7,
    extracted_fields: {
      vendor_name: "Synthetic Vendor",
      invoice_number: "V-0003",
    },
    extracted_at: "2026-06-02T13:00:00Z",
    created_at: "2026-06-02T13:00:00Z",
    updated_at: "2026-06-02T13:00:00Z",
    reviewed_by_employee_id: null,
    reviewed_at: null,
    review_notes: null,
    ...overrides,
  };
}

describe("canDecideExtraction", () => {
  it("allows an awaiting-review extraction without a recorded reviewer", () => {
    expect(canDecideExtraction(extraction())).toBe(true);
  });

  it("does not allow an already reviewed extraction", () => {
    expect(
      canDecideExtraction(
        extraction({
          status: "accepted",
          reviewed_by_employee_id: "emp_0001",
          reviewed_at: "2026-06-08T10:00:00Z",
        }),
      ),
    ).toBe(false);
  });
});

describe("extractionFields", () => {
  it("formats extracted fields for display", () => {
    expect(extractionFields(extraction())).toContain('"invoice_number": "V-0003"');
  });
});
