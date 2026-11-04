# development-ops

Append-only **Development Activity Log** for AI Solutions Lab. Events live in the
`development_ops` schema on database **`wasatch_development_ops`** (separate from
Wasatch `wasatch` and pytest `wasatch_test`).

See [docs/operations/DEVELOPMENT_ACTIVITY_LOG.md](../../docs/operations/DEVELOPMENT_ACTIVITY_LOG.md)
for taxonomy, configuration, Slack routing, and recovery.

```bash
python3 -m pip install -e "libs/development_ops[dev]"
development-ops-record record --help
pytest libs/development_ops/tests
```
