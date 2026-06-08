#!/usr/bin/env bash
# graphql-sync.sh — Export the GraphQL schema from Django and sync it to the
#                   Next.js frontend for codegen.
#
# Steps:
#   1. Run `python manage.py export_schema` in api/ to write schema.graphql
#   2. Copy schema.graphql to ui/src/
#   3. Run `bun run codegen` in ui/ to regenerate __generated__/ types
#      (skip with EXPORT_ONLY=true)
#
# Run this whenever you change a Strawberry type, query, mutation, or subscription.
# Commit both schema.graphql and __generated__/ together so the repo stays consistent.
#
# Usage:
#   ./scripts/graphql-sync.sh
#   EXPORT_ONLY=true ./scripts/graphql-sync.sh   # Export only, skip codegen

set -euo pipefail

SCRIPTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPTS_DIR}/.." && pwd)"
API_DIR="${REPO_ROOT}/api"
UI_DIR="${REPO_ROOT}/ui"
SCHEMA_SRC="${API_DIR}/gql/schema.graphql"
SCHEMA_DST="${UI_DIR}/src/schema.graphql"

# ---------------------------------------------------------------------------
# Step 1: Export schema from Django
# ---------------------------------------------------------------------------
echo "[graphql-sync] Exporting schema from Django (api/)..."

if [[ ! -d "${API_DIR}" ]]; then
    echo "ERROR: api/ directory not found at ${API_DIR}" >&2
    echo "       Run this script from the monorepo root, or ensure api/ exists." >&2
    exit 1
fi

cd "${API_DIR}"

# uv run ensures the correct .venv is used regardless of the active virtualenv
uv run python manage.py export_schema gql.schema --path gql/schema.graphql

echo "[graphql-sync] Schema written to ${SCHEMA_SRC}"

# ---------------------------------------------------------------------------
# Step 2: Copy schema to ui/src/
# ---------------------------------------------------------------------------
echo "[graphql-sync] Copying schema to ${SCHEMA_DST} ..."

if [[ ! -d "${UI_DIR}/src" ]]; then
    echo "ERROR: ui/src/ not found at ${UI_DIR}/src" >&2
    exit 1
fi

cp "${SCHEMA_SRC}" "${SCHEMA_DST}"

# ---------------------------------------------------------------------------
# Step 3: Run codegen (unless EXPORT_ONLY=true)
# ---------------------------------------------------------------------------
if [[ "${EXPORT_ONLY:-false}" == "true" ]]; then
    echo "[graphql-sync] EXPORT_ONLY=true — skipping codegen."
else
    echo "[graphql-sync] Running GraphQL codegen (ui/)..."
    cd "${UI_DIR}"
    bun run codegen
    echo "[graphql-sync] Types regenerated in ui/src/__generated__/"
fi

echo ""
echo "[graphql-sync] Done. Commit both files:"
echo "   ${SCHEMA_SRC}"
echo "   ${SCHEMA_DST}"
echo "   ui/src/__generated__/  (if codegen ran)"
