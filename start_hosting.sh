#!/usr/bin/env bash
set -Eeuo pipefail
umask 027

export APP_ENV="${APP_ENV:-production}"
export DATA_DIR="${DATA_DIR:-${RAILWAY_VOLUME_MOUNT_PATH:-/data}}"
export PORT="${PORT:-5000}"

# Railway monta el volumen en tiempo de ejecución. El proceso de entrada puede
# preparar sus permisos como root, pero Flask/Gunicorn nunca queda ejecutándose
# con privilegios de root.
if [[ "$(id -u)" -eq 0 ]]; then
  mkdir -p "$DATA_DIR"
  chown -R appuser:appuser "$DATA_DIR"
  exec gosu appuser "$0" "$@"
fi

mkdir -p "$DATA_DIR" "$DATA_DIR/integrity" "$DATA_DIR/migration_reports"

if [[ "${APP_ENV}" == "production" ]]; then
  if [[ -z "${DATABASE_URL:-}" ]]; then
    echo "[ERROR] DATABASE_URL PostgreSQL es obligatoria en producción." >&2
    exit 20
  fi
  python backend/tools/postgresql_preflight.py \
    --postgres "$DATABASE_URL" \
    --report "$DATA_DIR/integrity/postgresql_preflight.json"
fi

# Gate rápido y no destructivo: bloquea despliegues con capacidades críticas ausentes.
python backend/tools/integrity_gate.py \
  --root /app \
  --report "$DATA_DIR/integrity/integrity_gate_startup.json" \
  --skip-tests \
  --skip-manifest

python backend/init_hosting.py

# PostgreSQL elimina la contención del archivo SQLite. Se conserva un worker por
# omisión porque algunos jobs operativos aún son memoria local; puede aumentarse
# GUNICORN_WORKERS después de externalizar esos jobs.
exec gunicorn \
  --chdir backend \
  --bind "0.0.0.0:${PORT}" \
  --workers "${GUNICORN_WORKERS:-1}" \
  --worker-class gthread \
  --threads "${GUNICORN_THREADS:-4}" \
  --timeout "${GUNICORN_TIMEOUT:-300}" \
  --graceful-timeout 60 \
  --keep-alive 5 \
  --access-logfile - \
  --error-logfile - \
  --capture-output \
  wsgi:application
