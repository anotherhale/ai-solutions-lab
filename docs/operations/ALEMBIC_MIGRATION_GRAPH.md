# Alembic migration graph (integration branch)

Linear chain on `develop` after open feature work lands:

```
0001 → … → 0009 (development_ops.activity_events)
  → 0010 (invoice_lines — FIN-2, PR #34)
  → 0011 (payments — FIN-3, PR #35)
  → 0012 (development_ops.coordinator_tasks — PR #37)
```

## Conflicts resolved

| Branch | Was | Now |
|---|---|---|
| `cursor/fin-2-invoice-lines-read-513c` | `0010` invoice lines | unchanged (`down_revision=0009`) |
| `cursor/fin-3-payments-read-513c` | `0011` payments | unchanged (`down_revision=0010`) |
| `cursor/coordinator-continuity-ef97` | `0010` coordinator (duplicate id) | **`0012`**, `down_revision=0011` |
| `cursor/development-ops-db-isolation-513c` | no migration | superseded by coordinator branch DB URL split |
| `cursor/development-activity-log-851a` | duplicate Phase 1 | superseded; `0009` already on `develop` |

Do not merge branches with competing `0010` revision ids. Merge order:

1. FIN-2 (#34)
2. FIN-3 (#35) — rebase onto `develop` after FIN-2
3. Coordinator (#37) — includes `0010`/`0011` files for CI graph testing until FIN merges, then drop duplicates on rebase

Pytest migration tests use disposable database **`wasatch_alembic_disposable`**. Operational telemetry uses **`wasatch_development_ops`** only.
