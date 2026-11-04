# Data

Synthetic laboratory data only.

| Directory | Purpose |
|---|---|
| `schemas/v1/` | JSON Schema Draft 2020-12 contracts |
| `fixtures/valid/` | Internally consistent sample dataset |
| `fixtures/quality-issues/` | Deliberate defects, not valid business data |
| `seed/` | Reserved for future database seed files derived from fixtures |
| `documents/` | Synthetic procedure pages for retrieval. Document-version blobs are not stored here |

Do not add real customer, employee, or financial files. See [../docs/architecture/DATA_CONTRACTS.md](../docs/architecture/DATA_CONTRACTS.md).
