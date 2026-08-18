#!/usr/bin/env bash
set -Eeuo pipefail
umask 027

export APP_ENV="${APP_ENV:-production}"
# Railway ejecuta pre-deploy sin el volumen persistente. Toda salida temporal
# vive en /tmp; PostgreSQL conserva las migraciones y semillas definitivas.
export DATA_DIR="${PREDEPLOY_DATA_DIR:-/tmp/primera-infancia-predeploy}"
mkdir -p "$DATA_DIR/integrity" "$DATA_DIR/migration_reports"

if ! RESOLVED_DATABASE_URL="$(python backend/tools/resolve_postgresql_env.py)"; then
  echo "[PREDEPLOY][ERROR] No se recibió una conexión PostgreSQL de Railway." >&2
  exit 20
fi
export DATABASE_URL="$RESOLVED_DATABASE_URL"
unset RESOLVED_DATABASE_URL

python backend/tools/postgresql_preflight.py \
  --postgres "$DATABASE_URL" \
  --report "$DATA_DIR/integrity/postgresql_preflight.json"

python backend/tools/integrity_gate.py \
  --root /app \
  --report "$DATA_DIR/integrity/integrity_gate_predeploy.json" \
  --skip-tests \
  --skip-manifest

export APP_SCHEMA_MIGRATION_MODE=1
export SKIP_RUNTIME_SCHEMA_DDL=0
python backend/init_hosting.py

echo "[PREDEPLOY] Migraciones, semillas y bootstrap PostgreSQL completados."
