# Alembic integration test matrix

These tests run against PostgreSQL with pgvector. CI sets `WASATCH_REQUIRE_DATABASE=1` and fails if they are skipped.

Each revision below has a dedicated integration test that downgrades one step (or to `base` for `0001`), asserts schema state, upgrades back, and restores seed data where the session fixture expects it.

| Revision | Migration module | Integration test |
|---|---|---|
| `0001` | `0001_initial_wasatch_slice.py` | `test_initial_migration.py` |
| `0002` | `0002_customer_service_slice.py` | `test_customer_service_migration.py` |
| `0003` | `0003_governance_slice.py` | `test_governance_migration.py` |
| `0004` | `0004_workforce_slice.py` | `test_workforce_migration.py` |
| `0005` | `0005_documents_slice.py` | `test_documents_migration.py` |
| `0006` | `0006_procedure_embeddings.py` | `test_procedure_embedding_migration.py` |
| `0007` | `0007_follow_up_visits.py` | `test_follow_up_visit_migration.py` |
| `0008` | `0008_work_order_invoice_fk.py` | `test_invoice_migration.py` |

Add a row to this table when a new Alembic revision ships. Downgrade coverage is required when `downgrade()` is implemented and safe on the synthetic database.
