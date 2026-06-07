#!/bin/sh
# Production entrypoint for the `api-beat` service (Celery Beat).
#
# Registers periodic tasks in the DB then starts the Beat scheduler.
# Identical in behaviour to the development variant.
# The register_periodic_tasks command is idempotent — safe on every restart.

set -e

echo "[api-beat] Registering periodic tasks..."
python manage.py register_periodic_tasks

echo "[api-beat] Starting Celery Beat..."
exec celery -A config beat \
  --loglevel=info \
  --scheduler django_celery_beat.schedulers:DatabaseScheduler
