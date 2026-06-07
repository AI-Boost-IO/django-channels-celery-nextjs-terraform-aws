#!/usr/bin/env bash
# db.sh — Postgres access and management for the production database container.
#
# The `db` service does NOT expose port 5432 on the host — all access goes
# through Docker's network via SSH. See the `tunnel` subcommand for GUI tools.
#
# Subcommands:
#
#   psql                      Interactive psql shell (via docker exec over SSH)
#
#   tunnel                    Forward localhost:15432 → db container (for GUI tools).
#                             Connect TablePlus / DBeaver / pgAdmin to:
#                               host=localhost port=15432 user=$POSTGRES_USER
#                             Override the local port: LOCAL_PORT=5555 ./scripts/db.sh tunnel
#
#   dump [file]               Stream pg_dump directly to a local file over SSH.
#                             No temp file is written on the server.
#                             Default filename: db-YYYYMMDD-HHMMSS.dump
#
#   restore <file>            Stream a local dump file to pg_restore over SSH.
#                             No temp file is written on the server.
#                             Prompts for confirmation before running.
#
#   query "<sql>"             Run a single SQL statement and print the result.
#
# Usage examples:
#   ./scripts/db.sh psql
#   ./scripts/db.sh tunnel
#   ./scripts/db.sh dump
#   ./scripts/db.sh dump ./backups/before-migration.dump
#   ./scripts/db.sh restore ./backups/before-migration.dump
#   ./scripts/db.sh query "SELECT count(*) FROM auth_user;"

set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_common.sh"

SUBCOMMAND="${1:-}"

if [[ -z "${SUBCOMMAND}" ]]; then
    echo "Usage: $0 {psql|tunnel|dump [file]|restore <file>|query <sql>}" >&2
    exit 1
fi
shift || true

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Print a labelled header so all subcommands follow the same log style
_header() {
    echo "[db:${SUBCOMMAND}] Host   : ${EC2_HOST}"
    echo "[db:${SUBCOMMAND}] Service: db container (${COMPOSE_PROJECT})"
}

# Get the db container's IP on the Docker bridge network.
# Used by the tunnel subcommand to establish a direct SSH port forward.
_db_container_ip() {
    local container_id
    container_id=$(ssh_run "cd ${PROJECT_DIR} && docker compose -f ${COMPOSE_FILE} ps -q db")
    if [[ -z "${container_id}" ]]; then
        echo "ERROR: db container is not running." >&2
        exit 1
    fi
    ssh_run "docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' ${container_id}"
}

# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------

case "${SUBCOMMAND}" in

    # -------------------------------------------------------------------------
    # psql — interactive shell inside the db container
    # -------------------------------------------------------------------------
    psql)
        _header
        echo ""
        echo "[db:psql] Opening psql shell. Type \\q or Ctrl-D to exit."
        echo ""
        # -T in docker compose exec would disable the TTY; we need -t in SSH instead.
        # The db container has POSTGRES_USER and POSTGRES_DB as environment variables
        # so we can reference them inside the container shell without hard-coding values.
        ssh_tty "cd ${PROJECT_DIR} && docker compose -f ${COMPOSE_FILE} exec db psql -U \"\${POSTGRES_USER}\" \"\${POSTGRES_DB}\""
        ;;

    # -------------------------------------------------------------------------
    # tunnel — SSH local port forward to the db container
    #
    # How it works:
    #   1. Retrieve the db container's IP from the Docker bridge network.
    #      The EC2 host can reach container IPs directly via Docker's routing.
    #   2. Open an SSH local port forward:
    #        localhost:LOCAL_PORT → EC2 host → container_ip:5432
    #   This requires no changes to the container or compose file.
    # -------------------------------------------------------------------------
    tunnel)
        LOCAL_PORT="${LOCAL_PORT:-15432}"

        _header
        echo ""
        echo "[db:tunnel] Resolving db container IP..."
        DB_IP="$(_db_container_ip)"

        if [[ -z "${DB_IP}" ]]; then
            echo "ERROR: Could not determine db container IP. Is the container running?" >&2
            exit 1
        fi

        echo "[db:tunnel] Container IP : ${DB_IP}"
        echo "[db:tunnel] Tunnel       : localhost:${LOCAL_PORT} → ${DB_IP}:5432"
        echo "[db:tunnel] Connect your GUI tool to:"
        echo "              Host:     localhost"
        echo "              Port:     ${LOCAL_PORT}"
        echo "              Database: (same as \$POSTGRES_DB on the server)"
        echo "[db:tunnel] Press Ctrl-C to close the tunnel."
        echo ""

        # -N: do not execute a remote command (tunnel only)
        # -L: local port forwarding
        ssh "${SSH_OPTS[@]}" \
            -L "${LOCAL_PORT}:${DB_IP}:5432" \
            -N \
            "${SSH_TARGET}"
        ;;

    # -------------------------------------------------------------------------
    # dump — stream pg_dump directly from the container to a local file
    #
    # Uses the -Fc (custom format) which is smaller and faster than plain SQL.
    # The dump streams through SSH: container → EC2 → SSH → local disk.
    # No temporary file is written on the server.
    # -------------------------------------------------------------------------
    dump)
        DUMP_FILE="${1:-db-$(date +%Y%m%d-%H%M%S).dump}"

        _header
        echo "[db:dump] Output: ${DUMP_FILE}"
        echo ""

        # pg_dump writes to stdout when no -f flag is given.
        # docker compose exec -T disables TTY allocation so binary data passes cleanly.
        # The output streams: container stdout → SSH stdout → local file.
        ssh_run "cd ${PROJECT_DIR} && docker compose -f ${COMPOSE_FILE} exec -T db \
            sh -c 'pg_dump -U \"\$POSTGRES_USER\" -Fc \"\$POSTGRES_DB\"'" \
            > "${DUMP_FILE}"

        local size
        size=$(du -sh "${DUMP_FILE}" | cut -f1)
        echo "[db:dump] Done. ${DUMP_FILE} (${size})"
        ;;

    # -------------------------------------------------------------------------
    # restore — stream a local dump file to pg_restore inside the container
    #
    # WARNING: Drops and recreates all objects. Use only after taking a fresh
    #          dump or on a non-critical environment.
    #
    # The file streams: local stdin → SSH stdin → container stdin.
    # No temporary file is written on the server.
    # -------------------------------------------------------------------------
    restore)
        DUMP_FILE="${1:-}"

        if [[ -z "${DUMP_FILE}" ]]; then
            echo "Usage: $0 restore <dump-file>" >&2
            exit 1
        fi

        if [[ ! -f "${DUMP_FILE}" ]]; then
            echo "ERROR: File not found: ${DUMP_FILE}" >&2
            exit 1
        fi

        _header
        echo "[db:restore] Source: ${DUMP_FILE} ($(du -sh "${DUMP_FILE}" | cut -f1))"
        echo ""
        echo "WARNING: This will REPLACE the production database on ${EC2_HOST}."
        echo "         All existing data will be overwritten."
        echo ""
        read -rp "         Type YES to confirm: " CONFIRM

        if [[ "${CONFIRM}" != "YES" ]]; then
            echo "Aborted."
            exit 0
        fi

        echo ""
        echo "[db:restore] Streaming dump to pg_restore..."

        # pg_restore reads from stdin when given the '-' argument.
        # docker compose exec -T is required to pass stdin through.
        # The file streams: local file → SSH stdin → container stdin → pg_restore.
        ssh_pipe_in "cd ${PROJECT_DIR} && docker compose -f ${COMPOSE_FILE} exec -T db \
            sh -c 'pg_restore -U \"\$POSTGRES_USER\" -d \"\$POSTGRES_DB\" --clean --if-exists -'" \
            < "${DUMP_FILE}"

        echo "[db:restore] Done."
        ;;

    # -------------------------------------------------------------------------
    # query — run a single SQL statement and print results
    # -------------------------------------------------------------------------
    query)
        SQL="${1:-}"

        if [[ -z "${SQL}" ]]; then
            echo "Usage: $0 query \"<sql>\"" >&2
            exit 1
        fi

        # Pass SQL as a positional argument to psql -c to avoid quoting issues
        # with the intermediate shell layers.
        ssh_run "cd ${PROJECT_DIR} && docker compose -f ${COMPOSE_FILE} exec -T db \
            psql -U \"\${POSTGRES_USER}\" -d \"\${POSTGRES_DB}\" -c $(printf '%q' "${SQL}")"
        ;;

    *)
        echo "Unknown subcommand: ${SUBCOMMAND}" >&2
        echo "Usage: $0 {psql|tunnel|dump [file]|restore <file>|query <sql>}" >&2
        exit 1
        ;;

esac
