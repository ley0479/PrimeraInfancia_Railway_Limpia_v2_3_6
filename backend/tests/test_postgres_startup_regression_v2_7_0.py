#!/usr/bin/env python3
"""Regresión focalizada del bloqueo de despliegue PostgreSQL/Railway.

No requiere un servidor PostgreSQL: verifica que PRAGMA table_info consulte una
sola tabla, que el startup separe migración/runtime y que los módulos críticos
no puedan quedar silenciosamente sin registrar.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from database import database  # noqa: E402
from modules.dbapi_compat import CompatConnection  # noqa: E402


def require(value, message: str) -> None:
    if not value:
        raise AssertionError(message)


class FakeResult:
    def __iter__(self):
        return iter([
            ("id", "bigint", "NO", None, 1, True),
            ("titulo", "text", "YES", None, 2, False),
        ])


class FakeConnection:
    def __init__(self, calls):
        self.calls = calls

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, statement, params=None):
        self.calls.append((str(statement), dict(params or {})))
        return FakeResult()

    def close(self):
        return None


class FakeEngine:
    def __init__(self):
        self.calls = []

    def connect(self):
        return FakeConnection(self.calls)


def run() -> None:
    source = (BACKEND / "modules" / "dbapi_compat.py").read_text(encoding="utf-8")
    require("SELECT table_name, column_name" not in source, "Persistió la introspección global de information_schema.columns")
    require("AND c.table_name = :table_name" in source, "Falta filtro por tabla en PRAGMA table_info")
    require(source.count("self._owner.rollback()") >= 6, "Faltan rollbacks explícitos ante errores PostgreSQL")

    original_engine = database.engine
    fake = FakeEngine()
    database.engine = fake
    old_skip = os.environ.get("SKIP_RUNTIME_SCHEMA_DDL")
    os.environ["SKIP_RUNTIME_SCHEMA_DDL"] = "1"
    try:
        conn = CompatConnection()
        rows = conn.execute('PRAGMA table_info("gp_planeaciones")').fetchall()
        conn.close()
    finally:
        database.engine = original_engine
        if old_skip is None:
            os.environ.pop("SKIP_RUNTIME_SCHEMA_DDL", None)
        else:
            os.environ["SKIP_RUNTIME_SCHEMA_DDL"] = old_skip

    require(len(rows) == 2, "La introspección focalizada no devolvió columnas")
    require(fake.calls, "No se ejecutó la introspección focalizada")
    sql, params = fake.calls[-1]
    require("c.table_name = :table_name" in sql, "La consulta ejecutada no filtra por tabla")
    require(params == {"table_name": "gp_planeaciones"}, f"Parámetros inesperados: {params}")
    require("ORDER BY table_name" not in sql, "La consulta todavía ordena/carga todo el esquema")

    start = (ROOT / "start_hosting.sh").read_text(encoding="utf-8")
    migration_pos = start.find("APP_SCHEMA_MIGRATION_MODE=1")
    init_pos = start.find("python backend/init_hosting.py")
    runtime_pos = start.find("APP_SCHEMA_MIGRATION_MODE=0")
    gunicorn_pos = start.find("gunicorn")
    require(-1 not in {migration_pos, init_pos, runtime_pos, gunicorn_pos}, "Faltan etapas del startup")
    require(migration_pos < init_pos < runtime_pos < gunicorn_pos, "Orden migración/runtime/Gunicorn inválido")

    init_source = (BACKEND / "init_hosting.py").read_text(encoding="utf-8")
    require("required_blueprints" in init_source and "missing_blueprints" in init_source, "Falta gate de módulos críticos")
    require("Módulos críticos no registrados" in init_source, "El startup no bloquea despliegues parciales")

    security_source = (BACKEND / "modules" / "seguridad" / "services.py").read_text(encoding="utf-8")
    require(
        'SELECT 1 FROM fundaciones WHERE id = 1' in security_source,
        "La fundación semilla no se consulta antes de intentar escribir",
    )
    require(
        "SELECT 1, 'Entorno de pruebas'" not in security_source,
        "Persistió INSERT...SELECT que toma RowExclusiveLock aunque la semilla exista",
    )
    ddl_commit = security_source.find("libera locks DDL")
    seed_start = security_source.find("now = now_iso()", ddl_commit)
    require(ddl_commit >= 0 and seed_start > ddl_commit, "La siembra no libera locks DDL antes de empezar")

    app_source = (BACKEND / "app.py").read_text(encoding="utf-8")
    require("/api/system/version" in app_source, "Falta endpoint de huella exacta de versión")
    require("RAILWAY_GIT_COMMIT_SHA" in app_source, "Falta SHA del commit en diagnóstico")
    print("PASS test_postgres_startup_regression_v2_7_0")


if __name__ == "__main__":
    run()
