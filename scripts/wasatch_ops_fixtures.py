"""Operational synthetic records for Wasatch Business Systems fixtures."""

from __future__ import annotations

from decimal import Decimal

from wasatch_fixture_common import (
    TAX_RATE,
    TWOPLACES,
    checksum,
    day,
    id_for,
    money,
    ts,
)

TECHS = ["emp_0010", "emp_0011", "emp_0012", "emp_0013"]
EQUIPMENT_TYPES = [
    "rooftop_unit",
    "split_system",
    "air_handler",
    "heat_pump",
    "exhaust_fan",
    "controls",
    "boiler",
    "chiller",
]


def build_equipment(locations: list[dict]) -> list[dict]:
    created = ts(1, 12, 15)
    records: list[dict] = []
    number = 0
    for loc_index, location in enumerate(locations):
        extra = 1 if loc_index < 10 else 0
        for _offset in range(1 + extra):
            number += 1
            kind = EQUIPMENT_TYPES[(number - 1) % len(EQUIPMENT_TYPES)]
            record = {
                "id": id_for("eq", number),
                "customer_id": location["customer_id"],
                "service_location_id": location["id"],
                "asset_tag": f"AST-{number:04d}",
                "name": f"{kind.replace('_', ' ').title()} {number}",
                "equipment_type": kind,
                "manufacturer": ["Carrier", "Trane", "Lennox", "York"][number % 4],
                "model": f"SYN-{kind[:3].upper()}-{number:03d}",
                "serial_number": f"SN{number:06d}",
                "installed_on": f"{2016 + (number % 8)}-06-01",
                "last_service_on": day(6 + (number % 4), 5 + (number % 20)),
                "status": "needs_repair" if number in {7, 19} else "in_service",
                "created_at": created,
                "updated_at": created,
            }
            if number in {3, 8, 14, 21, 27}:
                record["next_maintenance_on"] = (
                    "2026-11-10" if number % 2 else "2026-12-02"
                )
            if number == 19:
                record["notes"] = "Compressor noise reported; parts quoted."
            records.append(record)
    return records


WO_STATUSES = (
    ["created"] * 3
    + ["scheduled"] * 4
    + ["assigned"] * 4
    + ["in_progress"] * 5
    + ["awaiting_parts"] * 3
    + ["completed"] * 8
    + ["invoiced"] * 10
    + ["cancelled"] * 2
    + ["reopened"]
)

WO_TYPES = [
    "maintenance",
    "repair",
    "inspection",
    "after_hours",
    "install",
    "callback",
]


def _primary_contact(customer_id: str) -> str:
    mapping = {
        "cust_0001": "con_0001",
        "cust_0002": "con_0004",
        "cust_0003": "con_0005",
        "cust_0004": "con_0008",
        "cust_0005": "con_0010",
        "cust_0006": "con_0011",
        "cust_0007": "con_0012",
        "cust_0008": "con_0014",
        "cust_0009": "con_0015",
        "cust_0010": "con_0016",
        "cust_0011": "con_0018",
        "cust_0012": "con_0019",
        "cust_0013": "con_0020",
        "cust_0014": "con_0023",
        "cust_0015": "con_0025",
    }
    return mapping[customer_id]


def build_work_orders(locations: list[dict], equipment: list[dict]) -> list[dict]:
    by_location: dict[str, list[str]] = {}
    for asset in equipment:
        by_location.setdefault(asset["service_location_id"], []).append(asset["id"])
    records: list[dict] = []
    for index, status in enumerate(WO_STATUSES, start=1):
        location = locations[(index - 1) % len(locations)]
        tech = TECHS[(index - 1) % len(TECHS)]
        assets = by_location[location["id"]][:2]
        opened_month = 3 + ((index - 1) // 8)
        opened_day = 3 + ((index * 2) % 24)
        opened = ts(min(opened_month, 10), min(opened_day, 28), 14, 15)
        work_type = WO_TYPES[(index - 1) % len(WO_TYPES)]
        if status == "reopened":
            work_type = "callback"
        if status == "awaiting_parts":
            work_type = "repair"
        priority = "normal"
        if work_type == "after_hours":
            priority = "high"
        if index in {12, 17}:
            priority = "emergency"
        record: dict = {
            "id": id_for("wo", index),
            "customer_id": location["customer_id"],
            "service_location_id": location["id"],
            "status": status,
            "priority": priority,
            "work_type": work_type,
            "summary": f"{work_type.replace('_', ' ').title()} request {index}",
            "description": (
                "Synthetic laboratory work order for Wasatch Business Systems."
            ),
            "requested_by_contact_id": _primary_contact(location["customer_id"]),
            "opened_at": opened,
            "created_at": opened,
            "updated_at": opened,
        }
        if assets:
            record["equipment_ids"] = assets
        if status not in {"created", "cancelled"}:
            record["assigned_employee_ids"] = [tech]
            record["scheduled_for"] = ts(
                min(opened_month, 10), min(opened_day + 1, 28), 8, 0
            )
        if status in {"completed", "invoiced"}:
            done = ts(min(opened_month + 1, 10), min(opened_day, 28), 17, 40)
            record["completed_at"] = done
            record["completion_notes"] = (
                "Filters replaced, voltages checked, customer signed."
            )
            record["updated_at"] = done
        if status == "invoiced":
            # invoiced WOs are indexes 28-37 -> invoices 5-14 mapped later
            invoice_number = index - 23
            record["invoice_id"] = id_for("inv", invoice_number)
        if status == "cancelled":
            record["cancelled_reason"] = "Customer postponed pending budget."
        if status == "reopened":
            record["reopen_reason"] = "Callback for repeated short cycling."
            record["assigned_employee_ids"] = [tech]
            record["completed_at"] = ts(9, 18, 16, 10)
            record["completion_notes"] = "Original visit completed; reopened."
        if status == "awaiting_parts":
            record["description"] = (
                "Waiting on compressor assembly; ETA ten business days."
            )
        if index <= 15:
            record["support_ticket_id"] = id_for("tkt", index)
        records.append(record)
    return records


def build_tasks(work_orders: list[dict]) -> list[dict]:
    created = ts(3, 1, 12)
    records: list[dict] = []
    number = 0
    for work_order in work_orders:
        task_count = (
            2 if work_order["status"] in {"in_progress", "completed", "invoiced"} else 1
        )
        for sequence in range(1, task_count + 1):
            number += 1
            status = "pending"
            if work_order["status"] in {"completed", "invoiced"}:
                status = "completed"
            elif work_order["status"] == "in_progress" and sequence == 1:
                status = "in_progress"
            elif work_order["status"] == "awaiting_parts" and sequence == 1:
                status = "blocked"
            elif work_order["status"] == "cancelled":
                status = "cancelled"
            record = {
                "id": id_for("wot", number),
                "work_order_id": work_order["id"],
                "sequence": sequence,
                "description": f"Task {sequence} for {work_order['id']}",
                "status": status,
                "created_at": created,
                "updated_at": created,
            }
            assigned = work_order.get("assigned_employee_ids")
            if assigned:
                record["assigned_employee_id"] = assigned[0]
            if status == "completed":
                record["completed_at"] = work_order.get("completed_at", ts(6, 1, 16))
            if status == "blocked":
                record["blocked_reason"] = "Parts not on truck."
            records.append(record)
    return records


def build_appointments(work_orders: list[dict]) -> list[dict]:
    eligible = [
        work_order
        for work_order in work_orders
        if work_order["status"] not in {"created", "cancelled"}
    ][:25]
    records: list[dict] = []
    for index, work_order in enumerate(eligible, start=1):
        start = ts(5, index, 8, 0)
        end_hour = 10
        status = "scheduled"
        if work_order["status"] in {"assigned"}:
            status = "confirmed"
        if work_order["status"] == "in_progress":
            status = "in_progress"
        if work_order["status"] in {"completed", "invoiced"}:
            status = "completed"
        if work_order["status"] == "reopened":
            status = "rescheduled"
        record = {
            "id": id_for("appt", index),
            "work_order_id": work_order["id"],
            "service_location_id": work_order["service_location_id"],
            "assigned_employee_id": work_order.get("assigned_employee_ids", TECHS)[0],
            "status": status,
            "start_at": start,
            "end_at": start[:11] + f"{end_hour:02d}:00:00Z",
            "created_at": work_order["created_at"],
            "updated_at": work_order["updated_at"],
        }
        if index == 2:
            record["status"] = "rescheduled"
            record["replaces_appointment_id"] = "appt_0001"
            record["notes"] = "Moved after original window conflicted."
        records.append(record)
    return records


def _line(
    number: int,
    invoice_id: str,
    description: str,
    quantity: int | float,
    unit: Decimal,
    line_type: str,
    work_order_id: str | None,
    stamp: str,
) -> dict:
    qty = Decimal(str(quantity))
    total = (qty * unit).quantize(TWOPLACES)
    record = {
        "id": id_for("il", number),
        "invoice_id": invoice_id,
        "description": description,
        "quantity": float(qty) if qty != qty.to_integral() else int(qty),
        "unit_price": money(unit),
        "line_total": money(total),
        "line_type": line_type,
        "created_at": stamp,
        "updated_at": stamp,
    }
    if work_order_id:
        record["work_order_id"] = work_order_id
    return record


def _invoice_from_lines(
    number: int,
    customer_id: str,
    status: str,
    lines: list[dict],
    stamp: str,
    work_order_id: str | None = None,
    issued_on: str | None = None,
    due_on: str | None = None,
    amount_paid: Decimal = Decimal("0.00"),
    notes: str | None = None,
    voided_on: str | None = None,
    void_reason: str | None = None,
) -> dict:
    subtotal = sum(
        (Decimal(line["line_total"]["amount"]) for line in lines),
        Decimal("0.00"),
    ).quantize(TWOPLACES)
    tax = (subtotal * TAX_RATE).quantize(TWOPLACES)
    adjustments = Decimal("0.00")
    total = (subtotal + tax + adjustments).quantize(TWOPLACES)
    paid = amount_paid.quantize(TWOPLACES)
    record = {
        "id": id_for("inv", number),
        "customer_id": customer_id,
        "status": status,
        "subtotal": money(subtotal),
        "tax": money(tax),
        "adjustments": money(adjustments),
        "total": money(total),
        "amount_paid": money(paid),
        "balance": money(total - paid),
        "created_at": stamp,
        "updated_at": stamp,
    }
    if work_order_id:
        record["work_order_id"] = work_order_id
    if issued_on:
        record["issued_on"] = issued_on
    if due_on:
        record["due_on"] = due_on
    if notes:
        record["notes"] = notes
    if voided_on:
        record["voided_on"] = voided_on
    if void_reason:
        record["void_reason"] = void_reason
    return record


def build_finance(work_orders: list[dict]) -> tuple[list, list, list]:
    stamp = ts(5, 1, 11)
    invoices: list[dict] = []
    lines: list[dict] = []
    payments: list[dict] = []
    line_number = 0
    payment_number = 0

    def add_lines(
        invoice_id: str, work_order_id: str | None, extra: bool
    ) -> list[dict]:
        nonlocal line_number
        created_lines = []
        line_number += 1
        created_lines.append(
            _line(
                line_number,
                invoice_id,
                "Labor - diagnostic and repair",
                2,
                Decimal("125.00"),
                "labor",
                work_order_id,
                stamp,
            )
        )
        if extra:
            line_number += 1
            created_lines.append(
                _line(
                    line_number,
                    invoice_id,
                    "Replacement contactor",
                    1,
                    Decimal("86.50"),
                    "parts",
                    work_order_id,
                    stamp,
                )
            )
        lines.extend(created_lines)
        return created_lines

    completed = [wo for wo in work_orders if wo["status"] == "completed"]
    invoiced = [wo for wo in work_orders if wo["status"] == "invoiced"]

    # 1-4 draft from completed WOs
    for index in range(1, 5):
        work_order = completed[index - 1]
        extra = index <= 2
        created_lines = add_lines(id_for("inv", index), work_order["id"], extra)
        invoices.append(
            _invoice_from_lines(
                index,
                work_order["customer_id"],
                "draft",
                created_lines,
                stamp,
                work_order_id=work_order["id"],
            )
        )

    # 5-10 issued from first six invoiced WOs
    for offset, work_order in enumerate(invoiced[:6], start=5):
        extra = offset == 5
        created_lines = add_lines(id_for("inv", offset), work_order["id"], extra)
        invoices.append(
            _invoice_from_lines(
                offset,
                work_order["customer_id"],
                "issued",
                created_lines,
                stamp,
                work_order_id=work_order["id"],
                issued_on=day(10, 20),
                due_on=day(11, 20),
            )
        )

    # 11-12 paid from remaining invoiced WOs (first two of remaining four)
    for offset, work_order in enumerate(invoiced[6:8], start=11):
        created_lines = add_lines(id_for("inv", offset), work_order["id"], True)
        invoice = _invoice_from_lines(
            offset,
            work_order["customer_id"],
            "paid",
            created_lines,
            stamp,
            work_order_id=work_order["id"],
            issued_on=day(8, 1),
            due_on=day(8, 31),
            amount_paid=Decimal("0.00"),
        )
        total = Decimal(invoice["total"]["amount"])
        invoice["amount_paid"] = money(total)
        invoice["balance"] = money("0.00")
        invoices.append(invoice)
        payment_number += 1
        payments.append(
            {
                "id": id_for("pay", payment_number),
                "invoice_id": invoice["id"],
                "amount": money(total),
                "method": "ach",
                "status": "posted",
                "received_on": day(8, 20),
                "received_by_employee_id": "emp_0009",
                "created_at": stamp,
                "updated_at": stamp,
            }
        )

    # 13 partial from next invoiced WO
    work_order = invoiced[8]
    created_lines = add_lines("inv_0013", work_order["id"], True)
    invoice = _invoice_from_lines(
        13,
        work_order["customer_id"],
        "partially_paid",
        created_lines,
        stamp,
        work_order_id=work_order["id"],
        issued_on=day(10, 1),
        due_on=day(11, 15),
    )
    half = (Decimal(invoice["total"]["amount"]) / 2).quantize(TWOPLACES)
    invoice["amount_paid"] = money(half)
    invoice["balance"] = money(Decimal(invoice["total"]["amount"]) - half)
    invoices.append(invoice)
    payment_number += 1
    payments.append(
        {
            "id": id_for("pay", payment_number),
            "invoice_id": "inv_0013",
            "amount": money(half),
            "method": "check",
            "status": "posted",
            "received_on": day(10, 20),
            "reference": "CHK-4410",
            "received_by_employee_id": "emp_0009",
            "created_at": stamp,
            "updated_at": stamp,
        }
    )

    # 14 overdue from last invoiced WO, unpaid
    work_order = invoiced[9]
    created_lines = add_lines("inv_0014", work_order["id"], False)
    invoices.append(
        _invoice_from_lines(
            14,
            work_order["customer_id"],
            "overdue",
            created_lines,
            stamp,
            work_order_id=work_order["id"],
            issued_on=day(8, 5),
            due_on=day(9, 5),
        )
    )

    agreement_customers = [
        "cust_0001",
        "cust_0003",
        "cust_0004",
        "cust_0007",
        "cust_0008",
        "cust_0013",
        "cust_0002",
        "cust_0006",
        "cust_0010",
        "cust_0011",
        "cust_0005",
        "cust_0009",
        "cust_0014",
        "cust_0001",
        "cust_0003",
        "cust_0013",
    ]
    # remaining invoices 15-30: 8 paid, 3 partial, 3 overdue, 2 voided = 16
    statuses = ["paid"] * 8 + ["partially_paid"] * 3 + ["overdue"] * 3 + ["voided"] * 2
    if len(statuses) != len(agreement_customers):
        raise ValueError("agreement invoice specs are misaligned")
    for offset, status, customer_id in (
        (index + 15, statuses[index], agreement_customers[index])
        for index in range(len(statuses))
    ):
        extra = offset in {15, 16, 20, 24}
        created_lines = add_lines(id_for("inv", offset), None, extra)
        issued = day(7, 10) if status != "voided" else day(6, 2)
        due = day(8, 10) if status == "overdue" else day(11, 10)
        if status == "voided":
            due = day(7, 2)
        invoice = _invoice_from_lines(
            offset,
            customer_id,
            status,
            created_lines,
            stamp,
            issued_on=None if status == "voided" else issued,
            due_on=None if status == "voided" else due,
            notes="Seasonal agreement billing" if status != "voided" else None,
            voided_on=day(6, 20) if status == "voided" else None,
            void_reason="Duplicate draft issued in error"
            if status == "voided"
            else None,
        )
        total = Decimal(invoice["total"]["amount"])
        if status == "paid":
            # four of these get split payments
            if offset in {15, 16, 17, 18}:
                first = (total / 2).quantize(TWOPLACES)
                second = total - first
                invoice["amount_paid"] = money(total)
                invoice["balance"] = money("0.00")
                for amount, received in (
                    (first, day(7, 20)),
                    (second, day(8, 5)),
                ):
                    payment_number += 1
                    payments.append(
                        {
                            "id": id_for("pay", payment_number),
                            "invoice_id": invoice["id"],
                            "amount": money(amount),
                            "method": "card",
                            "status": "posted",
                            "received_on": received,
                            "received_by_employee_id": "emp_0008",
                            "created_at": stamp,
                            "updated_at": stamp,
                        }
                    )
            else:
                invoice["amount_paid"] = money(total)
                invoice["balance"] = money("0.00")
                payment_number += 1
                payments.append(
                    {
                        "id": id_for("pay", payment_number),
                        "invoice_id": invoice["id"],
                        "amount": money(total),
                        "method": "ach",
                        "status": "posted",
                        "received_on": day(8, 12),
                        "received_by_employee_id": "emp_0008",
                        "created_at": stamp,
                        "updated_at": stamp,
                    }
                )
        elif status == "partially_paid":
            partial = (total / 3).quantize(TWOPLACES)
            invoice["amount_paid"] = money(partial)
            invoice["balance"] = money(total - partial)
            payment_number += 1
            payments.append(
                {
                    "id": id_for("pay", payment_number),
                    "invoice_id": invoice["id"],
                    "amount": money(partial),
                    "method": "check",
                    "status": "posted",
                    "received_on": day(10, 12),
                    "reference": f"CHK-{offset}00",
                    "created_at": stamp,
                    "updated_at": stamp,
                }
            )
        elif status == "overdue" and offset in {26, 27}:
            partial = Decimal("200.00")
            invoice["amount_paid"] = money(partial)
            invoice["balance"] = money(total - partial)
            invoice["due_on"] = day(9, 1)
            payment_number += 1
            payments.append(
                {
                    "id": id_for("pay", payment_number),
                    "invoice_id": invoice["id"],
                    "amount": money(partial),
                    "method": "ach",
                    "status": "posted",
                    "received_on": day(8, 28),
                    "created_at": stamp,
                    "updated_at": stamp,
                }
            )
        elif status == "overdue":
            invoice["due_on"] = day(9, 1)
        elif status == "voided":
            invoice["issued_on"] = issued
            invoice["status"] = "voided"
        invoices.append(invoice)

    return invoices, lines, payments


def build_documents(
    work_orders: list[dict], invoices: list[dict], locations: list[dict]
) -> tuple[list, list, list]:
    stamp = ts(6, 2, 13)
    documents: list[dict] = []
    versions: list[dict] = []
    extractions: list[dict] = []
    types = [
        "invoice_scan",
        "work_order_photo",
        "contract",
        "vendor_bill",
        "equipment_manual",
        "correspondence",
    ]
    statuses = [
        "uploaded",
        "awaiting_extraction",
        "extracted",
        "needs_review",
        "reviewed",
        "archived",
    ]
    for index in range(1, 31):
        location = locations[(index - 1) % len(locations)]
        work_order = work_orders[(index - 1) % len(work_orders)]
        invoice = invoices[(index - 1) % len(invoices)]
        doc_id = id_for("doc", index)
        version_id = id_for("dv", index)
        source = ["email", "upload", "scan", "generated"][(index - 1) % 4]
        document = {
            "id": doc_id,
            "title": f"Synthetic document {index}",
            "document_type": types[(index - 1) % len(types)],
            "status": statuses[(index - 1) % len(statuses)],
            "source": source,
            "mime_type": "application/pdf" if index % 2 else "image/jpeg",
            "untrusted": source != "generated",
            "customer_id": location["customer_id"],
            "service_location_id": location["id"],
            "current_version_id": version_id,
            "uploaded_by_employee_id": "emp_0007",
            "created_at": stamp,
            "updated_at": stamp,
        }
        if index % 3 == 0:
            document["work_order_id"] = work_order["id"]
        if index % 5 == 0:
            document["invoice_id"] = invoice["id"]
        if document["status"] == "awaiting_extraction":
            document["notes"] = "Queued for extraction; human review required."
        documents.append(document)
        versions.append(
            {
                "id": version_id,
                "document_id": doc_id,
                "version_number": 1,
                "storage_path": f"synthetic/documents/{doc_id}/v1.bin",
                "checksum_sha256": checksum(doc_id, "v1"),
                "byte_size": 12000 + index * 137,
                "created_by_employee_id": "emp_0007",
                "created_at": stamp,
            }
        )
        if index <= 18:
            status = [
                "pending",
                "succeeded",
                "needs_review",
                "accepted",
                "rejected",
                "failed",
            ][(index - 1) % 6]
            extraction = {
                "id": id_for("dx", index),
                "document_id": doc_id,
                "document_version_id": version_id,
                "status": status,
                "extractor": "model" if status != "pending" else "rules",
                "confidence": round(0.4 + (index % 6) * 0.1, 2),
                "extracted_fields": {
                    "vendor_name": "Synthetic Vendor",
                    "invoice_number": f"V-{index:04d}",
                },
                "extracted_at": stamp,
                "created_at": stamp,
                "updated_at": stamp,
            }
            if status in {"accepted", "rejected"}:
                extraction["reviewed_by_employee_id"] = "emp_0008"
                extraction["reviewed_at"] = ts(6, 8, 10)
                extraction["review_notes"] = (
                    "Accepted for posting"
                    if status == "accepted"
                    else "Amounts did not match work order."
                )
            if status == "needs_review":
                extraction["review_notes"] = "Low confidence; hold for AP."
            extractions.append(extraction)
    extra_version = {
        "id": "dv_0031",
        "document_id": "doc_0004",
        "version_number": 2,
        "storage_path": "synthetic/documents/doc_0004/v2.bin",
        "checksum_sha256": checksum("doc_0004", "v2"),
        "byte_size": 15001,
        "created_by_employee_id": "emp_0009",
        "created_at": ts(6, 9, 11),
    }
    versions.append(extra_version)
    documents[3]["current_version_id"] = "dv_0031"
    return documents, versions, extractions


def build_tickets(work_orders: list[dict]) -> tuple[list, list, list]:
    statuses = [
        "opened",
        "triaged",
        "triaged",
        "assigned",
        "assigned",
        "assigned",
        "awaiting_customer",
        "awaiting_customer",
        "awaiting_customer",
        "resolved",
        "resolved",
        "closed",
        "closed",
        "closed",
        "reopened",
    ]
    tickets: list[dict] = []
    messages: list[dict] = []
    interactions: list[dict] = []
    for index, status in enumerate(statuses, start=1):
        work_order = work_orders[index - 1]
        opened = ts(4, min(index + 1, 28), 9, 30)
        ticket = {
            "id": id_for("tkt", index),
            "customer_id": work_order["customer_id"],
            "contact_id": work_order.get("requested_by_contact_id"),
            "service_location_id": work_order["service_location_id"],
            "work_order_id": work_order["id"],
            "status": status,
            "priority": work_order["priority"],
            "channel": ["phone", "email", "portal", "sms"][(index - 1) % 4],
            "subject": f"Service request related to {work_order['id']}",
            "opened_at": opened,
            "created_at": opened,
            "updated_at": opened,
        }
        if status not in {"opened", "triaged"}:
            ticket["assigned_employee_id"] = "emp_0006" if index % 2 else "emp_0007"
        if status in {"resolved", "closed"}:
            ticket["resolved_at"] = ts(5, min(index, 28), 16)
        if status == "closed":
            ticket["closed_at"] = ts(5, min(index + 1, 28), 11)
        if index in {3, 8}:
            ticket["related_document_ids"] = [id_for("doc", index)]
        tickets.append(ticket)
        messages.append(
            {
                "id": id_for("msg", index),
                "support_ticket_id": ticket["id"],
                "direction": "inbound",
                "channel": ticket["channel"],
                "body": "Please send a technician. Rooftop unit is down.",
                "status": "sent",
                "author_contact_id": ticket.get("contact_id"),
                "sent_at": opened,
                "created_at": opened,
                "updated_at": opened,
            }
        )
        interactions.append(
            {
                "id": id_for("ixn", index),
                "customer_id": ticket["customer_id"],
                "contact_id": ticket.get("contact_id"),
                "support_ticket_id": ticket["id"],
                "work_order_id": work_order["id"],
                "channel": ticket["channel"],
                "occurred_at": opened,
                "summary": "Logged inbound request and created work order.",
                "employee_id": "emp_0007",
                "outcome": "scheduled" if status != "opened" else "answered",
                "created_at": opened,
                "updated_at": opened,
            }
        )
    # extra outbound messages needing approval
    messages.append(
        {
            "id": "msg_0016",
            "support_ticket_id": "tkt_0007",
            "direction": "outbound",
            "channel": "email",
            "body": "We can be on site Thursday at 08:00 if you approve overtime.",
            "status": "pending_approval",
            "author_employee_id": "emp_0006",
            "requires_approval": True,
            "approval_request_id": "apr_0001",
            "sent_at": ts(10, 28, 15, 5),
            "created_at": ts(10, 28, 15, 5),
            "updated_at": ts(10, 28, 15, 5),
        }
    )
    messages.append(
        {
            "id": "msg_0017",
            "support_ticket_id": "tkt_0012",
            "direction": "outbound",
            "channel": "email",
            "body": "Work is complete. Invoice will follow under net 30 terms.",
            "status": "sent",
            "author_employee_id": "emp_0006",
            "requires_approval": True,
            "approval_request_id": "apr_0004",
            "sent_at": ts(9, 12, 11, 20),
            "created_at": ts(9, 12, 11, 0),
            "updated_at": ts(9, 12, 11, 20),
        }
    )
    return tickets, messages, interactions


def build_approvals(work_orders: list[dict], invoices: list[dict]) -> list[dict]:
    stamp = ts(9, 1, 10)

    def history(entries: list[tuple]) -> list[dict]:
        rows = []
        for at, actor, source, target, note in entries:
            item = {
                "at": at,
                "actor_employee_id": actor,
                "from_status": source,
                "to_status": target,
            }
            if note:
                item["note"] = note
            rows.append(item)
        return rows

    cancelled_wo = next(
        work_order for work_order in work_orders if work_order["status"] == "cancelled"
    )
    voided = next(invoice for invoice in invoices if invoice["status"] == "voided")
    issued = next(invoice for invoice in invoices if invoice["status"] == "issued")
    return [
        {
            "id": "apr_0001",
            "action_type": "send_customer_message",
            "status": "pending",
            "requested_by_employee_id": "emp_0006",
            "subject_type": "message",
            "subject_id": "msg_0016",
            "rationale": "Overtime commitment needs manager approval.",
            "requested_at": ts(10, 28, 15, 6),
            "decision_history": [],
            "created_at": stamp,
            "updated_at": ts(10, 28, 15, 6),
        },
        {
            "id": "apr_0002",
            "action_type": "void_invoice",
            "status": "pending",
            "requested_by_employee_id": "emp_0009",
            "subject_type": "invoice",
            "subject_id": issued["id"],
            "rationale": "Customer disputes duplicate visit.",
            "requested_at": ts(11, 1, 9, 15),
            "decision_history": [],
            "created_at": stamp,
            "updated_at": ts(11, 1, 9, 15),
        },
        {
            "id": "apr_0003",
            "action_type": "price_override",
            "status": "approved",
            "requested_by_employee_id": "emp_0014",
            "reviewer_employee_id": "emp_0001",
            "subject_type": "invoice",
            "subject_id": "inv_0011",
            "rationale": "Match quoted maintenance rate.",
            "decision_notes": "Approved at quoted rate.",
            "requested_at": ts(8, 2, 13, 0),
            "decided_at": ts(8, 2, 15, 10),
            "decision_history": history(
                [
                    (
                        ts(8, 2, 15, 10),
                        "emp_0001",
                        "pending",
                        "approved",
                        "Rate matches signed quote.",
                    )
                ]
            ),
            "created_at": stamp,
            "updated_at": ts(8, 2, 15, 10),
        },
        {
            "id": "apr_0004",
            "action_type": "send_customer_message",
            "status": "executed",
            "requested_by_employee_id": "emp_0006",
            "reviewer_employee_id": "emp_0002",
            "subject_type": "message",
            "subject_id": "msg_0017",
            "rationale": "Confirm completion and billing terms.",
            "requested_at": ts(9, 12, 11, 5),
            "decided_at": ts(9, 12, 11, 15),
            "executed_at": ts(9, 12, 11, 20),
            "decision_history": history(
                [
                    (
                        ts(9, 12, 11, 15),
                        "emp_0002",
                        "pending",
                        "approved",
                        None,
                    ),
                    (
                        ts(9, 12, 11, 20),
                        "emp_0006",
                        "approved",
                        "executed",
                        "Email sent.",
                    ),
                ]
            ),
            "created_at": stamp,
            "updated_at": ts(9, 12, 11, 20),
        },
        {
            "id": "apr_0005",
            "action_type": "issue_invoice",
            "status": "executed",
            "requested_by_employee_id": "emp_0009",
            "reviewer_employee_id": "emp_0008",
            "subject_type": "invoice",
            "subject_id": "inv_0005",
            "rationale": "Issue seasonal work invoice over threshold.",
            "requested_at": ts(9, 14, 10, 0),
            "decided_at": ts(9, 14, 16, 0),
            "executed_at": ts(9, 15, 9, 0),
            "decision_history": history(
                [
                    (ts(9, 14, 16, 0), "emp_0008", "pending", "approved", None),
                    (ts(9, 15, 9, 0), "emp_0009", "approved", "executed", None),
                ]
            ),
            "created_at": stamp,
            "updated_at": ts(9, 15, 9, 0),
        },
        {
            "id": "apr_0006",
            "action_type": "cancel_work_order",
            "status": "executed",
            "requested_by_employee_id": "emp_0004",
            "reviewer_employee_id": "emp_0003",
            "subject_type": "work_order",
            "subject_id": cancelled_wo["id"],
            "rationale": "Customer asked to freeze spend this quarter.",
            "requested_at": ts(10, 2, 8, 30),
            "decided_at": ts(10, 2, 9, 0),
            "executed_at": ts(10, 2, 9, 15),
            "decision_history": history(
                [
                    (ts(10, 2, 9, 0), "emp_0003", "pending", "approved", None),
                    (
                        ts(10, 2, 9, 15),
                        "emp_0004",
                        "approved",
                        "executed",
                        "Work order cancelled.",
                    ),
                ]
            ),
            "created_at": stamp,
            "updated_at": ts(10, 2, 9, 15),
        },
        {
            "id": "apr_0007",
            "action_type": "export_records",
            "status": "rejected",
            "requested_by_employee_id": "emp_0007",
            "reviewer_employee_id": "emp_0001",
            "subject_type": "customer",
            "subject_id": "cust_0001",
            "rationale": "Vendor asked for full customer export.",
            "decision_notes": "Denied; no DPA in place.",
            "requested_at": ts(10, 20, 14, 0),
            "decided_at": ts(10, 20, 16, 40),
            "decision_history": history(
                [
                    (
                        ts(10, 20, 16, 40),
                        "emp_0001",
                        "pending",
                        "rejected",
                        "Use a summarized report instead.",
                    )
                ]
            ),
            "created_at": stamp,
            "updated_at": ts(10, 20, 16, 40),
        },
        {
            "id": "apr_0008",
            "action_type": "change_schedule",
            "status": "cancelled",
            "requested_by_employee_id": "emp_0005",
            "subject_type": "appointment",
            "subject_id": "appt_0004",
            "rationale": "Move emergency ahead of routine filter run.",
            "requested_at": ts(10, 12, 7, 45),
            "decided_at": ts(10, 12, 8, 10),
            "decision_history": history(
                [
                    (
                        ts(10, 12, 8, 10),
                        "emp_0005",
                        "pending",
                        "cancelled",
                        "Emergency fit into open slot; change not needed.",
                    )
                ]
            ),
            "created_at": stamp,
            "updated_at": ts(10, 12, 8, 10),
        },
        {
            "id": "apr_0009",
            "action_type": "void_invoice",
            "status": "executed",
            "requested_by_employee_id": "emp_0009",
            "reviewer_employee_id": "emp_0008",
            "subject_type": "invoice",
            "subject_id": voided["id"],
            "rationale": "Duplicate agreement invoice.",
            "requested_at": ts(6, 18, 10, 0),
            "decided_at": ts(6, 19, 9, 0),
            "executed_at": ts(6, 20, 9, 0),
            "decision_history": history(
                [
                    (ts(6, 19, 9, 0), "emp_0008", "pending", "approved", None),
                    (ts(6, 20, 9, 0), "emp_0009", "approved", "executed", None),
                ]
            ),
            "created_at": stamp,
            "updated_at": ts(6, 20, 9, 0),
        },
        {
            "id": "apr_0010",
            "action_type": "change_schedule",
            "status": "pending",
            "requested_by_employee_id": "emp_0004",
            "subject_type": "appointment",
            "subject_id": "appt_0010",
            "rationale": "Technician still on emergency at Lakeside.",
            "requested_at": ts(11, 2, 6, 50),
            "decision_history": [],
            "created_at": stamp,
            "updated_at": ts(11, 2, 6, 50),
        },
    ]


def build_audits(
    work_orders: list[dict],
    invoices: list[dict],
    tickets: list[dict],
    approvals: list[dict],
    documents: list[dict],
    payments: list[dict],
) -> list[dict]:
    events: list[dict] = []

    def add(action: str, subject_type: str, subject_id: str, **extra: object) -> None:
        index = len(events) + 1
        event = {
            "id": id_for("aud", index),
            "occurred_at": ts(3 + (index % 8), 1 + (index % 27), 10, index % 60),
            "actor_type": extra.pop("actor_type", "employee"),
            "action": action,
            "subject_type": subject_type,
            "subject_id": subject_id,
            "outcome": extra.pop("outcome", "succeeded"),
        }
        if "actor_employee_id" in extra:
            event["actor_employee_id"] = extra.pop("actor_employee_id")
        elif event["actor_type"] == "employee":
            event["actor_employee_id"] = "emp_0004"
        event.update({key: value for key, value in extra.items() if value is not None})
        events.append(event)

    for work_order in work_orders[:12]:
        add(
            "work_order.created",
            "work_order",
            work_order["id"],
            actor_employee_id="emp_0006",
        )
    for work_order in work_orders[19:27]:
        add(
            "work_order.completed",
            "work_order",
            work_order["id"],
            actor_employee_id="emp_0010",
        )
    for invoice in invoices[:10]:
        add(
            "invoice.recorded",
            "invoice",
            invoice["id"],
            actor_employee_id="emp_0009",
        )
    for payment in payments[:8]:
        add(
            "payment.posted",
            "payment",
            payment["id"],
            actor_employee_id="emp_0008",
        )
    for ticket in tickets[:6]:
        add(
            "support_ticket.opened",
            "support_ticket",
            ticket["id"],
            actor_employee_id="emp_0007",
        )
    for approval in approvals:
        add(
            "approval.updated",
            "approval_request",
            approval["id"],
            actor_employee_id=approval["requested_by_employee_id"],
            approval_request_id=approval["id"],
            outcome="pending" if approval["status"] == "pending" else "succeeded",
        )
    for document in documents[:6]:
        add(
            "document.uploaded",
            "document",
            document["id"],
            actor_employee_id="emp_0007",
        )
    while len(events) < 50:
        add(
            "work_order.status_changed",
            "work_order",
            work_orders[len(events) % len(work_orders)]["id"],
            actor_employee_id="emp_0005",
            details={"note": "Dispatch updated status."},
        )
    return events[:50]
