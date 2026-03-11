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

Coolify note:
- Set the same env vars in Coolify UI (no `env_file` is used in compose).
- Expose port `PORT` (default `8000`, this repo currently uses `8099` in `.env`).

Startup flow:
- `db` starts.
- `app` runs `/app/.venv/bin/python -m terminal.cli database upgrade head` and then starts the API.

Database backup/restore:
- `docker compose exec app /app/.venv/bin/python -m terminal.cli database backup --output /app/data/backup.sql`
- `docker compose exec app /app/.venv/bin/python -m terminal.cli database restore /app/data/backup.sql --yes`

## Devcontainer Env

Devcontainer uses its own env file under `.devcontainer/` (not root `.env`).

1. Create devcontainer env:
   `cp .devcontainer/.env.example .devcontainer/.env`
2. Fill required values (especially `OCI_*`, `SECRET_KEY`, `ENCRYPTION_KEY`).
3. Rebuild/reopen the devcontainer.
