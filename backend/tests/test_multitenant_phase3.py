#!/usr/bin/env python3
"""Pruebas puras del aislamiento multi-fundación v2.4.0.

No usa Flask ni datos reales. Crea una base temporal con dos fundaciones y
comprueba migración, SQL fail-closed, SQLAlchemy Core y rutas físicas.
"""
from __future__ import annotations

import os
import sqlite3
import tempfile
from pathlib import Path

os.environ["SINGLE_TENANT_MODE"] = "false"
os.environ["ALLOW_EXPERIMENTAL_MULTI_TENANT"] = "true"
os.environ["MULTI_TENANT_STRICT"] = "true"
os.environ["TENANT_STORAGE_ISOLATION"] = "true"
os.environ["MULTI_TENANT_SCHEMA_VERSION"] = "3"

from sqlalchemy import create_engine

from database import database
from migrations.migrate_multitenant_phase3 import migrate
from modules.seguridad.tenant_context import tenant_context, tenant_path
from modules.seguridad.tenant_sql_guard import (
    TenantIsolationError,
    install_sqlite_tenant_guard,
    uninstall_sqlite_tenant_guard,
)
from modules.sqlalchemy_compat import CoreCompatRepository, _CORE_TENANT_SCHEMA_CACHE
from services.uds_catalog import canonical_units, ensure_catalog_units_sqlite


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def create_legacy_database(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE fundaciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT UNIQUE NOT NULL,
            estado TEXT DEFAULT 'ACTIVA'
        );
        INSERT INTO fundaciones(id,nombre,estado) VALUES
            (1,'Fundación A','ACTIVA'), (2,'Fundación B','ACTIVA');

        CREATE TABLE beneficiarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            documento TEXT NOT NULL,
            unidad TEXT NOT NULL,
            nombre TEXT,
            UNIQUE(documento, unidad)
        );
        INSERT INTO beneficiarios(documento,unidad,nombre)
        VALUES ('LEGACY-1','UNIDAD LEGACY','Persona ficticia');

        CREATE TABLE gestantes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            documento TEXT UNIQUE NOT NULL,
            nombre TEXT
        );
        CREATE TABLE docentes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            documento TEXT UNIQUE NOT NULL,
            nombre TEXT
        );
        CREATE TABLE coordinadores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            documento TEXT UNIQUE NOT NULL,
            nombre TEXT
        );
        CREATE TABLE unidades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT UNIQUE NOT NULL,
            total_usuarios INTEGER DEFAULT 0,
            alerta_cobertura INTEGER DEFAULT 1,
            ultima_actualizacion TEXT
        );
        CREATE TABLE pc_ticket_comentarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id INTEGER,
            comentario TEXT
        );
        CREATE TABLE evaluaciones_cumplimiento (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            indicador TEXT,
            resultado TEXT
        );
        CREATE TABLE tm_temas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL
        );
        CREATE TABLE reglas_cumplimiento (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo TEXT NOT NULL,
            descripcion TEXT
        );
        INSERT INTO reglas_cumplimiento(codigo,descripcion) VALUES ('REG-DEMO','Regla histórica');
        CREATE TABLE plantillas_oficiales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tipo_formato TEXT NOT NULL,
            nombre TEXT NOT NULL
        );
        CREATE TABLE plantillas_oficiales_versiones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plantilla_oficial_id INTEGER,
            tipo_formato TEXT NOT NULL,
            version TEXT NOT NULL,
            archivo_path TEXT NOT NULL
        );
        CREATE TABLE estandares_icbf (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo TEXT UNIQUE NOT NULL,
            descripcion TEXT
        );
        """
    )
    conn.commit()
    conn.close()


def test_migration_and_uniques(db_path: Path) -> None:
    report = migrate(db_path)
    assert_true(report["schema_version"] == 3, "versión de esquema incorrecta")
    assert_true(report.get("integrity") == "ok", "integridad SQLite falló")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    for table in ("beneficiarios", "unidades", "pc_ticket_comentarios", "evaluaciones_cumplimiento", "reglas_cumplimiento", "plantillas_oficiales", "plantillas_oficiales_versiones"):
        cols = {r[1] for r in conn.execute(f'PRAGMA table_info("{table}")')}
        assert_true("fundacion_id" in cols, f"{table} no recibió fundacion_id")
    legacy = conn.execute("SELECT fundacion_id FROM beneficiarios WHERE documento='LEGACY-1'").fetchone()
    assert_true(int(legacy[0]) == 1, "fila histórica no fue asignada a fundación 1")

    # El mismo documento/unidad puede existir en fundaciones distintas.
    conn.execute(
        "INSERT INTO beneficiarios(documento,unidad,nombre,fundacion_id) VALUES (?,?,?,?)",
        ("LEGACY-1", "UNIDAD LEGACY", "Otro ficticio", 2),
    )
    try:
        conn.execute(
            "INSERT INTO beneficiarios(documento,unidad,nombre,fundacion_id) VALUES (?,?,?,?)",
            ("LEGACY-1", "UNIDAD LEGACY", "Duplicado", 1),
        )
        raise AssertionError("duplicado dentro del mismo tenant fue permitido")
    except sqlite3.IntegrityError:
        pass
    conn.commit()
    assert_true(conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok", "integrity_check final")
    conn.close()


def test_core_guard(db_path: Path) -> None:
    database.dispose()
    database.database_path = str(db_path)
    database.database_url = f"sqlite:///{db_path.as_posix()}"
    database.engine = create_engine(database.database_url, future=True)
    _CORE_TENANT_SCHEMA_CACHE.clear()
    repo = CoreCompatRepository()

    with tenant_context(1, role="GERENTE", source="test-core"):
        rows = repo.fetch_all("SELECT documento,fundacion_id FROM beneficiarios ORDER BY id")
        assert_true(rows and {int(r["fundacion_id"]) for r in rows} == {1}, "Core SELECT filtró mal")
        repo.execute(
            "INSERT INTO beneficiarios(documento,unidad,nombre) VALUES (?,?,?)",
            ("CORE-1", "UNIDAD CORE", "Ficticio"),
        )
        inserted = repo.fetch_one("SELECT fundacion_id FROM beneficiarios WHERE documento=?", ("CORE-1",))
        assert_true(int(inserted["fundacion_id"]) == 1, "Core INSERT no inyectó tenant")
        try:
            repo.execute(
                "INSERT INTO beneficiarios(documento,unidad,nombre,fundacion_id) VALUES (?,?,?,?)",
                ("CORE-X", "UNIDAD CORE", "Cruce", 2),
            )
            raise AssertionError("Core permitió escritura cruzada")
        except TenantIsolationError:
            pass
        try:
            repo.fetch_all(
                "SELECT b.id,u.id FROM beneficiarios b JOIN unidades u ON u.nombre=b.unidad"
            )
            raise AssertionError("Core permitió JOIN sin alcance tenant")
        except TenantIsolationError:
            pass
        try:
            repo.fetch_all(
                "SELECT b.id,u.id FROM beneficiarios b "
                "JOIN unidades u ON u.nombre=b.unidad AND u.fundacion_id=? "
                "WHERE b.fundacion_id=?",
                (2, 2),
            )
            raise AssertionError("Core permitió parámetros explícitos de otro tenant")
        except TenantIsolationError:
            pass
        repo.execute("UPDATE beneficiarios SET nombre=?", ("Actualizado T1",))
    database.dispose()
    database.engine = None
    database.database_url = None
    database.database_path = None


def test_sqlite_guard_and_storage(db_path: Path, data_dir: Path) -> None:
    install_sqlite_tenant_guard()
    try:
        with tenant_context(1, role="GERENTE", source="test-sqlite"):
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT documento,fundacion_id FROM beneficiarios ORDER BY id").fetchall()
            assert_true(rows and {int(r["fundacion_id"]) for r in rows} == {1}, "SQLite SELECT filtró mal")

            conn.execute(
                "INSERT INTO beneficiarios(documento,unidad,nombre) VALUES (?,?,?)",
                ("AUTO-1", "UNIDAD AUTO", "Ficticio"),
            )
            conn.commit()
            row = conn.execute("SELECT fundacion_id FROM beneficiarios WHERE documento=?", ("AUTO-1",)).fetchone()
            assert_true(int(row[0]) == 1, "SQLite INSERT no inyectó tenant")

            try:
                conn.execute(
                    "INSERT INTO beneficiarios(documento,unidad,nombre,fundacion_id) VALUES (?,?,?,?)",
                    ("CROSS-1", "UNIDAD AUTO", "Cruce", 2),
                )
                raise AssertionError("SQLite permitió escritura cruzada")
            except TenantIsolationError:
                pass

            try:
                conn.execute("SELECT b.id,u.id FROM beneficiarios b JOIN unidades u ON u.nombre=b.unidad")
                raise AssertionError("SQLite permitió JOIN sin alcance tenant")
            except TenantIsolationError:
                pass

            conn.execute(
                "SELECT b.id,u.id FROM beneficiarios b "
                "JOIN unidades u ON u.nombre=b.unidad AND u.fundacion_id=? "
                "WHERE b.fundacion_id=?",
                (1, 1),
            ).fetchall()
            try:
                conn.execute(
                    "SELECT b.id,u.id FROM beneficiarios b "
                    "JOIN unidades u ON u.nombre=b.unidad AND u.fundacion_id=? "
                    "WHERE b.fundacion_id=?",
                    (2, 2),
                ).fetchall()
                raise AssertionError("SQLite permitió parámetros explícitos de otro tenant")
            except TenantIsolationError:
                pass
            conn.execute("UPDATE beneficiarios SET nombre=?", ("SQLite T1",))
            conn.execute(
                "INSERT INTO beneficiarios(documento,unidad,nombre) VALUES (?,?,?)",
                ("DELETE-T1", "UNIDAD DELETE", "Eliminar solo T1"),
            )
            conn.execute("DELETE FROM beneficiarios WHERE documento=?", ("DELETE-T1",))
            conn.commit()
            conn.executescript("CREATE TABLE IF NOT EXISTS ddl_prueba(id INTEGER PRIMARY KEY);")
            try:
                conn.executescript("INSERT INTO beneficiarios(documento,unidad,nombre) VALUES ('DML','X','Y');")
                raise AssertionError("executescript DML no fue bloqueado")
            except TenantIsolationError:
                pass
            conn.close()

            path_a = Path(os.fspath(tenant_path(data_dir / "uploads")))
            assert_true("tenants/1/uploads" in path_a.as_posix(), "ruta tenant 1 incorrecta")

        with tenant_context(2, role="GERENTE", source="test-sqlite"):
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT documento,fundacion_id,nombre FROM beneficiarios ORDER BY id").fetchall()
            assert_true(rows and {int(r["fundacion_id"]) for r in rows} == {2}, "SQLite tenant 2 filtró mal")
            assert_true(all(r["nombre"] != "SQLite T1" for r in rows), "UPDATE tenant 1 afectó tenant 2")
            assert_true(all(r["nombre"] != "Actualizado T1" for r in rows), "Core UPDATE tenant 1 afectó tenant 2")
            path_b = Path(os.fspath(tenant_path(data_dir / "uploads")))
            assert_true("tenants/2/uploads" in path_b.as_posix(), "ruta tenant 2 incorrecta")
            conn.close()
        assert_true(path_a != path_b, "dos tenants resolvieron la misma carpeta")

        # Cada tenant recibe el catálogo completo aunque los nombres coincidan.
        with tenant_context(1, role="SYSTEM", source="seed"):
            seed_a = ensure_catalog_units_sqlite(db_path, fundacion_id=1)
        with tenant_context(2, role="SYSTEM", source="seed"):
            seed_b = ensure_catalog_units_sqlite(db_path, fundacion_id=2)
        assert_true(seed_a["catalog_total"] == len(canonical_units()), "catálogo tenant 1 incompleto")
        assert_true(seed_b["catalog_total"] == len(canonical_units()), "catálogo tenant 2 incompleto")

        # Reglas y plantillas versionadas también quedan aisladas por tenant.
        with tenant_context(1, role="GERENTE", source="test-operational-catalog"):
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            conn.execute("INSERT INTO reglas_cumplimiento(codigo,descripcion) VALUES (?,?)", ("REG-T1", "Tenant 1"))
            conn.execute("INSERT INTO plantillas_oficiales(tipo_formato,nombre) VALUES (?,?)", ("RPP", "RPP T1"))
            conn.commit()
            assert_true({int(r['fundacion_id']) for r in conn.execute("SELECT * FROM reglas_cumplimiento")} == {1}, "reglas tenant 1 sin alcance")
            conn.close()
        with tenant_context(2, role="GERENTE", source="test-operational-catalog"):
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            conn.execute("INSERT INTO reglas_cumplimiento(codigo,descripcion) VALUES (?,?)", ("REG-T2", "Tenant 2"))
            conn.execute("INSERT INTO plantillas_oficiales(tipo_formato,nombre) VALUES (?,?)", ("RPP", "RPP T2"))
            conn.commit()
            assert_true({int(r['fundacion_id']) for r in conn.execute("SELECT * FROM reglas_cumplimiento")} == {2}, "reglas tenant 2 filtradas incorrectamente")
            assert_true({int(r['fundacion_id']) for r in conn.execute("SELECT * FROM plantillas_oficiales")} == {2}, "plantillas oficiales tenant 2 filtradas incorrectamente")
            conn.close()

        # Catálogo compartido: una fila global intencional sigue permitida.
        with tenant_context(1, role="GERENTE", source="test-shared"):
            conn = sqlite3.connect(db_path)
            conn.execute("INSERT INTO tm_temas(nombre) VALUES (?)", ("Tema global ficticio",))
            conn.commit()
            conn.close()
    finally:
        uninstall_sqlite_tenant_guard()


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="pi-mt3-") as tmp:
        root = Path(tmp)
        db_path = root / "database.sqlite3"
        create_legacy_database(db_path)
        test_migration_and_uniques(db_path)
        test_core_guard(db_path)
        test_sqlite_guard_and_storage(db_path, root / "data")
    print("PASS test_multitenant_phase3")


if __name__ == "__main__":
    main()
