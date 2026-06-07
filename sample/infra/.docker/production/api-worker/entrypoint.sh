#!/bin/sh
# Production entrypoint for the `api-worker` service (Celery worker).
#
# Runs with higher concurrency than development — tune WORKER_CONCURRENCY
# based on the EC2 instance CPU count (a good default is 2× vCPU count).
#
# --without-gossip/mingle/heartbeat: disables intra-worker communication
# protocols that are unnecessary on a single-instance deployment and add
# unnecessary Redis traffic.

set -e

echo "[api-worker] Starting Celery worker..."
exec celery -A config worker \
  --loglevel=info \
  --concurrency="${WORKER_CONCURRENCY:-4}" \
  --queues=celery \
  --without-gossip \
  --without-mingle \
  --without-heartbeat
