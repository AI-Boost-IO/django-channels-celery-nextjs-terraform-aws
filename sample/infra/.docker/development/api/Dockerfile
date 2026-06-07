# Development API Dockerfile — Python 3.12 + uv
#
# This image is used for the `api`, `api-beat`, and `api-worker` services.
# In development, the source tree is volume-mounted at /app so code changes
# are reflected immediately without rebuilding the image.
#
# The Dockerfile only installs dependencies; source code is NOT COPY'd —
# it is provided at runtime via the volume mount in docker-compose.yaml.
#
# Install Python dependencies with uv for speed.
# uv 0.11.19 is pinned for reproducibility.

FROM python:3.12-slim AS base

# Prevent .pyc files and enable unbuffered stdout/stderr for clean Docker logs
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    # Place uv-managed binaries on PATH
    PATH="/root/.local/bin:$PATH"

WORKDIR /app

# Install system dependencies required by psycopg2 and Pillow
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
  && rm -rf /var/lib/apt/lists/*

# Install uv — fast Python package manager that replaces pip in this project
RUN curl -LsSf https://astral.sh/uv/0.11.19/install.sh | sh

# Copy only the dependency manifest first so Docker can cache this layer.
# The source is mounted at runtime, so we skip COPY . .
COPY pyproject.toml uv.lock* ./

# Install all dependencies (including dev extras) from the lock file.
# --no-install-project: installs deps only, not the project itself (no src layout needed).
RUN uv sync --frozen --no-install-project

# Copy entrypoint scripts for all three service roles.
# These are baked into the image; the docker-compose `command` selects which one to run.
COPY ../.docker/development/api/entrypoint.sh /entrypoint.sh
COPY ../.docker/development/api-beat/entrypoint.sh /entrypoint-beat.sh
COPY ../.docker/development/api-worker/entrypoint.sh /entrypoint-worker.sh

RUN chmod +x /entrypoint.sh /entrypoint-beat.sh /entrypoint-worker.sh

EXPOSE 8000
