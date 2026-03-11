## Environment Setup

This project uses a single root compose file: `docker-compose.yaml`.

1. Create your runtime env file:
   `cp .env.example .env`
2. Fill required values in `.env`:
   - DB container credentials: `DB_USER`, `DB_PASSWORD`, `DB_NAME` (`DB_HOST=db`, `DB_PORT=5432`)
   - security: `SECRET_KEY`, `ENCRYPTION_KEY`
   - OCI: `OCI_BUCKET`, `OCI_CONFIG`, `OCI_KEY`
3. Start services:
   `docker compose up -d`

Startup flow:
- `db` starts first and becomes healthy.
- `configurator` runs `/app/.venv/bin/python -m terminal.cli database upgrade head`.
- `app` starts only after configurator succeeds.

Database backup/restore:
- `docker compose exec app terminal database backup --output /app/data/backup.sql`
- `docker compose exec app terminal database restore /app/data/backup.sql --yes`

## Devcontainer Env

Devcontainer uses its own env file under `.devcontainer/` (not root `.env`).

1. Create devcontainer env:
   `cp .devcontainer/.env.example .devcontainer/.env`
2. Fill required values (especially `OCI_*`, `SECRET_KEY`, `ENCRYPTION_KEY`).
3. Rebuild/reopen the devcontainer.
