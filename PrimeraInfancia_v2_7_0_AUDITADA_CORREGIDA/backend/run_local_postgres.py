"""Arranque local mínimo y exclusivo para PostgreSQL."""
from __future__ import annotations

import os
import faulthandler
from pathlib import Path

from config import normalize_database_url


def main() -> None:
    database_url = normalize_database_url(os.getenv("DATABASE_URL", ""))
    if not database_url.startswith("postgresql+psycopg://"):
        raise SystemExit("DATABASE_URL debe apuntar a PostgreSQL; SQLite está deshabilitado.")

    # Se fija antes de importar app porque la configuración se evalúa al importar.
    os.environ["DATABASE_URL"] = database_url
    os.environ.setdefault("APP_ENV", "development")
    os.environ.setdefault("FLASK_ENV", "development")
    os.environ.setdefault("FLASK_HOST", "127.0.0.1")
    os.environ.setdefault("FLASK_PORT", "5000")
    os.environ.setdefault("ENABLE_POSTGRESQL_RUNTIME", "true")
    os.environ.setdefault("REQUIRE_POSTGRESQL_IN_PRODUCTION", "true")
    os.environ.setdefault("SKIP_RUNTIME_SCHEMA_DDL", "true")
    os.environ["FORCE_HTTPS"] = "false"
    os.environ["SESSION_COOKIE_SECURE"] = "false"
    os.environ["TRUSTED_PROXY_COUNT"] = "0"

    trace_path = Path(__file__).resolve().parents[1] / 'data' / 'logs' / 'startup_postgres_trace.log'
    trace_path.parent.mkdir(parents=True, exist_ok=True)
    trace_handle = trace_path.open('w', encoding='utf-8')
    faulthandler.dump_traceback_later(20, repeat=True, file=trace_handle)

    from app import app

    faulthandler.cancel_dump_traceback_later()
    trace_handle.close()

    host = os.environ["FLASK_HOST"]
    port = int(os.environ["FLASK_PORT"])
    print(f"Plataforma local conectada a PostgreSQL: http://{host}:{port}/frontend/index.html")
    app.run(host=host, port=port, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
