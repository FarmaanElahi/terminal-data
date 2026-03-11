## Environment Setup

This project uses a single root compose file: `docker-compose.yaml`.

1. Create your runtime env file:
   `cp .env.example .env`
2. Fill required values in `.env`:
   - external DB: `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`
   - security: `SECRET_KEY`, `ENCRYPTION_KEY`
   - OCI: `OCI_BUCKET`, `OCI_CONFIG`, `OCI_KEY`
3. Start services:
   `docker compose up -d --build`

Startup flow:
- `configurator` runs `database upgrade head` with retries.
- `app` starts only after configurator succeeds.

## Devcontainer Env

Devcontainer uses its own env file under `.devcontainer/` (not root `.env`).

1. Create devcontainer env:
   `cp .devcontainer/.env.example .devcontainer/.env`
2. Fill required values (especially `OCI_*`, `SECRET_KEY`, `ENCRYPTION_KEY`).
3. Rebuild/reopen the devcontainer.
