# development-ops

Append-only **Development Activity Log** for AI Solutions Lab. Events live in the
`development_ops` PostgreSQL schema (separate from Wasatch synthetic business
data).

See [docs/operations/DEVELOPMENT_ACTIVITY_LOG.md](../../docs/operations/DEVELOPMENT_ACTIVITY_LOG.md)
for taxonomy, configuration, Slack routing, and recovery.

```bash
python3 -m pip install -e "libs/development_ops[dev]"
development-ops-record record --help
pytest libs/development_ops/tests
```
