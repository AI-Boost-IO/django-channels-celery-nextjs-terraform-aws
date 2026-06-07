#!/usr/bin/env bash
# logs.sh — Stream or dump logs from production Docker services.
#
# Usage:
#   ./scripts/logs.sh                          # All services — last 100 lines, then follow
#   ./scripts/logs.sh api                      # api service only, follow
#   ./scripts/logs.sh api-worker               # Celery worker logs
#   ./scripts/logs.sh api-beat                 # Celery Beat scheduler logs
#   ./scripts/logs.sh db                       # Postgres logs
#   ./scripts/logs.sh traefik                  # Traefik access + TLS logs
#   ./scripts/logs.sh api --tail 500           # Last 500 lines of api, then follow
#   ./scripts/logs.sh api --no-follow          # Dump last 100 lines without following
#   ./scripts/logs.sh api --tail all           # Full log history without following
#
# Services: api | api-worker | api-beat | db | cache | traefik

set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"

# ---------------------------------------------------------------------------
# Parse arguments
# ---------------------------------------------------------------------------
SERVICE=""
TAIL="100"
FOLLOW=true

while [[ $# -gt 0 ]]; do
    case "$1" in
        --tail)
            TAIL="$2"
            shift 2
            ;;
        --no-follow)
            FOLLOW=false
            shift
            ;;
        -*)
            echo "Unknown option: $1" >&2
            echo "Usage: $0 [service] [--tail N|all] [--no-follow]" >&2
            exit 1
            ;;
        *)
            if [[ -z "${SERVICE}" ]]; then
                SERVICE="$1"
            else
                echo "Unexpected argument: $1" >&2
                exit 1
            fi
            shift
            ;;
    esac
done

# Build docker compose logs flags
FOLLOW_FLAG=""
if [[ "${FOLLOW}" == true ]]; then
    FOLLOW_FLAG="--follow"
fi

TAIL_FLAG="--tail ${TAIL}"
if [[ "${TAIL}" == "all" ]]; then
    TAIL_FLAG="--no-log-prefix"
fi

# ---------------------------------------------------------------------------
# Stream logs
# ---------------------------------------------------------------------------
echo "[logs] Host    : ${EC2_HOST}"
echo "[logs] Service : ${SERVICE:-all}"
echo "[logs] Tail    : ${TAIL} | Follow: ${FOLLOW}"
echo "[logs] Press Ctrl-C to stop."
echo ""

# -t allocates a pseudo-TTY so Ctrl-C propagates correctly when following
ssh_tty "cd ${PROJECT_DIR} && docker compose -f ${COMPOSE_FILE} logs ${FOLLOW_FLAG} --tail ${TAIL} ${SERVICE}"
