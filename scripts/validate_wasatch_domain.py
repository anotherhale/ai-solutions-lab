"""Validate Wasatch domain schemas, references, and business invariants."""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from jsonschema_lite import SchemaError, SchemaRegistry, validate_instance

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_ROOT = ROOT / "data" / "schemas" / "v1"
VALID_DIR = ROOT / "data" / "fixtures" / "valid"
QUALITY_DIR = ROOT / "data" / "fixtures" / "quality-issues"
PROCEDURES_DIR = ROOT / "data" / "documents" / "procedures"
PROCEDURE_LABEL = "Synthetic laboratory procedure for Wasatch Business Systems."
PROCEDURE_CORPUS = "wasatch-procedures"
AS_OF = date(2026, 11, 3)

FIXTURE_FILES = {
    "role": "roles.json",
    "team": "teams.json",
    "employee": "employees.json",
    "customer": "customers.json",
    "contact": "contacts.json",
    "service_location": "service_locations.json",
    "equipment": "equipment.json",
    "work_order": "work_orders.json",
    "work_order_task": "work_order_tasks.json",
    "appointment": "appointments.json",
    "invoice": "invoices.json",
    "invoice_line": "invoice_lines.json",
    "payment": "payments.json",
    "document": "documents.json",
    "document_version": "document_versions.json",
    "document_extraction": "document_extractions.json",
    "support_ticket": "support_tickets.json",
    "message": "messages.json",
    "interaction": "interactions.json",
    "approval_request": "approval_requests.json",
    "audit_event": "audit_events.json",
}

EXPECTED_MIN_COUNTS = {
    "customer": 15,
    "contact": 25,
    "service_location": 20,
    "employee": 15,
    "equipment": 30,
    "work_order": 40,
    "appointment": 25,
    "invoice": 30,
    "invoice_line": 40,
    "payment": 20,
    "document": 30,
    "support_ticket": 15,
    "approval_request": 10,
    "audit_event": 50,
}

FOREIGN_KEYS = [
    ("contact", "customer_id", "customer"),
    ("customer", "primary_contact_id", "contact"),
    ("service_location", "customer_id", "customer"),
    ("employee", "role_id", "role"),
    ("employee", "team_id", "team"),
    ("team", "lead_employee_id", "employee"),
    ("equipment", "customer_id", "customer"),
    ("equipment", "service_location_id", "service_location"),
    ("work_order", "customer_id", "customer"),
    ("work_order", "service_location_id", "service_location"),
    ("work_order", "support_ticket_id", "support_ticket"),
    ("work_order", "requested_by_contact_id", "contact"),
    ("work_order", "invoice_id", "invoice"),
    ("work_order_task", "work_order_id", "work_order"),
    ("work_order_task", "assigned_employee_id", "employee"),
    ("appointment", "work_order_id", "work_order"),
    ("appointment", "service_location_id", "service_location"),
    ("appointment", "assigned_employee_id", "employee"),
    ("appointment", "replaces_appointment_id", "appointment"),
    ("invoice", "customer_id", "customer"),
    ("invoice", "work_order_id", "work_order"),
    ("invoice_line", "invoice_id", "invoice"),
    ("invoice_line", "work_order_id", "work_order"),
    ("payment", "invoice_id", "invoice"),
    ("payment", "received_by_employee_id", "employee"),
    ("document", "customer_id", "customer"),
    ("document", "service_location_id", "service_location"),
    ("document", "work_order_id", "work_order"),
    ("document", "invoice_id", "invoice"),
    ("document", "current_version_id", "document_version"),
    ("document", "uploaded_by_employee_id", "employee"),
    ("document_version", "document_id", "document"),
    ("document_version", "created_by_employee_id", "employee"),
    ("document_extraction", "document_id", "document"),
    ("document_extraction", "document_version_id", "document_version"),
    ("document_extraction", "reviewed_by_employee_id", "employee"),
    ("support_ticket", "customer_id", "customer"),
    ("support_ticket", "contact_id", "contact"),
    ("support_ticket", "service_location_id", "service_location"),
    ("support_ticket", "work_order_id", "work_order"),
    ("support_ticket", "assigned_employee_id", "employee"),
    ("message", "support_ticket_id", "support_ticket"),
    ("message", "author_employee_id", "employee"),
    ("message", "author_contact_id", "contact"),
    ("message", "approval_request_id", "approval_request"),
    ("interaction", "customer_id", "customer"),
    ("interaction", "contact_id", "contact"),
    ("interaction", "support_ticket_id", "support_ticket"),
    ("interaction", "work_order_id", "work_order"),
    ("interaction", "employee_id", "employee"),
    ("approval_request", "requested_by_employee_id", "employee"),
    ("approval_request", "reviewer_employee_id", "employee"),
    ("audit_event", "actor_employee_id", "employee"),
    ("audit_event", "approval_request_id", "approval_request"),
]

ARRAY_FOREIGN_KEYS = [
    ("work_order", "assigned_employee_ids", "employee"),
    ("work_order", "equipment_ids", "equipment"),
    ("support_ticket", "related_document_ids", "document"),
]


def error(errors: list[str], message: str) -> None:
    errors.append(message)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def amount(value: dict) -> Decimal:
    return Decimal(value["amount"])


def parse_date(value: str) -> date:
    return date.fromisoformat(value)


def parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def load_valid_fixtures(errors: list[str]) -> dict[str, list[dict]]:
    fixtures: dict[str, list[dict]] = {}
    registry = SchemaRegistry(SCHEMA_ROOT)
    for entity, filename in FIXTURE_FILES.items():
        path = VALID_DIR / filename
        if not path.is_file():
            error(errors, f"Missing fixture file: {path.relative_to(ROOT)}")
            fixtures[entity] = []
            continue
        payload = load_json(path)
        if payload.get("synthetic") is not True:
            error(errors, f"{filename} must set synthetic to true")
        records = payload.get("records")
        if not isinstance(records, list):
            error(errors, f"{filename} records must be an array")
            fixtures[entity] = []
            continue
        schema_rel = payload.get("schema")
        if not schema_rel:
            error(errors, f"{filename} missing schema reference")
            fixtures[entity] = records
            continue
        schema_path = SCHEMA_ROOT / schema_rel
        schema = registry.load(schema_path)
        for index, record in enumerate(records):
            try:
                validate_instance(
                    record,
                    schema,
                    registry=registry,
                    schema_path=schema_path,
                    path=f"{filename}.records[{index}]",
                )
            except SchemaError as exc:
                error(errors, str(exc))
        fixtures[entity] = records
    return fixtures


def index_records(
    fixtures: dict[str, list[dict]], errors: list[str]
) -> dict[str, dict[str, dict]]:
    by_id: dict[str, dict[str, dict]] = defaultdict(dict)
    seen: dict[str, str] = {}
    for entity, records in fixtures.items():
        for record in records:
            identifier = record.get("id")
            if not identifier:
                error(errors, f"{entity} record missing id")
                continue
            if identifier in seen:
                error(
                    errors,
                    f"duplicate identifier {identifier} in {seen[identifier]}"
                    f" and {entity}",
                )
            seen[identifier] = entity
            by_id[entity][identifier] = record
    return by_id


def check_foreign_keys(
    fixtures: dict[str, list[dict]],
    by_id: dict[str, dict[str, dict]],
    errors: list[str],
) -> None:
    for entity, field, target in FOREIGN_KEYS:
        for record in fixtures.get(entity, []):
            value = record.get(field)
            if value and value not in by_id.get(target, {}):
                error(
                    errors,
                    f"{record.get('id')}.{field} -> missing {target} {value}",
                )
    for entity, field, target in ARRAY_FOREIGN_KEYS:
        for record in fixtures.get(entity, []):
            for value in record.get(field, []):
                if value not in by_id.get(target, {}):
                    error(
                        errors,
                        f"{record.get('id')}.{field} -> missing {target} {value}",
                    )


def check_counts(fixtures: dict[str, list[dict]], errors: list[str]) -> None:
    for entity, minimum in EXPECTED_MIN_COUNTS.items():
        actual = len(fixtures.get(entity, []))
        if actual < minimum:
            error(
                errors,
                f"{entity} count {actual} is below expected minimum {minimum}",
            )


def check_customer_consistency(
    fixtures: dict[str, list[dict]],
    by_id: dict[str, dict[str, dict]],
    errors: list[str],
) -> None:
    for customer in fixtures["customer"]:
        primary = customer.get("primary_contact_id")
        if not primary:
            continue
        contact = by_id["contact"].get(primary)
        if contact and contact["customer_id"] != customer["id"]:
            error(
                errors,
                f"{customer['id']} primary contact belongs to another customer",
            )
    for equipment in fixtures["equipment"]:
        location = by_id["service_location"].get(equipment["service_location_id"])
        if location and location["customer_id"] != equipment["customer_id"]:
            error(
                errors,
                f"{equipment['id']} customer does not match location customer",
            )
    for work_order in fixtures["work_order"]:
        location = by_id["service_location"].get(work_order["service_location_id"])
        if location and location["customer_id"] != work_order["customer_id"]:
            error(errors, f"{work_order['id']} location/customer mismatch")
        contact_id = work_order.get("requested_by_contact_id")
        if contact_id:
            contact = by_id["contact"].get(contact_id)
            if contact and contact["customer_id"] != work_order["customer_id"]:
                error(errors, f"{work_order['id']} requester/customer mismatch")
        for equipment_id in work_order.get("equipment_ids", []):
            asset = by_id["equipment"].get(equipment_id)
            if (
                asset
                and asset["service_location_id"] != work_order["service_location_id"]
            ):
                error(
                    errors,
                    f"{work_order['id']} equipment {equipment_id} is at another site",
                )


def check_work_orders(fixtures: dict[str, list[dict]], errors: list[str]) -> None:
    for work_order in fixtures["work_order"]:
        status = work_order["status"]
        identifier = work_order["id"]
        if status in {"completed", "invoiced"}:
            if not work_order.get("completed_at") or not work_order.get(
                "completion_notes"
            ):
                error(errors, f"{identifier} completed work is missing notes")
        if status == "invoiced" and not work_order.get("invoice_id"):
            error(errors, f"{identifier} invoiced work missing invoice_id")
        if status == "cancelled" and not work_order.get("cancelled_reason"):
            error(errors, f"{identifier} cancelled without reason")
        if status == "reopened" and not work_order.get("reopen_reason"):
            error(errors, f"{identifier} reopened without reason")
    for task in fixtures["work_order_task"]:
        if task["status"] == "blocked" and not task.get("blocked_reason"):
            error(errors, f"{task['id']} blocked without reason")


def check_appointments(
    fixtures: dict[str, list[dict]],
    by_id: dict[str, dict[str, dict]],
    errors: list[str],
) -> None:
    active_status = {"scheduled", "confirmed", "in_progress"}
    intervals: dict[str, list[tuple[datetime, datetime, str]]] = defaultdict(list)
    for appointment in fixtures["appointment"]:
        start = parse_datetime(appointment["start_at"])
        end = parse_datetime(appointment["end_at"])
        if start >= end:
            error(errors, f"{appointment['id']} start_at must be before end_at")
        work_order = by_id["work_order"].get(appointment["work_order_id"])
        if (
            work_order
            and work_order["service_location_id"] != appointment["service_location_id"]
        ):
            error(errors, f"{appointment['id']} location does not match work order")
        if appointment["status"] in active_status:
            intervals[appointment["assigned_employee_id"]].append(
                (start, end, appointment["id"])
            )
    for employee_id, windows in intervals.items():
        ordered = sorted(windows)
        for index in range(1, len(ordered)):
            previous = ordered[index - 1]
            current = ordered[index]
            if previous[1] > current[0]:
                error(
                    errors,
                    f"overlapping appointments {previous[2]} and {current[2]}"
                    f" for {employee_id}",
                )


def check_invoices(fixtures: dict[str, list[dict]], errors: list[str]) -> None:
    lines_by_invoice: dict[str, list[dict]] = defaultdict(list)
    for line in fixtures["invoice_line"]:
        qty = Decimal(str(line["quantity"]))
        expected = (qty * amount(line["unit_price"])).quantize(Decimal("0.01"))
        if expected != amount(line["line_total"]):
            error(errors, f"{line['id']} line_total does not equal quantity * price")
        lines_by_invoice[line["invoice_id"]].append(line)

    posted_by_invoice: dict[str, Decimal] = defaultdict(lambda: Decimal("0.00"))
    for payment in fixtures["payment"]:
        if payment["status"] == "posted":
            posted_by_invoice[payment["invoice_id"]] += amount(payment["amount"])

    for invoice in fixtures["invoice"]:
        identifier = invoice["id"]
        subtotal = amount(invoice["subtotal"])
        tax = amount(invoice["tax"])
        adjustments = amount(invoice["adjustments"])
        total = amount(invoice["total"])
        paid = amount(invoice["amount_paid"])
        balance = amount(invoice["balance"])
        if total != (subtotal + tax + adjustments):
            error(errors, f"{identifier} total does not reconcile")
        if balance != total - paid:
            error(errors, f"{identifier} balance does not equal total minus paid")
        line_sum = sum(
            (amount(line["line_total"]) for line in lines_by_invoice[identifier]),
            Decimal("0.00"),
        )
        if line_sum != subtotal:
            error(errors, f"{identifier} subtotal does not match invoice lines")
        posted = posted_by_invoice[identifier].quantize(Decimal("0.01"))
        if posted != paid:
            error(errors, f"{identifier} amount_paid does not match posted payments")
        if posted > total:
            error(errors, f"{identifier} posted payments exceed total")
        status = invoice["status"]
        due = parse_date(invoice["due_on"]) if invoice.get("due_on") else None
        if status == "paid" and (paid != total or balance != 0):
            error(errors, f"{identifier} paid invoice is not fully settled")
        if status == "draft" and paid != 0:
            error(errors, f"{identifier} draft invoice has payments")
        if status == "issued" and (
            paid != 0 or due is None or due < AS_OF or not invoice.get("issued_on")
        ):
            error(errors, f"{identifier} issued invoice is inconsistent")
        if status == "partially_paid" and not (
            0 < paid < total and due and due >= AS_OF
        ):
            error(errors, f"{identifier} partially paid invoice is inconsistent")
        if status == "overdue" and not (balance > 0 and due and due < AS_OF):
            error(errors, f"{identifier} overdue invoice is inconsistent")
        if status == "voided" and not invoice.get("voided_on"):
            error(errors, f"{identifier} voided invoice missing voided_on")


def check_documents(
    fixtures: dict[str, list[dict]],
    by_id: dict[str, dict[str, dict]],
    errors: list[str],
) -> None:
    for document in fixtures["document"]:
        current = document.get("current_version_id")
        if not current:
            continue
        version = by_id["document_version"].get(current)
        if version and version["document_id"] != document["id"]:
            error(errors, f"{document['id']} current version belongs elsewhere")
        if document["source"] != "generated" and document["untrusted"] is not True:
            error(errors, f"{document['id']} external document must be untrusted")
    for extraction in fixtures["document_extraction"]:
        version = by_id["document_version"].get(extraction["document_version_id"])
        if version and version["document_id"] != extraction["document_id"]:
            error(errors, f"{extraction['id']} version provenance is broken")
        if extraction["status"] in {"accepted", "rejected"}:
            if not extraction.get("reviewed_by_employee_id") or not extraction.get(
                "reviewed_at"
            ):
                error(
                    errors, f"{extraction['id']} reviewed extraction missing reviewer"
                )


def check_approvals_and_messages(
    fixtures: dict[str, list[dict]], errors: list[str]
) -> None:
    approvals = {record["id"]: record for record in fixtures["approval_request"]}
    for approval in fixtures["approval_request"]:
        identifier = approval["id"]
        status = approval["status"]
        history = approval.get("decision_history") or []
        if status == "pending" and history:
            # History may be empty while pending; non-empty is allowed.
            pass
        if status != "pending" and not history:
            error(errors, f"{identifier} must retain decision history")
        if status in {"approved", "rejected"} and not approval.get("decided_at"):
            error(errors, f"{identifier} decided without decided_at")
        if status == "executed" and not approval.get("executed_at"):
            error(errors, f"{identifier} executed without executed_at")
        if status == "executed" and not any(
            item.get("to_status") == "approved" for item in history
        ):
            error(errors, f"{identifier} executed without an approved step")
    for message in fixtures["message"]:
        if message.get("requires_approval") and message["status"] == "sent":
            approval = approvals.get(message.get("approval_request_id"))
            if not approval or approval["status"] != "executed":
                error(
                    errors,
                    f"{message['id']} sent without an executed approval",
                )


def check_quality_issue_separation(errors: list[str]) -> None:
    if not QUALITY_DIR.is_dir():
        error(errors, "quality-issues directory is missing")
        return
    valid_names = set(FIXTURE_FILES.values()) | {"manifest.json"}
    for path in QUALITY_DIR.glob("*.json"):
        if path.name in valid_names:
            error(
                errors,
                f"quality-issues/{path.name} collides with a valid fixture name",
            )
        payload = load_json(path)
        if payload.get("synthetic") is not True:
            error(errors, f"quality-issues/{path.name} must be labeled synthetic")
        if payload.get("quality_issue") is not True:
            error(
                errors,
                f"quality-issues/{path.name} must set quality_issue to true",
            )


def check_unique_business_keys(
    fixtures: dict[str, list[dict]], errors: list[str]
) -> None:
    def unique(entity: str, field: str) -> None:
        seen: dict[str, str] = {}
        for record in fixtures[entity]:
            value = record.get(field)
            if value in seen:
                error(errors, f"duplicate {field} {value} on {entity}")
            elif value:
                seen[value] = record["id"]

    unique("customer", "account_number")
    unique("employee", "employee_number")
    unique("equipment", "asset_tag")


def check_procedure_corpus(errors: list[str]) -> None:
    """The procedure catalog is synthetic and is not a replacement fixture set."""

    catalog_path = PROCEDURES_DIR / "catalog.json"
    if not catalog_path.is_file():
        error(
            errors, "Missing procedure catalog: data/documents/procedures/catalog.json"
        )
        return
    if VALID_DIR in catalog_path.parents:
        error(errors, "procedure catalog must not live under data/fixtures/valid")
    payload = json.loads(catalog_path.read_text(encoding="utf-8"))
    if payload.get("synthetic") is not True:
        error(errors, "procedure catalog must set synthetic to true")
    if payload.get("corpus") != PROCEDURE_CORPUS:
        error(errors, f"procedure catalog corpus must be {PROCEDURE_CORPUS}")
    pages = payload.get("pages")
    if not isinstance(pages, list) or not pages:
        error(errors, "procedure catalog pages must be a non-empty array")
        return
    seen: set[str] = set()
    for page in pages:
        if not isinstance(page, dict):
            error(errors, "procedure page must be an object")
            continue
        page_id = page.get("id")
        relative = page.get("path")
        if not _procedure_id(page_id):
            error(errors, f"procedure page id is invalid: {page_id}")
        elif page_id in seen:
            error(errors, f"duplicate procedure page id {page_id}")
        else:
            seen.add(page_id)
        if not isinstance(relative, str) or Path(relative).name != relative:
            error(errors, f"procedure path must be a file name: {relative}")
            continue
        file_path = PROCEDURES_DIR / relative
        if not file_path.is_file():
            error(errors, f"missing procedure page {relative}")
            continue
        lines = file_path.read_text(encoding="utf-8").lstrip("\ufeff").splitlines()
        if not lines or lines[0].strip() != PROCEDURE_LABEL:
            error(errors, f"{relative} must be labeled synthetic")


def _procedure_id(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 9
        and value.startswith("proc_")
        and value[5:].isdigit()
    )


def main() -> int:
    errors: list[str] = []
    if not VALID_DIR.is_dir():
        print("Missing data/fixtures/valid")
        return 1
    fixtures = load_valid_fixtures(errors)
    by_id = index_records(fixtures, errors)
    check_counts(fixtures, errors)
    check_unique_business_keys(fixtures, errors)
    check_foreign_keys(fixtures, by_id, errors)
    check_customer_consistency(fixtures, by_id, errors)
    check_work_orders(fixtures, errors)
    check_appointments(fixtures, by_id, errors)
    check_invoices(fixtures, errors)
    check_documents(fixtures, by_id, errors)
    check_approvals_and_messages(fixtures, errors)
    check_quality_issue_separation(errors)
    check_procedure_corpus(errors)

    if errors:
        print("Wasatch domain validation failed:")
        for item in errors:
            print(f"- {item}")
        return 1

    counts = {entity: len(records) for entity, records in fixtures.items()}
    print("Wasatch domain fixtures validated.")
    print(json.dumps(counts, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
