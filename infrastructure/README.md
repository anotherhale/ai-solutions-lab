# Infrastructure

Reserved for container and cloud definitions.

- `docker/` holds notes for the root `compose.yaml` local topology.
- `terraform/` will hold Azure infrastructure as code when a cloud environment is actually provisioned. No workspace exists. OPS-1 adds no module, backend, subscription id, tenant id, or credential. See [terraform/README.md](terraform/README.md).

Neither environment is a cloud deployment. Laboratory backup and secret notes are in [../docs/operations/](../docs/operations/). See [../docs/adr/0005-docker-compose-local-development.md](../docs/adr/0005-docker-compose-local-development.md).
