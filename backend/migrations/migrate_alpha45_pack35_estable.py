"""Migración ALPHA45 Pack35 estable evolucionado.

Crea tablas de Configuración Institucional y Manual Operativo de forma idempotente.
No toca el motor de procesamiento, CoreCursor, Base Maestra ni formatos oficiales.
"""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parents[1]


def conectar(database_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(database_path)
    try:
        conn.execute('PRAGMA foreign_keys=ON')
        conn.execute('PRAGMA busy_timeout=30000')
    except Exception:
        pass
    return conn


def migrar(database_path: str) -> None:
    conn = conectar(database_path)
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS configuracion_institucional (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            corporacion_id INTEGER DEFAULT 1,
            fundacion_id INTEGER DEFAULT 1,
            nombre_plataforma TEXT,
            nombre_corporacion TEXT,
            sigla TEXT,
            nit TEXT,
            representante_legal TEXT,
            direccion TEXT,
            telefono TEXT,
            correo TEXT,
            logo_principal_path TEXT,
            logo_reportes_path TEXT,
            logo_formatos_path TEXT,
            foto_admin_path TEXT,
            favicon_path TEXT,
            nombre_admin TEXT,
            cargo_admin TEXT,
            color_primario TEXT,
            color_secundario TEXT,
            firma_path TEXT,
            activo INTEGER DEFAULT 1,
            creado_por TEXT,
            actualizado_por TEXT,
            created_at TEXT,
            updated_at TEXT
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS manuales_operativos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            corporacion_id INTEGER DEFAULT 1,
            fundacion_id INTEGER DEFAULT 1,
            codigo TEXT,
            nombre TEXT,
            version TEXT,
            fecha_documento TEXT,
            estado TEXT DEFAULT 'borrador',
            archivo_path TEXT,
            total_paginas INTEGER,
            observacion TEXT,
            cargado_por TEXT,
            created_at TEXT,
            updated_at TEXT
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS manuales_operativos_secciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            manual_id INTEGER,
            titulo TEXT,
            numero TEXT,
            pagina_inicio INTEGER,
            pagina_fin INTEGER,
            orden INTEGER,
            resumen TEXT,
            created_at TEXT,
            FOREIGN KEY (manual_id) REFERENCES manuales_operativos(id)
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS auditoria_institucional_alpha41 (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            accion TEXT NOT NULL,
            entidad TEXT,
            entidad_id INTEGER,
            detalle_json TEXT,
            usuario TEXT,
            fundacion_id INTEGER DEFAULT 1,
            fecha TEXT NOT NULL
        )
    ''')
    existentes = {row[1] for row in cur.execute('PRAGMA table_info(configuracion_institucional)').fetchall()}
    for columna, tipo in {'nombre_plataforma': 'TEXT', 'favicon_path': 'TEXT'}.items():
        if columna not in existentes:
            cur.execute(f'ALTER TABLE configuracion_institucional ADD COLUMN {columna} {tipo}')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_config_inst_fund ON configuracion_institucional(fundacion_id, activo)')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_manuales_fund_estado ON manuales_operativos(fundacion_id, estado)')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_manuales_secciones_manual ON manuales_operativos_secciones(manual_id, orden)')
    row = cur.execute('SELECT id FROM configuracion_institucional WHERE fundacion_id=1 AND COALESCE(activo,1)=1 LIMIT 1').fetchone()
    if not row:
        now = datetime.now().isoformat(timespec='seconds')
        cur.execute('''
            INSERT INTO configuracion_institucional
            (corporacion_id, fundacion_id, nombre_plataforma, nombre_corporacion, sigla, nombre_admin, cargo_admin, color_primario, color_secundario, activo, created_at, updated_at)
            VALUES (1, 1, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
        ''', ('Primera Infancia', 'Organización de prueba', 'ORGDEMO', 'Administrador General', 'Administrador Plataforma', '#2563eb', '#06b6d4', now, now))
    conn.commit()
    conn.close()


def main() -> None:
    database_path = os.environ.get('DATABASE_PATH') or str(BASE_DIR / 'database.sqlite3')
    migrar(database_path)
    print(f'ALPHA45 institucional schema OK: {database_path}')


if __name__ == '__main__':
    main()
