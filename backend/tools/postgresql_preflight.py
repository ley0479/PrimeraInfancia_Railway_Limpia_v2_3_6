#!/usr/bin/env python3
"""Preflight no destructivo de PostgreSQL para despliegue y migración.

Comprueba conectividad, primario escribible, privilegios del esquema y una
transacción temporal. No crea estructuras permanentes ni modifica datos de
negocio.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, text

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from config import normalize_database_url  # noqa: E402
from tools.migrate_sqlite_to_postgresql import masked_url, quote_identifier  # noqa: E402


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def add_check(report: dict[str, Any], name: str, ok: bool, detail: Any = None) -> None:
    report["checks"].append({"name": name, "status": "PASS" if ok else "FAIL", "detail": detail})


def main() -> int:
    parser = argparse.ArgumentParser(description="Preflight PostgreSQL Primera Infancia")
    parser.add_argument("--postgres", default=os.getenv("DATABASE_URL"))
    parser.add_argument("--schema", default="public")
    parser.add_argument("--report", default="data/migration_reports/postgresql_preflight.json")
    args = parser.parse_args()

    if not args.postgres:
        raise SystemExit("Falta DATABASE_URL PostgreSQL.")
    url = normalize_database_url(args.postgres)
    if not url.startswith("postgresql+psycopg://"):
        raise SystemExit("DATABASE_URL no es PostgreSQL/psycopg.")

    report: dict[str, Any] = {
        "schema_version": 2,
        "generated_at": utc_now(),
        "target": masked_url(url),
        "schema": args.schema,
        "status": "RUNNING",
        "checks": [],
    }
    engine = create_engine(
        url,
        pool_pre_ping=True,
        future=True,
        connect_args={"connect_timeout": 10, "application_name": "primera-infancia-preflight"},
    )
    try:
        with engine.connect() as conn:
            version = str(conn.execute(text("SHOW server_version")).scalar_one())
            database = str(conn.execute(text("SELECT current_database()")).scalar_one())
            user = str(conn.execute(text("SELECT current_user")).scalar_one())
            timezone_value = str(conn.execute(text("SHOW TIME ZONE")).scalar_one())
            writable = bool(conn.execute(text("SELECT NOT pg_is_in_recovery()")).scalar_one())
            schema_exists = bool(conn.execute(
                text("SELECT EXISTS (SELECT 1 FROM information_schema.schemata WHERE schema_name=:schema)"),
                {"schema": args.schema},
            ).scalar_one())
            can_create_db = bool(conn.execute(text("SELECT has_database_privilege(current_user, current_database(), 'CREATE')")).scalar_one())
            can_use_schema = bool(conn.execute(
                text("SELECT CASE WHEN :schema='public' THEN has_schema_privilege(current_user, :schema, 'USAGE') ELSE "
                     "COALESCE(has_schema_privilege(current_user, :schema, 'USAGE'), false) END"),
                {"schema": args.schema},
            ).scalar_one()) if schema_exists else False

            report.update({
                "server_version": version,
                "database": database,
                "user": user,
                "timezone": timezone_value,
                "writable_primary": writable,
                "schema_exists": schema_exists,
            })
            add_check(report, "Conectividad", True, {"database": database, "user": user, "server_version": version})
            add_check(report, "Servidor primario escribible", writable)
            add_check(report, "Privilegio CREATE en base", can_create_db)
            if schema_exists:
                add_check(report, "Uso del esquema", can_use_schema, args.schema)
            else:
                add_check(report, "Esquema creable", can_create_db, f"{args.schema} se creará durante la migración")

            # La tabla temporal vive solo en esta sesión. Toda la prueba se revierte.
            try:
                conn.execute(text("CREATE TEMP TABLE pi_preflight_write_test (id INTEGER PRIMARY KEY, value TEXT NOT NULL) ON COMMIT DROP"))
                conn.execute(text("INSERT INTO pi_preflight_write_test(id,value) VALUES (1,'ok')"))
                value = conn.execute(text("SELECT value FROM pi_preflight_write_test WHERE id=1")).scalar_one()
                add_check(report, "Transacción temporal de escritura", value == "ok")
            finally:
                conn.rollback()

            # Validación de identificador para impedir inyección en el nombre de esquema.
            quote_identifier(args.schema)

        failures = [item for item in report["checks"] if item["status"] == "FAIL"]
        report["status"] = "OK" if not failures else "ERROR"
    except Exception as exc:  # noqa: BLE001
        report["status"] = "ERROR"
        report["error"] = f"{type(exc).__name__}: {exc}"
        add_check(report, "Excepción de preflight", False, report["error"])
    finally:
        engine.dispose()

    path = Path(args.report).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
