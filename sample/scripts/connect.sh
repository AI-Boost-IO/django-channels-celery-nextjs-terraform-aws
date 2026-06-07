#!/usr/bin/env bash
# connect.sh — Open an interactive SSH shell on the EC2 instance.
#
# Usage:
#   ./scripts/connect.sh
#
# EC2_HOST and EC2_SSH_KEY are resolved by _common.sh — see that file for
# the full resolution order (env var → Terraform output → error).

set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"

echo "[connect] Connecting to ${EC2_USER}@${EC2_HOST} ..."
echo "[connect] Project directory: ${PROJECT_DIR}"
echo ""

exec ssh "${SSH_OPTS[@]}" "${SSH_TARGET}"
