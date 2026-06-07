#!/usr/bin/env bash
# _common.sh — Shared bootstrap for all ops scripts.
#
# SOURCE this file (do not execute it directly):
#   source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
#
# After sourcing, the following are available:
#   EC2_HOST         — resolved public IP of the EC2 instance
#   EC2_KEY          — path to the local private SSH key file
#   EC2_USER         — SSH login user (default: ec2-user)
#   PROJECT_DIR      — absolute path to the project on the remote host
#   COMPOSE_FILE     — path to the production compose file (relative to PROJECT_DIR)
#   SSH_OPTS         — array of SSH options (identity, StrictHostKeyChecking, timeout)
#   SSH_TARGET       — "ec2-user@<ip>" shorthand
#   ssh_run          — function: ssh_run "remote command"
#   ssh_pipe_in      — function: ssh_pipe_in "remote command" < local_file
#   ssh_pipe_out     — function: ssh_pipe_out "remote command" > local_file
#
# ---------------------------------------------------------------------------
# Resolution order for EC2_HOST
# ---------------------------------------------------------------------------
# 1. EC2_HOST environment variable (set in shell or loaded from .scripts.env)
# 2. terraform output -raw ec2_public_ip (requires .terraform/ to be initialised
#    and AWS credentials in the current shell)
# 3. Hard error with actionable message
#
# ---------------------------------------------------------------------------
# Resolution order for EC2_SSH_KEY
# ---------------------------------------------------------------------------
# 1. EC2_SSH_KEY environment variable (path to private key file)
# 2. ~/.ssh/<project_name>-ec2  (project-scoped key — recommended naming)
# 3. ~/.ssh/id_rsa              (fallback to default key)
# 4. Hard error with actionable message
#
# ---------------------------------------------------------------------------
# Quickstart for a new machine without Terraform state
# ---------------------------------------------------------------------------
# Copy scripts/.scripts.env.example → scripts/.scripts.env and fill in:
#
#   EC2_HOST=<elastic-ip>       # From Terraform output, AWS console, or team docs
#   EC2_SSH_KEY=~/.ssh/<key>    # Private key retrieved from your password manager
#
# The scripts load scripts/.scripts.env automatically if present.

set -euo pipefail

SCRIPTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPTS_DIR}/.." && pwd)"

# ---------------------------------------------------------------------------
# Load scripts/.scripts.env if present (gitignored — local overrides only)
# ---------------------------------------------------------------------------
SCRIPTS_ENV_FILE="${SCRIPTS_DIR}/.scripts.env"
if [[ -f "${SCRIPTS_ENV_FILE}" ]]; then
    # shellcheck source=/dev/null
    source "${SCRIPTS_ENV_FILE}"
fi

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
EC2_USER="${EC2_USER:-ec2-user}"
PROJECT_DIR="${REMOTE_PROJECT_DIR:-/opt/myproject}"
COMPOSE_FILE=".docker/production/docker-compose.yaml"
COMPOSE_PATH="${PROJECT_DIR}/${COMPOSE_FILE}"
# Project name in the compose file — used to construct container names
COMPOSE_PROJECT="${COMPOSE_PROJECT:-myproject-prod}"

# ---------------------------------------------------------------------------
# Resolve EC2_HOST
# ---------------------------------------------------------------------------
_resolve_host() {
    if [[ -n "${EC2_HOST:-}" ]]; then
        echo "${EC2_HOST}"
        return
    fi

    local terraform_dir="${REPO_ROOT}/.terraform"
    if [[ -d "${terraform_dir}" ]] && command -v terraform >/dev/null 2>&1; then
        local host
        # Capture output; suppress stderr in case state is uninitialised
        host=$(cd "${terraform_dir}" && terraform output -raw ec2_public_ip 2>/dev/null || true)
        if [[ -n "${host}" ]]; then
            echo "${host}"
            return
        fi
    fi

    cat >&2 <<'ERRMSG'
ERROR: EC2_HOST could not be resolved. Try one of:

  1. Set EC2_HOST in your shell:
       export EC2_HOST=<elastic-ip>

  2. Copy scripts/.scripts.env.example → scripts/.scripts.env and fill in EC2_HOST.

  3. Ensure .terraform/ is initialised and AWS credentials are active so
     Terraform output can be read automatically:
       cd .terraform && terraform init && terraform output ec2_public_ip

  The Elastic IP is available in the AWS console under EC2 → Elastic IPs,
  or was printed at the end of your last `terraform apply`.
ERRMSG
    exit 1
}

# ---------------------------------------------------------------------------
# Resolve EC2_SSH_KEY (path to private key file)
# ---------------------------------------------------------------------------
_resolve_key() {
    if [[ -n "${EC2_SSH_KEY:-}" ]]; then
        # Expand tilde if present
        echo "${EC2_SSH_KEY/#\~/$HOME}"
        return
    fi

    # Derive project name from the repo root directory name
    local project_name
    project_name="$(basename "${REPO_ROOT}")"
    local project_key="${HOME}/.ssh/${project_name}-ec2"

    if [[ -f "${project_key}" ]]; then
        echo "${project_key}"
        return
    fi

    if [[ -f "${HOME}/.ssh/id_rsa" ]]; then
        echo "${HOME}/.ssh/id_rsa"
        return
    fi

    cat >&2 <<ERRMSG
ERROR: SSH key not found. Try one of:

  1. Set EC2_SSH_KEY in your shell:
       export EC2_SSH_KEY=~/.ssh/your-key

  2. Place the private key at: ${project_key}
     (This is the recommended location for the project SSH key.)

  3. Add EC2_SSH_KEY to scripts/.scripts.env:
       EC2_SSH_KEY=~/.ssh/your-key

  The key is the private half of the SSH key pair whose public key was passed
  to Terraform as var.ssh_public_key during infrastructure provisioning.
  Retrieve it from your password manager or team secrets store.
ERRMSG
    exit 1
}

# ---------------------------------------------------------------------------
# Resolve and export
# ---------------------------------------------------------------------------
EC2_HOST="$(_resolve_host)"
EC2_KEY="$(_resolve_key)"

# Verify key file exists and has correct permissions
if [[ ! -f "${EC2_KEY}" ]]; then
    echo "ERROR: SSH key file not found: ${EC2_KEY}" >&2
    exit 1
fi
chmod 600 "${EC2_KEY}" 2>/dev/null || true

SSH_OPTS=(
    -i "${EC2_KEY}"
    -o StrictHostKeyChecking=accept-new
    -o ConnectTimeout=10
    -o ServerAliveInterval=30
    -o ServerAliveCountMax=3
)
SSH_TARGET="${EC2_USER}@${EC2_HOST}"

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

# ssh_run "remote command string"
# Run a command on the EC2 instance.
ssh_run() {
    ssh "${SSH_OPTS[@]}" "${SSH_TARGET}" "$@"
}

# ssh_tty "remote command string"
# Run a command that needs a TTY (e.g. interactive psql).
ssh_tty() {
    ssh "${SSH_OPTS[@]}" -t "${SSH_TARGET}" "$@"
}

# ssh_pipe_in "remote command" < local_file
# Pipe stdin through SSH to a remote command.
ssh_pipe_in() {
    ssh "${SSH_OPTS[@]}" "${SSH_TARGET}" "$@"
}

# compose_run "service" "command..."
# Run a non-interactive docker compose exec on the given service.
compose_run() {
    local service="$1"; shift
    ssh_run "cd ${PROJECT_DIR} && docker compose -f ${COMPOSE_FILE} exec -T ${service} $*"
}
