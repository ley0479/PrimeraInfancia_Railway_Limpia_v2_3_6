"""Esquema global de identidad v1: incremental, idempotente y no destructivo."""
from __future__ import annotations

from datetime import datetime, timezone

from modules.dbapi_compat import sqlite3


IDENTITY_SCHEMA_VERSION = 1


def migrate(database_path: str) -> dict:
    conn = sqlite3.connect(database_path)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS configuracion_global_plataforma (
                id INTEGER PRIMARY KEY,
                nombre_plataforma TEXT,
                sigla_plataforma TEXT,
                logo_global_key TEXT,
                logo_reportes_global_key TEXT,
                logo_formatos_global_key TEXT,
                favicon_global_key TEXT,
                nombre_administrador_general TEXT,
                cargo_administrador_general TEXT,
                foto_administrador_general_key TEXT,
                color_primario_global TEXT,
                color_secundario_global TEXT,
                identity_version INTEGER NOT NULL DEFAULT 1,
                activo INTEGER NOT NULL DEFAULT 1,
                updated_by TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                CHECK (id = 1)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS identidad_global_archivos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tipo TEXT NOT NULL,
                storage_key TEXT NOT NULL UNIQUE,
                nombre_original TEXT,
                mime_type TEXT NOT NULL,
                tamano_bytes INTEGER NOT NULL,
                sha256 TEXT NOT NULL,
                version INTEGER NOT NULL,
                activo INTEGER NOT NULL DEFAULT 1,
                cargado_por TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS identidad_schema_version (
                componente TEXT PRIMARY KEY,
                version INTEGER NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        conn.execute(
            """INSERT INTO configuracion_global_plataforma
               (id, nombre_plataforma, sigla_plataforma,
                nombre_administrador_general, cargo_administrador_general,
                color_primario_global, color_secundario_global,
                identity_version, activo, created_at, updated_at)
               VALUES (1, ?, ?, ?, ?, ?, ?, 1, 1, ?, ?)
               ON CONFLICT(id) DO NOTHING""",
            (
                "Primera Infancia", "PI", "Administrador General",
                "Administrador Plataforma", "#2563eb", "#06b6d4", now, now,
            ),
        )
        conn.execute(
            """INSERT INTO identidad_schema_version (componente, version, updated_at)
               VALUES ('identidad_global', ?, ?)
               ON CONFLICT(componente) DO UPDATE SET version=excluded.version, updated_at=excluded.updated_at""",
            (IDENTITY_SCHEMA_VERSION, now),
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_identidad_global_tipo_activo ON identidad_global_archivos(tipo, activo, version)")
        conn.commit()
        return {"status": "PASS", "identity_schema_version": IDENTITY_SCHEMA_VERSION}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    from config import get_config
    print(migrate(str(get_config().DATABASE_PATH)))
