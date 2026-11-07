# ADR 0011: Test database isolation for operational telemetry

- Status: Accepted
- Date: 2026-11-06

## Context

The development activity log and coordinator state live in the operational
`wasatch_development_ops` PostgreSQL database (ADR 0008, ADR 0009). Pytest must
use a disposable database so a test run never erases real telemetry.

A defect allowed the opposite. The coordinator integration tests resolved their
database through `wasatch_development_ops_database_url_for_tests()`, which:

1. returned `DEVELOPMENT_OPS_DATABASE_URL` verbatim when it was set — including
   the operational URL that laboratory agents export for their own runs; and
2. otherwise derived a URL whose database name was `wasatch_development_ops`.

The `ops_engine` fixture then ran `DROP DATABASE IF EXISTS` / `CREATE DATABASE`
and an autouse fixture ran `DELETE FROM development_ops.activity_events`. Running
`pytest tests/integration/test_coordinator_continuity.py` therefore dropped and
recreated the operational database, erasing recorded activity events. A sentinel
row inserted before the run did not survive it. The defect predated the Phase A
work and shipped on `ai-dev`.

## Decision

Test helpers resolve only to disposable databases, and destructive SQL is
guarded.

- `wasatch_api.testing.postgres` gains an explicit allow-list
  (`DISPOSABLE_TEST_DATABASES`) and a deny-list (`OPERATIONAL_DATABASES`:
  `wasatch`, `wasatch_development_ops`, `postgres`, `template0`, `template1`).
- `assert_disposable_test_database(url)` and `assert_engine_is_disposable(engine)`
  raise `UnsafeTestDatabaseError` for any database that is not disposable. The
  check runs before any connection, so an operational URL is rejected without
  touching the server.
- `wasatch_test_database_url()` keeps its existing precedence and additionally
  refuses an explicit `WASATCH_TEST_DATABASE_URL` that names an operational
  database.
- The operational-ops helper is replaced by
  `wasatch_development_ops_test_database_url()`, which resolves to the
  disposable `wasatch_development_ops_test` and never to
  `wasatch_development_ops`, even when `DEVELOPMENT_OPS_DATABASE_URL` points at
  the operational database. An explicit `DEVELOPMENT_OPS_TEST_DATABASE_URL` is
  honored only when it is disposable.
- `drop_and_recreate_test_database(url)` centralizes the drop/create dance behind
  the guard.
- `tests/conftest.py` provides `ops_test_database_url` and `ops_test_engine`
  fixtures on the disposable database. `alembic/env.py` resolves its URL from
  application settings, so `WASATCH_DATABASE_URL` is pointed at the disposable
  database only for the duration of the migration and then restored.

## Alternatives Considered

- **Keep one shared `wasatch_development_ops` database and only delete the rows
  a test created.** Rejected: any test that drops or downgrades the schema would
  still destroy unrelated telemetry, and cleanup would depend on every test being
  correct.
- **Trust `DEVELOPMENT_OPS_DATABASE_URL` and document "unset it before pytest".**
  Rejected: the failure mode is silent data loss, and a human or agent export is
  exactly the situation that produced the defect.
- **A pytest plugin that rewrites every database URL at collection time.**
  Deferred: heavier than needed, and it would hide the URL from the test that
  wants to assert on it.

## Consequences

- Pytest creates and drops `wasatch_development_ops_test`; operational telemetry
  is never a test target. Verified by a sentinel row that survives the full
  suite.
- Unit tests assert the guard for operational, maintenance, unknown, and missing
  database names; an integration test asserts the fixtures resolve to the
  disposable database.
- New tests that need the ops schema must request `ops_test_engine` (or
  `ops_test_database_url`) rather than resolving a URL themselves.
- The disposable database name must keep a `_test` or `_disposable` suffix to be
  recognized, which keeps accidental names out of the allow-list.
