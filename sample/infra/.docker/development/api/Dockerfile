# Development API Dockerfile — Python 3.12 + uv
#
# This image is used for the `api`, `api-beat`, and `api-worker` services.
# In development, the source tree is volume-mounted at /app so code changes
# are reflected immediately without rebuilding the image.
#
# The Dockerfile only installs dependencies; source code is NOT COPY'd —
# it is provided at runtime via the volume mount in docker-compose.yaml.
#
# IMPORTANT — venv location:
#   UV_PROJECT_ENVIRONMENT is set to /venv (outside /app).
#   This prevents the venv from being hidden by the `volumes` source mount
#   (../../../../api:/app) that Docker Compose applies at runtime.
#   If the venv were at /app/.venv (the uv default), the mount would shadow it
#   and every entrypoint would fail with "ModuleNotFoundError: No module named django".

FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    # Store the venv outside the source mount so it survives the volume overlay.
    UV_PROJECT_ENVIRONMENT=/venv \
    # /venv/bin first so the venv Python is used by bare `python` / `celery` / `daphne`.
    PATH="/venv/bin:$PATH"

WORKDIR /app

# System dependencies:
#   build-essential + libpq-dev  — compile psycopg2 C extension
#   curl                         — used by health check scripts (curl -f http://localhost:8000/health/)
#                                  Do NOT remove curl when switching to COPY --from=uv;
#                                  health checks fail without it.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
  && rm -rf /var/lib/apt/lists/*

# Install uv from the official distroless image — no curl pipe-to-shell needed.
# Pin the version here to match any uv-specific features used in pyproject.toml.
COPY --from=ghcr.io/astral-sh/uv:0.11.19 /uv /usr/local/bin/uv

# Copy only the dependency manifest first so Docker can cache this layer.
# The source is mounted at runtime, so we skip COPY . .
COPY pyproject.toml uv.lock* ./

# Install all dependencies (including dev extras) into /venv.
# --no-install-project: installs deps only, not the project package itself.
RUN uv sync --frozen --no-install-project

# Copy entrypoint scripts for all three service roles.
# These are baked into the image; the docker-compose `command` selects which one to run.
COPY ../.docker/development/api/entrypoint.sh /entrypoint.sh
COPY ../.docker/development/api-beat/entrypoint.sh /entrypoint-beat.sh
COPY ../.docker/development/api-worker/entrypoint.sh /entrypoint-worker.sh

RUN chmod +x /entrypoint.sh /entrypoint-beat.sh /entrypoint-worker.sh

EXPOSE 8000
