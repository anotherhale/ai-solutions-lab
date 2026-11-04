# Docker

Local Compose is defined at the repository root as `compose.yaml` so `docker compose up` works from a clone.

This directory remains the place for additional container notes. Compose does not run a collector, Redis, or n8n. The API exports spans only when the process has `OTEL_EXPORTER_OTLP_ENDPOINT` set. The Compose file does not set that variable.

```bash
docker compose up -d postgres            # or docker-compose
docker compose down                      # keeps the wasatch_pg_data volume
docker compose down -v                   # destroys local data; not part of normal shutdown
```
