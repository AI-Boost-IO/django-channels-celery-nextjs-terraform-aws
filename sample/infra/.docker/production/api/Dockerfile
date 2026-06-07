# Production API Dockerfile — multi-stage build, non-root user
#
# Stage 1 (builder): install Python dependencies with uv into an isolated layer.
# Stage 2 (runtime): copy only the installed packages and source code.
#
# Why multi-stage:
#   - The builder stage has build tools (gcc, libpq-dev) needed to compile
#     psycopg2 and other C extensions.
#   - The runtime stage is a clean slim image without those tools,
#     reducing the final image size significantly.
#
# uv 0.11.19 is pinned for reproducibility.

# ---------------------------------------------------------------------------
# Stage 1: builder — install deps
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/root/.local/bin:$PATH"

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
  && rm -rf /var/lib/apt/lists/*

# Install uv
RUN curl -LsSf https://astral.sh/uv/0.11.19/install.sh | sh

# Copy dependency manifests — Docker caches this layer until they change
COPY pyproject.toml uv.lock* ./

# Install production dependencies only (no dev extras)
# --no-install-project: we'll copy the source separately
RUN uv sync --frozen --no-dev --no-install-project

# Copy the full Django project source
COPY . .

# ---------------------------------------------------------------------------
# Stage 2: runtime — clean slim image
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    # Point to the uv virtual environment created in the builder stage
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# Runtime system dependencies only — no build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
  && rm -rf /var/lib/apt/lists/*

# Copy installed packages and source from the builder stage
COPY --from=builder /app /app

# Collect static files into STATIC_ROOT for WhiteNoise to serve
RUN python manage.py collectstatic --noinput --settings=config.settings.production

# Entrypoint scripts for all three service roles — baked into the image
COPY .docker/production/api/entrypoint.sh /entrypoint.sh
COPY .docker/production/api-beat/entrypoint.sh /entrypoint-beat.sh
COPY .docker/production/api-worker/entrypoint.sh /entrypoint-worker.sh

RUN chmod +x /entrypoint.sh /entrypoint-beat.sh /entrypoint-worker.sh

# Run as a non-root user to limit container privileges
RUN useradd --create-home --uid 1001 appuser
USER appuser

EXPOSE 8000
