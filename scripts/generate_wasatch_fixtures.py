"""Generate the valid synthetic Wasatch Business Systems fixture set.

All names, addresses, and financial figures are fictional. Re-run this script
after contract changes, then review the diff before committing.
"""

from __future__ import annotations

import json
from pathlib import Path

from wasatch_fixture_common import id_for, ts
from wasatch_ops_fixtures import (
    build_appointments,
    build_approvals,
    build_audits,
    build_documents,
    build_equipment,
    build_finance,
    build_tasks,
    build_tickets,
    build_work_orders,
)

ROOT = Path(__file__).resolve().parent.parent
VALID_DIR = ROOT / "data" / "fixtures" / "valid"
AS_OF = "2026-11-03"


def addr(
    line1: str, city: str, postal: str, line2: str | None = None
) -> dict[str, str]:
    payload = {
        "line1": line1,
        "city": city,
        "state": "UT",
        "postal_code": postal,
        "country": "US",
    }
    if line2:
        payload["line2"] = line2
    return payload


def envelope(entity: str, schema: str, records: list[dict]) -> dict:
    return {
        "synthetic": True,
        "entity": entity,
        "schema": schema,
        "records": records,
    }


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def build_roles() -> list[dict]:
    created = ts(1, 5, 14)
    specs = [
        ("General Manager", "management", True, "Company-wide approver"),
        ("Operations Manager", "management", True, "Operations approver"),
        ("Service Manager", "field_operations", True, "Field work approver"),
        ("Dispatcher", "dispatch", False, "Schedules technicians"),
        ("Customer Service Lead", "customer_service", False, "CS queue owner"),
        ("Customer Service Agent", "customer_service", False, "Inbound coverage"),
        ("Accounting Manager", "accounting", True, "Billing approver"),
        ("Staff Accountant", "accounting", False, "Invoice assembly"),
        ("Lead Technician", "field_operations", False, "Crew lead"),
        ("Service Technician", "field_operations", False, "Field work"),
        ("Account Executive", "sales", False, "Agreements and quotes"),
        ("HR Coordinator", "human_resources", False, "People records"),
    ]
    return [
        {
            "id": id_for("role", index),
            "name": name,
            "department": department,
            "is_approver": approver,
            "description": description,
            "created_at": created,
            "updated_at": created,
        }
        for index, (name, department, approver, description) in enumerate(
            specs, start=1
        )
    ]


def build_teams() -> list[dict]:
    created = ts(1, 5, 14, 10)
    return [
        {
            "id": "team_0001",
            "name": "Field Crew A",
            "department": "field_operations",
            "lead_employee_id": "emp_0010",
            "service_area": "Salt Lake County",
            "created_at": created,
            "updated_at": created,
        },
        {
            "id": "team_0002",
            "name": "Field Crew B",
            "department": "field_operations",
            "lead_employee_id": "emp_0012",
            "service_area": "Utah and Davis Counties",
            "created_at": created,
            "updated_at": created,
        },
        {
            "id": "team_0003",
            "name": "Dispatch Desk",
            "department": "dispatch",
            "lead_employee_id": "emp_0004",
            "service_area": "Wasatch Front",
            "created_at": created,
            "updated_at": created,
        },
        {
            "id": "team_0004",
            "name": "Customer Service",
            "department": "customer_service",
            "lead_employee_id": "emp_0006",
            "created_at": created,
            "updated_at": created,
        },
        {
            "id": "team_0005",
            "name": "Office",
            "department": "accounting",
            "lead_employee_id": "emp_0008",
            "created_at": created,
            "updated_at": created,
        },
    ]


def build_employees() -> list[dict]:
    created = ts(1, 6, 16)
    specs = [
        (
            "Jordan",
            "Hale",
            "role_0001",
            None,
            "management",
            "General Manager",
            "2014-03-03",
            [],
            "0100",
        ),
        (
            "Priya",
            "Shah",
            "role_0002",
            None,
            "management",
            "Operations Manager",
            "2017-06-12",
            ["OSHA_10"],
            "0101",
        ),
        (
            "Marcus",
            "Jensen",
            "role_0003",
            "team_0001",
            "field_operations",
            "Service Manager",
            "2015-09-21",
            ["EPA_608", "OSHA_30"],
            "0102",
        ),
        (
            "Elena",
            "Voss",
            "role_0004",
            "team_0003",
            "dispatch",
            "Dispatcher",
            "2019-01-08",
            [],
            "0103",
        ),
        (
            "Tyler",
            "Nguyen",
            "role_0004",
            "team_0003",
            "dispatch",
            "Dispatcher",
            "2021-04-19",
            [],
            "0104",
        ),
        (
            "Sofia",
            "Alvarez",
            "role_0005",
            "team_0004",
            "customer_service",
            "Customer Service Lead",
            "2018-11-02",
            ["FIRST_AID"],
            "0105",
        ),
        (
            "Ben",
            "Carter",
            "role_0006",
            "team_0004",
            "customer_service",
            "Customer Service Agent",
            "2022-02-14",
            [],
            "0106",
        ),
        (
            "Amina",
            "Qureshi",
            "role_0007",
            "team_0005",
            "accounting",
            "Accounting Manager",
            "2016-08-29",
            [],
            "0107",
        ),
        (
            "Luke",
            "Pedersen",
            "role_0008",
            "team_0005",
            "accounting",
            "Staff Accountant",
            "2020-05-11",
            [],
            "0108",
        ),
        (
            "Chris",
            "Barlow",
            "role_0009",
            "team_0001",
            "field_operations",
            "Lead Technician",
            "2013-07-15",
            ["EPA_608", "NATE", "OSHA_10"],
            "0109",
        ),
        (
            "Riley",
            "Chen",
            "role_0010",
            "team_0001",
            "field_operations",
            "Service Technician",
            "2019-10-07",
            ["EPA_608"],
            "0110",
        ),
        (
            "Devon",
            "Brooks",
            "role_0010",
            "team_0002",
            "field_operations",
            "Service Technician",
            "2018-03-26",
            ["EPA_608", "OSHA_10"],
            "0111",
        ),
        (
            "Harper",
            "Nilsen",
            "role_0010",
            "team_0002",
            "field_operations",
            "Service Technician",
            "2023-06-01",
            ["EPA_608"],
            "0112",
        ),
        (
            "Sam",
            "Ortiz",
            "role_0011",
            None,
            "sales",
            "Account Executive",
            "2019-09-16",
            [],
            "0113",
        ),
        (
            "Naomi",
            "Grant",
            "role_0012",
            None,
            "human_resources",
            "HR Coordinator",
            "2021-01-25",
            ["FIRST_AID"],
            "0114",
        ),
    ]
    records = []
    for index, spec in enumerate(specs, start=1):
        first, last, role, team, dept, title, hire, certs, phone = spec
        record = {
            "id": id_for("emp", index),
            "employee_number": f"E-{index:04d}",
            "first_name": first,
            "last_name": last,
            "email": (f"{first.lower()}.{last.lower()}@wasatch-business-systems.test"),
            "phone": f"+1-801-555-{phone}",
            "role_id": role,
            "department": dept,
            "job_title": title,
            "status": "active",
            "hire_date": hire,
            "created_at": created,
            "updated_at": created,
        }
        if team:
            record["team_id"] = team
        if certs:
            record["certifications"] = certs
        records.append(record)
    return records


def build_customers() -> list[dict]:
    created = ts(1, 8, 17)
    specs = [
        (
            "Pioneer Plaza Property Group LLC",
            "Pioneer Plaza",
            "property_manager",
            "active",
            "net_30",
            "full_coverage",
            "2027-03-31",
            "con_0001",
            addr("48 W 300 S", "Salt Lake City", "84101", "Suite 400"),
            "ap@pioneer-plaza.test",
            "+1-801-555-0120",
        ),
        (
            "Granite Peak Logistics Inc",
            None,
            "industrial",
            "active",
            "net_15",
            "seasonal",
            "2026-12-31",
            "con_0004",
            addr("2155 S 3270 W", "West Valley City", "84119"),
            "billing@granite-peak-logistics.test",
            "+1-385-555-0121",
        ),
        (
            "Red Rock Dental Partners LLC",
            "Red Rock Dental",
            "healthcare",
            "active",
            "net_30",
            "full_coverage",
            "2027-01-15",
            "con_0005",
            addr("9340 S 700 E", "Sandy", "84070"),
            "office@red-rock-dental.test",
            "+1-801-555-0122",
        ),
        (
            "Cottonwood Office Commons LLC",
            None,
            "property_manager",
            "active",
            "net_30",
            "seasonal",
            "2026-11-30",
            "con_0008",
            addr("2121 E 4800 S", "Holladay", "84117"),
            "billing@cottonwood-commons.test",
            "+1-801-555-0123",
        ),
        (
            "Wasatch View Retail LLC",
            None,
            "commercial_owner",
            "active",
            "due_on_receipt",
            "none",
            None,
            "con_0010",
            addr("3300 S 1300 E", "Millcreek", "84106"),
            "accounts@wasatch-view-retail.test",
            "+1-801-555-0124",
        ),
        (
            "Jordan River Charter School",
            None,
            "education",
            "active",
            "net_45",
            "seasonal",
            "2027-06-30",
            "con_0011",
            addr("10550 S 2200 W", "South Jordan", "84095"),
            "facilities@jordan-river-charter.test",
            "+1-801-555-0125",
        ),
        (
            "North Bench Civic Campus",
            None,
            "municipal",
            "active",
            "net_30",
            "full_coverage",
            "2027-02-28",
            "con_0012",
            addr("150 N Main St", "Bountiful", "84010"),
            "ap@north-bench-civic.test",
            "+1-801-555-0126",
        ),
        (
            "Lakeside Medical Pavilion LLC",
            None,
            "healthcare",
            "active",
            "net_30",
            "full_coverage",
            "2026-12-15",
            "con_0014",
            addr("444 W Shepard Ln", "Farmington", "84025"),
            "admin@lakeside-pavilion.test",
            "+1-385-555-0127",
        ),
        (
            "Sugar House Maker Works LLC",
            None,
            "industrial",
            "active",
            "net_15",
            "none",
            None,
            "con_0015",
            addr("2212 S 1100 E", "Salt Lake City", "84106"),
            None,
            "+1-801-555-0128",
        ),
        (
            "East Millcreek Professional Plaza",
            None,
            "property_manager",
            "active",
            "net_30",
            "seasonal",
            "2027-04-30",
            "con_0016",
            addr("3165 E 3300 S", "Millcreek", "84109"),
            "billing@east-millcreek-plaza.test",
            "+1-801-555-0129",
        ),
        (
            "Oquirrh Distribution Center LLC",
            None,
            "industrial",
            "active",
            "net_30",
            "seasonal",
            "2026-11-15",
            "con_0018",
            addr("8120 W 2100 S", "Magna", "84044"),
            "ap@oquirrh-distribution.test",
            "+1-385-555-0130",
        ),
        (
            "Exchange Place Retail Collective LLC",
            None,
            "commercial_owner",
            "suspended",
            "due_on_receipt",
            "none",
            None,
            "con_0019",
            addr("10 W Exchange Pl", "Salt Lake City", "84111"),
            "billing@exchange-place-retail.test",
            "+1-801-555-0131",
        ),
        (
            "Draper Canyon Tech Campus LLC",
            None,
            "property_manager",
            "active",
            "net_30",
            "full_coverage",
            "2027-08-31",
            "con_0020",
            addr("12899 S Minuteman Dr", "Draper", "84020"),
            "ops@draper-canyon-tech.test",
            "+1-801-555-0132",
        ),
        (
            "Ogden River Light Industrial LLC",
            None,
            "industrial",
            "active",
            "net_15",
            "none",
            None,
            "con_0023",
            addr("1450 W 2550 S", "Ogden", "84401"),
            "shop@ogden-river-industrial.test",
            "+1-385-555-0133",
        ),
        (
            "Provo Center Street Offices LLC",
            None,
            "commercial_owner",
            "prospect",
            "net_30",
            "none",
            None,
            "con_0025",
            addr("80 N University Ave", "Provo", "84601"),
            "hello@provo-center-offices.test",
            "+1-801-555-0134",
        ),
    ]
    records = []
    for index, spec in enumerate(specs, start=1):
        (
            legal,
            trade,
            ctype,
            status,
            terms,
            agreement,
            expires,
            primary,
            billing,
            email,
            phone,
        ) = spec
        record = {
            "id": id_for("cust", index),
            "legal_name": legal,
            "account_number": f"WBS-{index:05d}",
            "status": status,
            "customer_type": ctype,
            "billing_address": billing,
            "payment_terms": terms,
            "service_agreement": agreement,
            "primary_contact_id": primary,
            "created_at": created,
            "updated_at": created,
        }
        if trade:
            record["trade_name"] = trade
        if email:
            record["billing_email"] = email
        if phone:
            record["billing_phone"] = phone
        if expires:
            record["agreement_expires_on"] = expires
        records.append(record)
    return records


def build_contacts() -> list[dict]:
    created = ts(1, 9, 18)
    specs = [
        (
            "cust_0001",
            "Marta",
            "Ellison",
            "Director of Facilities",
            "facilities",
            True,
            "marta.ellison@pioneer-plaza.test",
            "+1-801-555-0140",
        ),
        (
            "cust_0001",
            "Owen",
            "Pratt",
            "AP Specialist",
            "billing",
            False,
            "owen.pratt@pioneer-plaza.test",
            "+1-801-555-0141",
        ),
        (
            "cust_0001",
            "Gina",
            "Cho",
            "Property Manager",
            "operations",
            False,
            "gina.cho@pioneer-plaza.test",
            "+1-801-555-0142",
        ),
        (
            "cust_0002",
            "Hector",
            "Miles",
            "Warehouse Manager",
            "operations",
            True,
            "hector.miles@granite-peak-logistics.test",
            "+1-385-555-0143",
        ),
        (
            "cust_0003",
            "Priya",
            "Dalton",
            "Practice Manager",
            "operations",
            True,
            "priya.dalton@red-rock-dental.test",
            "+1-801-555-0144",
        ),
        (
            "cust_0003",
            "Neil",
            "Barrow",
            "Facilities Lead",
            "facilities",
            False,
            "neil.barrow@red-rock-dental.test",
            "+1-801-555-0145",
        ),
        (
            "cust_0003",
            "Adele",
            "Moon",
            "Controller",
            "billing",
            False,
            "adele.moon@red-rock-dental.test",
            "+1-801-555-0146",
        ),
        (
            "cust_0004",
            "Chris",
            "Yates",
            "Building Engineer",
            "facilities",
            True,
            "chris.yates@cottonwood-commons.test",
            "+1-801-555-0147",
        ),
        (
            "cust_0004",
            "Lana",
            "Brooks",
            "Regional PM",
            "executive",
            False,
            "lana.brooks@cottonwood-commons.test",
            "+1-801-555-0148",
        ),
        (
            "cust_0005",
            "Ivy",
            "Nash",
            "Store Operations",
            "operations",
            True,
            "ivy.nash@wasatch-view-retail.test",
            "+1-801-555-0149",
        ),
        (
            "cust_0006",
            "Paul",
            "Kimball",
            "Facilities Director",
            "facilities",
            True,
            "paul.kimball@jordan-river-charter.test",
            "+1-801-555-0150",
        ),
        (
            "cust_0007",
            "Ruth",
            "Haddock",
            "Public Works Liaison",
            "operations",
            True,
            "ruth.haddock@north-bench-civic.test",
            "+1-801-555-0151",
        ),
        (
            "cust_0007",
            "Cal",
            "Mendez",
            "AP Clerk",
            "billing",
            False,
            "cal.mendez@north-bench-civic.test",
            "+1-801-555-0152",
        ),
        (
            "cust_0008",
            "Nora",
            "Whitfield",
            "Clinic Administrator",
            "executive",
            True,
            "nora.whitfield@lakeside-pavilion.test",
            "+1-385-555-0153",
        ),
        (
            "cust_0009",
            "Jules",
            "Farmer",
            "Owner",
            "executive",
            True,
            "jules.farmer@sugar-house-maker.test",
            "+1-801-555-0154",
        ),
        (
            "cust_0010",
            "Eden",
            "Park",
            "Property Manager",
            "facilities",
            True,
            "eden.park@east-millcreek-plaza.test",
            "+1-801-555-0155",
        ),
        (
            "cust_0010",
            "Theo",
            "Grant",
            "After-hours Contact",
            "other",
            False,
            None,
            "+1-801-555-0156",
        ),
        (
            "cust_0011",
            "Mina",
            "Solis",
            "Site Supervisor",
            "operations",
            True,
            "mina.solis@oquirrh-distribution.test",
            "+1-385-555-0157",
        ),
        (
            "cust_0012",
            "Arthur",
            "Bell",
            "Retail Lead",
            "operations",
            True,
            "arthur.bell@exchange-place-retail.test",
            "+1-801-555-0158",
        ),
        (
            "cust_0013",
            "Sasha",
            "Quinn",
            "Campus Engineer",
            "facilities",
            True,
            "sasha.quinn@draper-canyon-tech.test",
            "+1-801-555-0159",
        ),
        (
            "cust_0013",
            "Brett",
            "Ibarra",
            "Tenant Services",
            "operations",
            False,
            "brett.ibarra@draper-canyon-tech.test",
            "+1-801-555-0160",
        ),
        (
            "cust_0013",
            "Keiko",
            "Lund",
            "AP",
            "billing",
            False,
            "keiko.lund@draper-canyon-tech.test",
            "+1-801-555-0161",
        ),
        (
            "cust_0014",
            "Hank",
            "Rowe",
            "Plant Manager",
            "operations",
            True,
            "hank.rowe@ogden-river-industrial.test",
            "+1-385-555-0162",
        ),
        (
            "cust_0014",
            "Pia",
            "Nash",
            "Office Manager",
            "billing",
            False,
            "pia.nash@ogden-river-industrial.test",
            None,
        ),
        (
            "cust_0015",
            "Colin",
            "West",
            "Owner",
            "executive",
            True,
            "colin.west@provo-center-offices.test",
            "+1-801-555-0163",
        ),
    ]
    records = []
    for index, spec in enumerate(specs, start=1):
        customer, first, last, title, role, primary, email, phone = spec
        record = {
            "id": id_for("con", index),
            "customer_id": customer,
            "first_name": first,
            "last_name": last,
            "title": title,
            "contact_role": role,
            "is_primary": primary,
            "status": "active",
            "created_at": created,
            "updated_at": created,
        }
        if email:
            record["email"] = email
        if phone:
            record["phone"] = phone
        records.append(record)
    return records


def build_locations() -> list[dict]:
    created = ts(1, 10, 16)
    specs = [
        (
            "cust_0001",
            "Pioneer Plaza Tower",
            "office",
            addr("48 W 300 S", "Salt Lake City", "84101"),
            180000,
            "Dock 2 after 18:00",
        ),
        (
            "cust_0001",
            "Pioneer Plaza Annex",
            "mixed",
            addr("52 W 300 S", "Salt Lake City", "84101"),
            42000,
            None,
        ),
        (
            "cust_0002",
            "Granite Peak Warehouse",
            "warehouse",
            addr("2155 S 3270 W", "West Valley City", "84119"),
            220000,
            "Call before rooftop access",
        ),
        (
            "cust_0003",
            "Red Rock Dental Sandy",
            "medical",
            addr("9340 S 700 E", "Sandy", "84070"),
            12000,
            "Quiet hours 08:00-12:00",
        ),
        (
            "cust_0003",
            "Red Rock Dental Draper",
            "medical",
            addr("1192 E 12300 S", "Draper", "84020"),
            9000,
            None,
        ),
        (
            "cust_0004",
            "Cottonwood Commons North",
            "office",
            addr("2121 E 4800 S", "Holladay", "84117"),
            64000,
            None,
        ),
        (
            "cust_0004",
            "Cottonwood Commons South",
            "office",
            addr("2145 E 4800 S", "Holladay", "84117"),
            51000,
            "Loading dock on west side",
        ),
        (
            "cust_0005",
            "Wasatch View Shops",
            "retail",
            addr("3300 S 1300 E", "Millcreek", "84106"),
            28000,
            None,
        ),
        (
            "cust_0006",
            "Jordan River Charter Main",
            "school",
            addr("10550 S 2200 W", "South Jordan", "84095"),
            78000,
            "Check in at office",
        ),
        (
            "cust_0007",
            "North Bench City Hall",
            "municipal",
            addr("150 N Main St", "Bountiful", "84010"),
            36000,
            None,
        ),
        (
            "cust_0007",
            "North Bench Public Works Yard",
            "municipal",
            addr("80 E 400 N", "Bountiful", "84010"),
            18000,
            "Gate code on file",
        ),
        (
            "cust_0008",
            "Lakeside Medical Pavilion",
            "medical",
            addr("444 W Shepard Ln", "Farmington", "84025"),
            47000,
            "Infection-control rules",
        ),
        (
            "cust_0009",
            "Sugar House Maker Works",
            "warehouse",
            addr("2212 S 1100 E", "Salt Lake City", "84106"),
            16000,
            None,
        ),
        (
            "cust_0010",
            "East Millcreek Plaza",
            "office",
            addr("3165 E 3300 S", "Millcreek", "84109"),
            39000,
            None,
        ),
        (
            "cust_0011",
            "Oquirrh Distribution Center",
            "warehouse",
            addr("8120 W 2100 S", "Magna", "84044"),
            310000,
            "PPE required",
        ),
        (
            "cust_0012",
            "Exchange Place Shops",
            "retail",
            addr("10 W Exchange Pl", "Salt Lake City", "84111"),
            22000,
            None,
        ),
        (
            "cust_0013",
            "Draper Canyon Building A",
            "office",
            addr("12899 S Minuteman Dr", "Draper", "84020"),
            88000,
            None,
        ),
        (
            "cust_0013",
            "Draper Canyon Building B",
            "office",
            addr("12925 S Minuteman Dr", "Draper", "84020"),
            76000,
            "Visitor parking south lot",
        ),
        (
            "cust_0014",
            "Ogden River Light Industrial",
            "warehouse",
            addr("1450 W 2550 S", "Ogden", "84401"),
            54000,
            None,
        ),
        (
            "cust_0015",
            "Provo Center Street Offices",
            "office",
            addr("80 N University Ave", "Provo", "84601"),
            21000,
            None,
        ),
    ]
    records = []
    for index, spec in enumerate(specs, start=1):
        customer, name, site, address, sqft, access = spec
        record = {
            "id": id_for("loc", index),
            "customer_id": customer,
            "name": name,
            "address": address,
            "site_type": site,
            "timezone": "America/Denver",
            "square_footage": sqft,
            "status": "active" if customer != "cust_0012" else "inactive",
            "created_at": created,
            "updated_at": created,
        }
        if access:
            record["access_notes"] = access
        records.append(record)
    return records


def main() -> None:
    roles = build_roles()
    teams = build_teams()
    employees = build_employees()
    customers = build_customers()
    contacts = build_contacts()
    locations = build_locations()
    equipment = build_equipment(locations)
    work_orders = build_work_orders(locations, equipment)
    tasks = build_tasks(work_orders)
    appointments = build_appointments(work_orders)
    invoices, lines, payments = build_finance(work_orders)
    documents, versions, extractions = build_documents(work_orders, invoices, locations)
    tickets, messages, interactions = build_tickets(work_orders)
    approvals = build_approvals(work_orders, invoices)
    audits = build_audits(
        work_orders, invoices, tickets, approvals, documents, payments
    )

    files = [
        ("roles.json", "role", "workforce/role.schema.json", roles),
        ("teams.json", "team", "workforce/team.schema.json", teams),
        ("employees.json", "employee", "workforce/employee.schema.json", employees),
        ("customers.json", "customer", "customers/customer.schema.json", customers),
        ("contacts.json", "contact", "customers/contact.schema.json", contacts),
        (
            "service_locations.json",
            "service_location",
            "customers/service-location.schema.json",
            locations,
        ),
        (
            "equipment.json",
            "equipment",
            "field-operations/equipment.schema.json",
            equipment,
        ),
        (
            "work_orders.json",
            "work_order",
            "field-operations/work-order.schema.json",
            work_orders,
        ),
        (
            "work_order_tasks.json",
            "work_order_task",
            "field-operations/work-order-task.schema.json",
            tasks,
        ),
        (
            "appointments.json",
            "appointment",
            "field-operations/appointment.schema.json",
            appointments,
        ),
        ("invoices.json", "invoice", "finance/invoice.schema.json", invoices),
        (
            "invoice_lines.json",
            "invoice_line",
            "finance/invoice-line.schema.json",
            lines,
        ),
        ("payments.json", "payment", "finance/payment.schema.json", payments),
        ("documents.json", "document", "documents/document.schema.json", documents),
        (
            "document_versions.json",
            "document_version",
            "documents/document-version.schema.json",
            versions,
        ),
        (
            "document_extractions.json",
            "document_extraction",
            "documents/document-extraction.schema.json",
            extractions,
        ),
        (
            "support_tickets.json",
            "support_ticket",
            "customer-service/support-ticket.schema.json",
            tickets,
        ),
        (
            "messages.json",
            "message",
            "customer-service/message.schema.json",
            messages,
        ),
        (
            "interactions.json",
            "interaction",
            "customer-service/interaction.schema.json",
            interactions,
        ),
        (
            "approval_requests.json",
            "approval_request",
            "governance/approval-request.schema.json",
            approvals,
        ),
        (
            "audit_events.json",
            "audit_event",
            "governance/audit-event.schema.json",
            audits,
        ),
    ]

    counts = {}
    for filename, entity, schema, records in files:
        write_json(VALID_DIR / filename, envelope(entity, schema, records))
        counts[entity] = len(records)

    write_json(
        VALID_DIR / "manifest.json",
        {
            "synthetic": True,
            "as_of": AS_OF,
            "schema_version": "v1",
            "description": (
                "Valid interconnected Wasatch Business Systems laboratory dataset."
            ),
            "counts": counts,
        },
    )
    print(json.dumps(counts, indent=2))


if __name__ == "__main__":
    main()
