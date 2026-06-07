#!/usr/bin/env bash
# deploy.sh — Manual deploy: git pull the latest code and restart services.
#
# Automated deploys run via .github/workflows/deploy.yml on every push to main.
# Use this script for emergency redeploys, hotfixes, or bootstrapping a server
# before CI is configured.
#
# What it does (mirrors deploy.yml):
#   1. cd into PROJECT_DIR on the remote host
#   2. git pull origin main
#   3. docker compose pull api  (new image from GHCR)
#   4. docker compose up -d --remove-orphans
#   5. docker image prune -f
#
# Usage:
#   ./scripts/deploy.sh

set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"

echo "[deploy] Target : ${EC2_USER}@${EC2_HOST}"
echo "[deploy] Project: ${PROJECT_DIR}"
echo ""

ssh_run bash -s << REMOTE
set -euo pipefail

cd "${PROJECT_DIR}"

echo "[deploy] Pulling latest code..."
git pull origin main

echo "[deploy] Pulling latest API image from GHCR..."
docker compose -f "${COMPOSE_FILE}" pull api

echo "[deploy] Restarting all services..."
docker compose -f "${COMPOSE_FILE}" up -d --remove-orphans

echo "[deploy] Pruning dangling images..."
docker image prune -f

echo "[deploy] Done — \$(date -u +%Y-%m-%dT%H:%M:%SZ)"

echo ""
echo "[deploy] Service status:"
docker compose -f "${COMPOSE_FILE}" ps
REMOTE
