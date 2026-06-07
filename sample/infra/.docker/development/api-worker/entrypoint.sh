#!/bin/sh
# Development entrypoint for the `api-worker` service (Celery worker).
#
# Starts a Celery worker that consumes tasks from the Redis broker.
# The worker processes tasks dispatched by:
#   - GraphQL mutations via task.delay() calls
#   - Celery Beat via the periodic task schedule
#
# In development, a single worker with concurrency=2 is sufficient.
# In production (.docker/production/api-worker/entrypoint.sh), concurrency
# is set higher based on the EC2 instance's CPU count.
#
# --autoscale is an alternative to fixed concurrency — it scales between
# min and max workers based on queue depth.

set -e

echo "[api-worker] Starting Celery worker..."
exec celery -A config worker \
  --loglevel=info \
  --concurrency=2 \
  --queues=celery \
  --without-gossip \
  --without-mingle \
  --without-heartbeat
