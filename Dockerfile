# Stage 1: Build the Web Frontend
FROM node:22-slim AS web-builder

WORKDIR /app/src/web
# Copy package files for better caching
COPY src/web/package*.json ./
RUN npm ci

# Copy the rest of the web source
COPY src/web/ ./
# Build the production assets
RUN npm run build

# Stage 2: Base builder (shared for backend build and devcontainer)
FROM python:3.13-slim AS base-builder

WORKDIR /app

# Install tooling needed by backend build and DB maintenance commands
RUN apt-get update && apt-get install -y --no-install-recommends binutils postgresql-client && \
    rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Stage 3: Build the Python Backend
FROM base-builder AS backend-builder

# Copy dependency files
COPY pyproject.toml uv.lock README.md ./

# Install dependencies (excluding dev deps) and cleanup venv
RUN uv sync --frozen --no-dev --no-editable && \
    # Strip debug symbols from binary extensions
    find .venv -name "*.so" -exec strip --strip-unneeded {} + && \
    # Cleanup unnecessary files from venv
    find .venv -type d -name "__pycache__" -exec rm -rf {} + && \
    find .venv -type f -name "*.pyc" -delete && \
    find .venv -type d -name "tests" -exec rm -rf {} + && \
    find .venv -type d -name "testing" -exec rm -rf {} + && \
    rm -rf /root/.cache/uv

# Copy Python source code
COPY src/terminal src/terminal

# Stage 4: Dev builder (for devcontainer)
FROM base-builder AS dev-builder

# Devcontainer conveniences (kept out of backend/runtime build path)
RUN apt-get update && apt-get install -y --no-install-recommends git nodejs npm && \
    rm -rf /var/lib/apt/lists/*

# Stage 5: Final Runtime
FROM python:3.13-slim AS runtime

# Runtime dependencies used by CLI maintenance commands (pg_dump/psql)
RUN apt-get update && apt-get install -y --no-install-recommends postgresql-client && \
    rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd --gid 1000 terminal && \
    useradd --uid 1000 --gid terminal --shell /bin/bash --create-home terminal

WORKDIR /app

# Copy the optimized virtual environment
COPY --from=backend-builder --chown=terminal:terminal /app/.venv /app/.venv
# Copy the backend source
COPY --from=backend-builder --chown=terminal:terminal /app/src/terminal /app/src/terminal
# Copy the web dist from web-builder
COPY --from=web-builder --chown=terminal:terminal /app/src/web/dist /app/src/web/dist

# Add venv to PATH
ENV PATH="/app/.venv/bin:$PATH"
ENV PORT=8000
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/src

# Create data directory for local cache
RUN mkdir -p /app/data && chown -R terminal:terminal /app/data

USER terminal

EXPOSE $PORT

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; import os; port = os.getenv('PORT', '8000'); urllib.request.urlopen(f'http://localhost:{port}/health')" || exit 1

CMD ["sh", "-c", "uvicorn terminal.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
