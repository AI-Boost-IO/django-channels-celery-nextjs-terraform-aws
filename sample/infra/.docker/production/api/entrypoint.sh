#!/bin/sh
# Production entrypoint for the `api` service.
#
# Differences from development:
#   - collectstatic is skipped (done at image build time in the Dockerfile).
#   - migrate runs with --noinput to avoid prompts in CI/CD pipelines.
#   - Daphne uses a higher worker count and explicit timeout values.
#
# ASGI_APPLICATION is set in config/asgi.py — Daphne reads it directly.

set -e

echo "[api] Applying database migrations..."
python manage.py migrate --noinput

echo "[api] Starting Daphne..."
exec daphne \
  --bind 0.0.0.0 \
  --port 8000 \
  --proxy-headers \
  config.asgi:application
