#!/bin/sh
# Development entrypoint for the `api` service (Daphne ASGI server).
#
# Runs on every container start:
#   1. Apply any pending database migrations.
#   2. Start Daphne — the ASGI server that handles both HTTP (GraphQL) and WebSocket.
#
# Daphne is configured to listen on all interfaces (0.0.0.0) so requests
# from other Docker services and the host machine can reach it.
#
# ASGI_APPLICATION is read from config/asgi.py which routes:
#   HTTP  → GraphQL HTTP consumer (queries + mutations)
#   WS    → GraphQL WebSocket consumer (subscriptions)

set -e

echo "[api] Applying database migrations..."
python manage.py migrate --noinput

echo "[api] Starting Daphne..."
exec daphne \
  --bind 0.0.0.0 \
  --port 8000 \
  config.asgi:application
