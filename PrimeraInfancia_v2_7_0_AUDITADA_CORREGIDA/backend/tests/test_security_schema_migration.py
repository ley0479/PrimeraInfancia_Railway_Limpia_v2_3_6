#!/usr/bin/env python3
"""Regresión de migración Seguridad: base heredada, idempotencia y cero DDL en registro."""
from __future__ import annotations

import ast
import sqlite3
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / 'backend'
sys.path.insert(0, str(BACKEND))

from modules.seguridad.services import ensure_security_schema  # noqa: E402


def _legacy_database(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.execute('''
        CREATE TABLE usuarios_app (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            rol TEXT NOT NULL DEFAULT 'DOCENTE',
            unidades TEXT,
            activo INTEGER DEFAULT 1,
            fecha_creacion TEXT NOT NULL,
            fecha_ultima_conexion TEXT
        )
    ''')
    conn.execute('''
        CREATE TABLE fundaciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL UNIQUE,
            nit TEXT,
            representante TEXT,
            email TEXT,
            telefono TEXT,
            direccion TEXT,
            municipio TEXT,
            departamento TEXT,
            estado TEXT DEFAULT 'ACTIVA',
            plan TEXT DEFAULT 'PRUEBA',
            fecha_inicio TEXT,
            fecha_vencimiento TEXT,
            observaciones TEXT,
            fecha_creacion TEXT NOT NULL
        )
    ''')
    conn.execute("INSERT INTO fundaciones(nombre,estado,fecha_creacion) VALUES('Histórica','ACTIVA','2026-01-01')")
    conn.commit()
    conn.close()


def _registration_calls_schema(function_name: str, file_name: str) -> bool:
    source = (BACKEND / 'modules' / 'seguridad' / file_name).read_text(encoding='utf-8')
    tree = ast.parse(source)
    function = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == function_name)
    return any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == 'ensure_security_schema'
        for node in ast.walk(function)
    )


def main() -> None:
    with tempfile.TemporaryDirectory(prefix='pi-security-migration-') as tmp:
        path = Path(tmp) / 'legacy.sqlite3'
        _legacy_database(path)

        ensure_security_schema(str(path))
        conn = sqlite3.connect(path)
        before = conn.execute('SELECT id,nombre,estado FROM fundaciones ORDER BY id').fetchall()
        columns = {row[1] for row in conn.execute("PRAGMA table_info('fundaciones')").fetchall()}
        conn.close()
        assert before == [(1, 'Histórica', 'ACTIVA')]
        assert {'eliminado_en', 'eliminado_por', 'motivo_eliminacion'} <= columns

        statements: list[str] = []
        original_connect = sqlite3.connect

        def traced_connect(*args, **kwargs):
            connection = original_connect(*args, **kwargs)
            connection.set_trace_callback(statements.append)
            return connection

        import modules.seguridad.services as services
        original_proxy_connect = services.sqlite3.connect
        services.sqlite3.connect = traced_connect
        try:
            ensure_security_schema(str(path))
        finally:
            services.sqlite3.connect = original_proxy_connect

        ddl = [sql for sql in statements if sql.lstrip().upper().startswith(('ALTER ', 'CREATE ', 'DROP '))]
        assert ddl == [], f'La segunda migración ejecutó DDL innecesario: {ddl}'
        assert not _registration_calls_schema('register_seguridad', 'routes.py')
        assert not _registration_calls_schema('activate_security_guard', 'services.py')
        assert not _registration_calls_schema('bootstrap_initial_admin', 'services.py')

    print('SECURITY_SCHEMA_MIGRATION_PASS')


if __name__ == '__main__':
    main()
