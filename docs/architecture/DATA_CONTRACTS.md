# Data Contracts

Machine-readable contracts for the Wasatch Business Systems laboratory domain. These files are API-first artifacts: future FastAPI modules and React clients should consume the same shapes rather than inventing parallel models.

No database or HTTP API is implemented yet. JSON Schema is the current contract, not a PostgreSQL schema dump.

**All fixture data is synthetic.**

## Locations

| Path | Purpose |
|---|---|
| `data/schemas/v1/` | JSON Schema Draft 2020-12 contracts |
| `data/fixtures/valid/` | Internally consistent interconnected sample |
| `data/fixtures/quality-issues/` | Deliberate defects for later AI and ops scenarios |
| `docs/business/WASATCH_DOMAIN_MODEL.md` | Human-readable entity definitions |
| `scripts/validate_wasatch_domain.py` | Schema, referential, and invariant checks |
| `scripts/generate_wasatch_fixtures.py` | Deterministic generator for the valid set |

## Conventions

### Identifiers

Pattern `{prefix}_{nnnn}`:

| Prefix | Entity |
|---|---|
| `cust` | Customer |
| `con` | Contact |
| `loc` | ServiceLocation |
| `emp` | Employee |
| `role` | Role |
| `team` | Team |
| `eq` | Equipment |
| `wo` | WorkOrder |
| `wot` | WorkOrderTask |
| `appt` | Appointment |
| `inv` | Invoice |
| `il` | InvoiceLine |
| `pay` | Payment |
| `doc` | Document |
| `dv` | DocumentVersion |
| `dx` | DocumentExtraction |
| `tkt` | SupportTicket |
| `msg` | Message |
| `ixn` | Interaction |
| `apr` | ApprovalRequest |
| `aud` | AuditEvent |

### Date and time

- Calendar dates: `YYYY-MM-DD`
- Instants: `YYYY-MM-DDTHH:MM:SSZ` (UTC)
- Valid fixtures use clock date `2026-11-03`

### Money

```json
{ "amount": "1250.00", "currency": "USD" }
```

Amounts are decimal strings with exactly two fractional digits. Do not use floating-point JSON numbers for money. Arithmetic in validators uses `decimal.Decimal`.

### Fixture envelope

Each fixture file is an object, not a bare array:

```json
{
  "synthetic": true,
  "entity": "customer",
  "schema": "customers/customer.schema.json",
  "records": []
}
```

`schema` is relative to `data/schemas/v1/`.

## JSON Schema rules

- `$schema` is `https://json-schema.org/draft/2020-12/schema`.
- `$id` uses the stable identifier `https://ai-solutions-lab.local/schemas/v1/...` and is not a hosted URL.
- Entity objects set `additionalProperties` to `false`.
- Open maps (`extracted_fields`, audit `details`) allow additional properties by design.
- Status and classification fields use `enum`.
- Shared money, address, datetime, and date definitions live in `common.schema.json`.
- Contracts do not mention SQL types, ORM classes, or FastAPI models.

The repository validator implements the Draft 2020-12 **subset used by these files** (`type`, `properties`, `required`, `additionalProperties`, `enum`, `const`, `pattern`, `format`, `minimum`, `maximum`, `minItems`, `uniqueItems`, `$ref`, `$defs`). A full meta-schema engine is not a current dependency.

## Schema versioning and compatibility

Schemas live under `data/schemas/v1/`.

| Change | Compatibility | Action |
|---|---|---|
| Add an optional property | Backward compatible | Keep `v1`, document the field |
| Add an enum value that old writers may omit | Compatible if readers tolerate unknown values in future APIs | Keep `v1` only if existing fixtures remain valid |
| Rename, remove, or tighten a required field | Breaking | Add `data/schemas/v2/` and a mapping note |
| Change money or identifier representation | Breaking | New major version |

Rules:

1. Do not edit `v1` in a way that invalidates committed valid fixtures.
2. `$id` paths include the major version.
3. Fixture envelopes name the major version directory in `schema`.
4. Additive optional fields are preferred over breaking changes while Phase 1–2 are in flight.
5. Record contract breaks in an ADR when application services exist.

## Validation

```bash
python3 scripts/validate_wasatch_domain.py
```

The script:

- Validates every valid record against its schema
- Detects duplicate identifiers
- Checks foreign keys in the valid set
- Checks money, completion, approval, provenance, and status invariants
- Refuses to treat `quality-issues/` as valid business data
- Reports fixture counts

Quality-issue files are schema-checked when they declare a schema, but they are **not** required to satisfy referential or monetary invariants.

## Provenance, approval, and audit

Future adapters must keep:

- Document `source` and `untrusted`
- Extraction `document_id` + `document_version_id`
- Approval `decision_history`
- Audit events insert-only

Those fields exist in v1 so later AI modules can attach to the same contracts without remodeling the business.

## Out of scope

These contracts do not define:

- Authentication principals beyond employee identifiers
- Embedding vectors
- n8n workflow documents
- Physical file bytes (versions point at synthetic `storage_path` values)

Related: [../ARCHITECTURE.md](../ARCHITECTURE.md), [../business/WASATCH_DOMAIN_MODEL.md](../business/WASATCH_DOMAIN_MODEL.md), [../SECURITY.md](../SECURITY.md).
