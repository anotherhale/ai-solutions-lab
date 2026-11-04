# Seed Data

Operational seed loading is implemented by `wasatch-api seed`.

That command imports `data/fixtures/valid/` into PostgreSQL. It does not copy files into this directory, and it never loads `data/fixtures/quality-issues/`.

See [../../services/wasatch-api/README.md](../../services/wasatch-api/README.md).
