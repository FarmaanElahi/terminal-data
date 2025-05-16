FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

# Install deps
RUN apt-get update && apt-get install -y \
    wget gcc g++ make curl \
    && rm -rf /var/lib/apt/lists/*

ENV PATH="/root/.cargo/bin:$PATH"

# Install TA-Lib
RUN ARCH=$(dpkg --print-architecture) && \
    echo "Detected architecture: $ARCH" && \
    case "$ARCH" in \
        amd64) TA_URL="https://github.com/ta-lib/ta-lib/releases/download/v0.6.3/ta-lib_0.6.3_amd64.deb" ;; \
        arm64) TA_URL="https://github.com/ta-lib/ta-lib/releases/download/v0.6.3/ta-lib_0.6.3_arm64.deb" ;; \
        *) echo "Unsupported architecture: $ARCH" && exit 1 ;; \
    esac && \
    wget "$TA_URL" -O /tmp/ta-lib.deb && \
    dpkg -i /tmp/ta-lib.deb && \
    rm /tmp/ta-lib.deb

# Set working dir and copy code
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --locked

COPY . .

# Use main.py as startup
ENTRYPOINT ["/app/.venv/bin/python3", "main.py"]
CMD ["--help"]