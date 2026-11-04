# Docker

Local Compose is defined at the repository root as `compose.yaml` so `docker compose up` works from a clone.

This directory remains the place for additional container notes. Redis and n8n are not started yet.

```bash
docker compose up -d postgres            # or docker-compose
docker compose down                      # keeps the wasatch_pg_data volume
docker compose down -v                   # destroys local data; not part of normal shutdown
```
