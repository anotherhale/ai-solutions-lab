# Backup expectations

Wasatch Business Systems data in this repository is synthetic. No cloud environment is deployed. There is no Terraform workspace, no Azure subscription, and no backup vault.

## What exists today

Local PostgreSQL from root `compose.yaml` stores its data in the Docker volume `wasatch_pg_data`. That volume is local disk for the Compose project. It is a development copy of the synthetic fixtures. It is not a backup, and it is not recovered by any cloud policy.

`docker compose down` leaves the volume in place. `docker compose down -v` deletes it. Seed can load `data/fixtures/valid/` again after the schema is migrated. Audit rows are insert-only, so a re-seed does not rebuild audit history that existed only in the deleted volume.

The API container and the Compose file do not run a collector, Redis, n8n, or a cloud account. GitHub Actions does not store this database.

## Expectations before any cloud deployment

A cloud deployment does not exist. These are the expectations to write into that deployment's design before the first environment is created:

- The system of record is PostgreSQL. A non-production copy still holds synthetic customer, employee, and financial-shaped rows and needs the same care as a real backup: scheduled snapshots, a documented restore, and a retention period.
- Restore is rehearsed on a non-production copy. A backup that has not been restored is an unread file.
- Object storage for document bytes, when a later slice stores bytes, is included in the same restore story. This repository still has no document bytes. Version rows keep `storage_path` strings only.
- Redis, n8n, and a trace collector are not part of the backup set until a slice actually runs them. This slice runs none of them.
- Backup credentials live in the managed secret store for that future deployment. They are not committed, and they are not placed in GitHub Actions.

No module in `infrastructure/terraform/` provisions those resources. Do not add one until a workspace is ready to use it.
