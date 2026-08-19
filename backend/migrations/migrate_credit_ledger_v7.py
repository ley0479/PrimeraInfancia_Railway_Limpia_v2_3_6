"""Libro mayor de créditos v1: incremental, idempotente y no destructivo."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import inspect

from database import database, get_db_connection


CREDITS_SCHEMA_VERSION = 1


def _columns(table: str) -> set[str]:
    if database.engine is None or not inspect(database.engine).has_table(table):
        return set()
    return {str(column["name"]) for column in inspect(database.engine).get_columns(table)}


def migrate(_database_path: str | None = None) -> dict[str, Any]:
    columns = _columns("movimientos_credito")
    if not columns:
        raise RuntimeError("La tabla movimientos_credito no existe durante predeploy.")

    added: list[str] = []
    opening_movements = 0
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    definitions = {
        "idempotency_key": "TEXT",
        "estado": "TEXT NOT NULL DEFAULT 'APLICADO'",
        "metadata_json": "TEXT",
        "fecha_aplicacion": "TEXT",
    }
    with get_db_connection() as conn:
        for name, definition in definitions.items():
            if name not in columns:
                conn.execute(f"ALTER TABLE movimientos_credito ADD COLUMN {name} {definition}")
                added.append(name)

        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_creditos_mov_fundacion_idempotency "
            "ON movimientos_credito(fundacion_id, idempotency_key) "
            "WHERE idempotency_key IS NOT NULL"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_creditos_mov_fundacion_fecha "
            "ON movimientos_credito(fundacion_id, fecha_movimiento)"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS creditos_schema_version ("
            "componente TEXT PRIMARY KEY, version INTEGER NOT NULL, updated_at TEXT NOT NULL)"
        )

        subscriptions = conn.execute(
            "SELECT id, fundacion_id, creditos_disponibles FROM suscripciones_fundacion ORDER BY fundacion_id"
        ).fetchall()
        for subscription in subscriptions:
            fid = int(subscription["fundacion_id"])
            existing = conn.execute(
                "SELECT id FROM movimientos_credito WHERE fundacion_id=? LIMIT 1", (fid,)
            ).fetchone()
            if existing:
                continue
            balance = int(subscription["creditos_disponibles"] or 0)
            key = f"migration-opening-{fid}"
            conn.execute(
                """INSERT INTO movimientos_credito
                   (fundacion_id,suscripcion_id,tipo,accion,creditos,saldo_anterior,saldo_nuevo,
                    referencia_tipo,referencia_id,descripcion,fecha_movimiento,idempotency_key,
                    estado,metadata_json,fecha_aplicacion)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT DO NOTHING""",
                (fid, subscription["id"], "ASIGNACION_INICIAL", "migracion_saldo_existente",
                 balance, 0, balance, "MIGRACION", str(subscription["id"]),
                 "Movimiento de apertura; conserva el saldo existente sin modificarlo.", now,
                 key, "APLICADO", '{"origen":"MIGRACION_SALDO_EXISTENTE"}', now),
            )
            opening_movements += 1

        conn.execute(
            """INSERT INTO creditos_schema_version(componente,version,updated_at)
               VALUES ('credit_ledger',?,?)
               ON CONFLICT(componente) DO UPDATE SET version=excluded.version, updated_at=excluded.updated_at""",
            (CREDITS_SCHEMA_VERSION, now),
        )
        conn.commit()

    return {
        "status": "PASS",
        "credits_schema_version": CREDITS_SCHEMA_VERSION,
        "columns_added": added,
        "opening_movements": opening_movements,
    }


if __name__ == "__main__":
    from config import get_config

    print(migrate(str(get_config().DATABASE_PATH)))
