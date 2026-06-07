#!/bin/sh
# Development entrypoint for the `api-beat` service (Celery Beat scheduler).
#
# Runs on every container start:
#   1. Register (or update) periodic tasks in the DB scheduler.
#      This command is idempotent — safe to re-run on every restart.
#      Tasks are visible and editable in Django admin after this runs.
#   2. Start Celery Beat with the DB-backed scheduler.
#
# The Beat service does NOT handle task execution — it only enqueues tasks
# on the Redis broker at the scheduled times. The `api-worker` service picks them up.

set -e

echo "[api-beat] Registering periodic tasks..."
python manage.py register_periodic_tasks

echo "[api-beat] Starting Celery Beat..."
exec celery -A config beat \
  --loglevel=info \
  --scheduler django_celery_beat.schedulers:DatabaseScheduler
