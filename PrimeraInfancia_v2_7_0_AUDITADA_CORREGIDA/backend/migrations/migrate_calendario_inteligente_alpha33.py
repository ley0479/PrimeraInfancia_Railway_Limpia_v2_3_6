"""Migración segura ALPHA33 Calendario Inteligente.

Crea tablas auxiliares para vista previa editable de cronogramas, confirmación,
archivos, entregas, alertas y auditoría. No borra ni reemplaza tablas existentes.
"""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path


def database_path() -> str:
    base_dir = Path(__file__).resolve().parents[1]
    return os.environ.get("DATABASE_PATH") or str(base_dir / "database.sqlite3")


def run(db_path: str | None = None) -> None:
    db = db_path or database_path()
    with sqlite3.connect(db) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS calendario_cronogramas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre_archivo TEXT,
                archivo_guardado TEXT,
                periodo TEXT,
                estado TEXT DEFAULT 'preview',
                total_detectadas INTEGER DEFAULT 0,
                total_validas INTEGER DEFAULT 0,
                total_invalidas INTEGER DEFAULT 0,
                requiere_revision INTEGER DEFAULT 1,
                preview_json TEXT,
                usuario_carga TEXT,
                fecha_carga TEXT,
                fecha_confirmacion TEXT,
                confirmado_por TEXT,
                fundacion_id INTEGER DEFAULT 1
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS calendario_actividades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cronograma_id INTEGER,
                entregable_id INTEGER,
                fecha TEXT,
                titulo TEXT,
                descripcion TEXT,
                responsable TEXT,
                coordinador TEXT,
                unidad TEXT,
                modulo TEXT,
                estado TEXT DEFAULT 'programado',
                prioridad TEXT DEFAULT 'Media',
                observacion TEXT,
                archivo_origen TEXT,
                usuario_carga TEXT,
                fecha_carga TEXT,
                fecha_entrega TEXT,
                entregado_por TEXT,
                soporte_path TEXT,
                created_at TEXT,
                updated_at TEXT,
                clave_unica TEXT
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_ci_actividades_fecha ON calendario_actividades(fecha)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_ci_actividades_cronograma ON calendario_actividades(cronograma_id)")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS calendario_entregas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                actividad_id INTEGER,
                entregable_id INTEGER,
                fecha_entrega TEXT,
                entregado_por TEXT,
                soporte_path TEXT,
                observaciones TEXT,
                created_at TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS calendario_alertas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entregable_id INTEGER,
                fecha TEXT,
                nivel TEXT,
                mensaje TEXT,
                estado TEXT DEFAULT 'activa',
                created_at TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS calendario_archivos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cronograma_id INTEGER,
                nombre_original TEXT,
                nombre_guardado TEXT,
                ruta TEXT,
                tipo TEXT,
                usuario_carga TEXT,
                fecha_carga TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS calendario_auditoria (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                accion TEXT,
                referencia_tipo TEXT,
                referencia_id INTEGER,
                detalle TEXT,
                usuario TEXT,
                created_at TEXT
            )
            """
        )
        conn.commit()


if __name__ == "__main__":
    run()
    print("Migración ALPHA33 Calendario Inteligente ejecutada correctamente.")
