# Production API Dockerfile — multi-stage build, non-root user
#
# Stage 1 (builder): install Python dependencies with uv into /app/.venv.
# Stage 2 (runtime): copy only the installed packages and source code.
#
# Why multi-stage:
#   - The builder stage has build tools (gcc, libpq-dev) needed to compile
#     psycopg2 and other C extensions.
#   - The runtime stage is a clean slim image without those tools,
#     reducing the final image size significantly.
#
# Venv location:
#   /app/.venv is correct for production — there is no source volume mount
#   that could shadow it (unlike development, where UV_PROJECT_ENVIRONMENT=/venv
#   is required to keep the venv out of /app). COPY --from=builder /app /app
#   includes the venv, so PATH="/app/.venv/bin:$PATH" works as expected.

# ---------------------------------------------------------------------------
# Stage 1: builder — install deps
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Build tools needed to compile C extensions (psycopg2, etc.).
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
  && rm -rf /var/lib/apt/lists/*

# Install uv from the official distroless image — no curl pipe-to-shell needed.
COPY --from=ghcr.io/astral-sh/uv:0.11.19 /uv /usr/local/bin/uv

# Copy dependency manifests — Docker caches this layer until they change.
COPY pyproject.toml uv.lock* ./

# Install production dependencies only (no dev extras) into /app/.venv.
# --no-install-project: we'll copy the source separately.
RUN uv sync --frozen --no-dev --no-install-project

# Copy the full Django project source.
COPY . .

# ---------------------------------------------------------------------------
# Stage 2: runtime — clean slim image
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    # /app/.venv is safe in production — no source volume mount shadows it.
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# Runtime system dependencies:
#   libpq5  — shared library required by psycopg2 at runtime (no build tools needed)
#   curl    — used by health check scripts (e.g. curl -f http://localhost:8000/health/)
#             Do NOT omit curl: health checks and monitoring scripts depend on it.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
  && rm -rf /var/lib/apt/lists/*

# Copy installed packages and source from the builder stage.
COPY --from=builder /app /app

# Collect static files into STATIC_ROOT for WhiteNoise to serve.
RUN python manage.py collectstatic --noinput --settings=config.settings.production

# Entrypoint scripts for all three service roles — baked into the image.
COPY .docker/production/api/entrypoint.sh /entrypoint.sh
COPY .docker/production/api-beat/entrypoint.sh /entrypoint-beat.sh
COPY .docker/production/api-worker/entrypoint.sh /entrypoint-worker.sh

RUN chmod +x /entrypoint.sh /entrypoint-beat.sh /entrypoint-worker.sh

# Run as a non-root user to limit container privileges.
RUN useradd --create-home --uid 1001 appuser
USER appuser

EXPOSE 8000
