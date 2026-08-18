#!/usr/bin/env python3
"""Regresión focalizada del bloqueo de despliegue PostgreSQL/Railway.

No requiere un servidor PostgreSQL: verifica que PRAGMA table_info consulte una
sola tabla, que el startup separe migración/runtime y que los módulos críticos
no puedan quedar silenciosamente sin registrar.
"""
from __future__ import annotations

import os
import sqlite3 as native_sqlite3
import sys
import tempfile
from pathlib import Path

from flask import Flask

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from database import configure_database, database  # noqa: E402
from modules.dbapi_compat import CompatConnection  # noqa: E402
from modules.calendario_inteligente.repository import CalendarioInteligenteRepository  # noqa: E402


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

    predeploy = (ROOT / "predeploy_hosting.sh").read_text(encoding="utf-8")
    start = (ROOT / "start_hosting.sh").read_text(encoding="utf-8")
    migration_pos = predeploy.find("APP_SCHEMA_MIGRATION_MODE=1")
    init_pos = predeploy.find("python backend/init_hosting.py")
    runtime_pos = start.find("APP_SCHEMA_MIGRATION_MODE=0")
    gunicorn_pos = start.find("gunicorn")
    require(-1 not in {migration_pos, init_pos, runtime_pos, gunicorn_pos}, "Faltan etapas de pre-deploy/runtime")
    require(migration_pos < init_pos, "Orden de migración en pre-deploy inválido")
    require(runtime_pos < gunicorn_pos, "Orden runtime/Gunicorn inválido")
    require("python backend/init_hosting.py" not in start, "Runtime todavía ejecuta migraciones")

    init_source = (BACKEND / "init_hosting.py").read_text(encoding="utf-8")
    require("required_blueprints" in init_source and "missing_blueprints" in init_source, "Falta gate de módulos críticos")
    require("Módulos críticos no registrados" in init_source, "El startup no bloquea despliegues parciales")
    require(
        "state = 'idle in transaction'" in init_source and "pg_terminate_backend" in init_source,
        "El startup no limpia transacciones huérfanas de la propia aplicación",
    )

    security_source = (BACKEND / "modules" / "seguridad" / "services.py").read_text(encoding="utf-8")
    require(
        'SELECT 1 FROM fundaciones WHERE id = 1' in security_source,
        "La fundación semilla no se consulta antes de intentar escribir",
    )
    mature_guard = security_source.find("if not security_tables_complete:", security_source.find("no consultar ni escribir"))
    foundation_read = security_source.find('SELECT 1 FROM fundaciones WHERE id = 1', mature_guard)
    require(
        mature_guard >= 0 and foundation_read > mature_guard,
        "Una migración madura todavía puede consultar datos bloqueados de fundaciones",
    )
    require(
        "SELECT 1, 'Entorno de pruebas'" not in security_source,
        "Persistió INSERT...SELECT que toma RowExclusiveLock aunque la semilla exista",
    )
    ddl_commit = security_source.find("libera locks DDL")
    seed_start = security_source.find("now = now_iso()", ddl_commit)
    require(ddl_commit >= 0 and seed_start > ddl_commit, "La siembra no libera locks DDL antes de empezar")

    calendar_source = (BACKEND / "modules" / "calendario_inteligente" / "repository.py").read_text(encoding="utf-8")
    add_foundation = calendar_source.find('"fundacion_id": "INTEGER DEFAULT 1"')
    calendar_index = calendar_source.find("idx_calendario_entregables_clave")
    require(
        add_foundation >= 0 and calendar_index > add_foundation,
        "Calendario crea índices multi-tenant antes de migrar fundacion_id",
    )
    alert_columns = calendar_source.find("alert_columns =")
    alert_index = calendar_source.find("uq_cal_alerta_idempotente")
    cronogramas_repair = calendar_source.find(
        '"calendario_cronogramas", "calendario_actividades"'
    )
    require(
        alert_columns >= 0 and alert_index > alert_columns,
        "Alertas crea el índice tenant antes de reparar fundacion_id",
    )
    require(
        cronogramas_repair >= 0,
        "Cronogramas no participa en la reparación tenant histórica",
    )

    # Caracterización de una base anterior a multi-tenant: las tablas ya
    # existen sin fundacion_id y la migración debe completar columnas antes de
    # crear cualquiera de sus índices.
    with tempfile.TemporaryDirectory(prefix="pi_calendar_legacy_") as temp_dir:
        legacy_db = Path(temp_dir) / "legacy.sqlite3"
        raw = native_sqlite3.connect(legacy_db)
        try:
            raw.executescript(
                """
                CREATE TABLE calendario_entregables (id INTEGER PRIMARY KEY, titulo TEXT, fecha_limite TEXT, clave_unica TEXT, coordinador TEXT, unidad TEXT);
                CREATE TABLE calendario_cronogramas (id INTEGER PRIMARY KEY, nombre_archivo TEXT);
                CREATE TABLE calendario_alertas (id INTEGER PRIMARY KEY, entregable_id INTEGER);
                CREATE TABLE calendario_obligaciones (id INTEGER PRIMARY KEY, componente TEXT, activa INTEGER);
                CREATE TABLE calendario_requisitos (id INTEGER PRIMARY KEY, obligacion_id INTEGER, orden INTEGER);
                CREATE TABLE calendario_asignaciones (id INTEGER PRIMARY KEY, periodo TEXT, unidad TEXT, responsable_rol TEXT, estado TEXT);
                CREATE TABLE calendario_evidencias (id INTEGER PRIMARY KEY, entidad_tipo TEXT, entidad_id INTEGER, requisito_id INTEGER, fecha_carga TEXT);
                """
            )
            raw.commit()
        finally:
            raw.close()
        calendar_app = Flask("calendar_legacy_migration")
        calendar_app.config.update(
            DATABASE_URL=f"sqlite:///{legacy_db.as_posix()}",
            DATABASE_PATH=str(legacy_db),
            SQLALCHEMY_ENGINE_OPTIONS={},
        )
        configure_database(calendar_app)
        CalendarioInteligenteRepository(str(legacy_db), temp_dir).init_schema(force=True)
        check = native_sqlite3.connect(legacy_db)
        try:
            for table in (
                "calendario_entregables", "calendario_cronogramas", "calendario_alertas",
                "calendario_obligaciones", "calendario_requisitos", "calendario_asignaciones",
                "calendario_evidencias",
            ):
                columns = {row[1] for row in check.execute(f'PRAGMA table_info("{table}")')}
                require("fundacion_id" in columns, f"{table} no migró fundacion_id")
        finally:
            check.close()

    app_source = (BACKEND / "app.py").read_text(encoding="utf-8")
    require("/api/system/version" in app_source, "Falta endpoint de huella exacta de versión")
    require("RAILWAY_GIT_COMMIT_SHA" in app_source, "Falta SHA del commit en diagnóstico")
    print("PASS test_postgres_startup_regression_v2_7_0")


if __name__ == "__main__":
    run()
