#!/usr/bin/env bash
set -euo pipefail

cd /app

echo "[devcontainer] Syncing Python dependencies..."
uv sync

echo "[devcontainer] Ensuring web dependencies..."
cd /app/src/web
if ! node -e "import('rollup').then(() => process.exit(0)).catch(() => process.exit(1))" >/dev/null 2>&1; then
  echo "[devcontainer] Installing web dependencies (with optional packages)..."
  if ! npm ci --include=optional; then
    echo "[devcontainer] npm ci failed; retrying with clean npm install (npm optional-deps workaround)..."
    rm -rf node_modules
    npm install --include=optional
  fi
fi

if ! node -e "import('rollup').then(() => process.exit(0)).catch(() => process.exit(1))" >/dev/null 2>&1; then
  echo "[devcontainer] Rollup is still unavailable after install. Please check npm logs."
  exit 1
fi

cd /app

echo "[devcontainer] Applying database migrations..."
attempts=30
migrated=0
for i in $(seq 1 "$attempts"); do
  if uv run terminal database upgrade head; then
    echo "[devcontainer] Migrations applied."
    migrated=1
    break
  fi

  echo "[devcontainer] Migration attempt $i/$attempts failed; retrying in 2s..."
  sleep 2
done

if [ "$migrated" -eq 1 ]; then
  exit 0
fi

echo "[devcontainer] Failed to apply migrations after $attempts attempts."
exit 1
