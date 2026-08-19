"""Migra la unicidad de UDS desde ``nombre`` global a tenant + nombre.

Esta migracion se ejecuta exclusivamente durante predeploy, despues de crear el
esquema nucleo y antes de importar la aplicacion Flask. Es idempotente y no
modifica nombres ni elimina filas.
"""
from __future__ import annotations

import re
from typing import Any

from database import database, get_db_connection


_SAFE_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _quote_identifier(value: str) -> str:
    if not _SAFE_IDENTIFIER.fullmatch(str(value or "")):
        raise RuntimeError(f"Identificador PostgreSQL inseguro: {value!r}")
    return f'"{value}"'


def _postgres_unique_constraints(conn: Any) -> list[tuple[str, list[str]]]:
    rows = conn.execute(
        """
        SELECT tc.constraint_name,
               array_agg(kcu.column_name ORDER BY kcu.ordinal_position) AS columns
          FROM information_schema.table_constraints tc
          JOIN information_schema.key_column_usage kcu
            ON kcu.constraint_schema = tc.constraint_schema
           AND kcu.constraint_name = tc.constraint_name
           AND kcu.table_schema = tc.table_schema
           AND kcu.table_name = tc.table_name
         WHERE tc.table_schema = current_schema()
           AND tc.table_name = 'unidades'
           AND tc.constraint_type = 'UNIQUE'
         GROUP BY tc.constraint_name
        """
    ).fetchall()
    constraints: list[tuple[str, list[str]]] = []
    for row in rows:
        name = str(row["constraint_name"])
        columns = list(row["columns"] or [])
        constraints.append((name, [str(column) for column in columns]))
    return constraints


def migrate(_database_path: str | None = None) -> dict[str, Any]:
    """Garantiza ``UNIQUE(fundacion_id, nombre)`` en PostgreSQL.

    La restriccion historica ``UNIQUE(nombre)`` impedia que dos fundaciones
    usaran legítimamente el mismo nombre de UDS. Se retira solo esa restriccion
    exacta; la clave primaria y cualquier otra proteccion permanecen intactas.
    """
    if not database.is_postgresql:
        return {"engine": database.dialect_name, "status": "not-required"}

    dropped: list[str] = []
    with get_db_connection() as conn:
        columns = {
            str(row["column_name"])
            for row in conn.execute(
                """
                SELECT column_name
                  FROM information_schema.columns
                 WHERE table_schema = current_schema()
                   AND table_name = 'unidades'
                """
            ).fetchall()
        }
        if not columns:
            raise RuntimeError("La tabla unidades no existe durante el predeploy.")
        if "fundacion_id" not in columns:
            conn.execute("ALTER TABLE unidades ADD COLUMN fundacion_id INTEGER DEFAULT 1")
        conn.execute("UPDATE unidades SET fundacion_id=1 WHERE fundacion_id IS NULL")

        duplicates = conn.execute(
            """
            SELECT fundacion_id, nombre, COUNT(*) AS total
              FROM unidades
             GROUP BY fundacion_id, nombre
            HAVING COUNT(*) > 1
             LIMIT 10
            """
        ).fetchall()
        if duplicates:
            raise RuntimeError(
                "Existen UDS duplicadas dentro de una misma fundacion; "
                "no se modificaron datos: " + str([dict(row) for row in duplicates])
            )

        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_unidades_fundacion_nombre "
            "ON unidades(fundacion_id, nombre)"
        )
        for constraint_name, constraint_columns in _postgres_unique_constraints(conn):
            if constraint_columns == ["nombre"]:
                conn.execute(
                    "ALTER TABLE unidades DROP CONSTRAINT "
                    + _quote_identifier(constraint_name)
                )
                dropped.append(constraint_name)
        conn.commit()

    return {
        "engine": database.dialect_name,
        "status": "migrated",
        "dropped_legacy_constraints": dropped,
        "unique_key": ["fundacion_id", "nombre"],
    }
