#!/usr/bin/env python3
from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

from sqlalchemy import create_engine, text

from tools.migrate_sqlite_to_postgresql import (
    masked_url,
    prepare_metadata,
    sha256_file,
    sqlite_consistent_backup,
    table_fingerprint,
)

ROOT = Path(__file__).resolve().parents[2]


def require(ok, msg):
    if not ok:
        raise AssertionError(msg)


with tempfile.TemporaryDirectory(prefix="pi-migration-test-") as tmp:
    source = Path(tmp) / "source.sqlite3"
    snapshot = Path(tmp) / "snapshot.sqlite3"
    engine = create_engine(f"sqlite:///{source.as_posix()}", future=True)
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE fundaciones (id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT NOT NULL)"))
        conn.execute(text("CREATE TABLE usuarios_app (id INTEGER PRIMARY KEY AUTOINCREMENT, fundacion_id INTEGER NOT NULL, username TEXT UNIQUE, FOREIGN KEY(fundacion_id) REFERENCES fundaciones(id))"))
        conn.execute(text("INSERT INTO fundaciones(nombre) VALUES ('Prueba')"))
        conn.execute(text("INSERT INTO usuarios_app(fundacion_id,username) VALUES (1,'usuario')"))
    metadata = prepare_metadata(engine)
    require({"fundaciones", "usuarios_app"} <= set(metadata.tables), "No reflejó el esquema SQLite")
    require(len(metadata.tables["usuarios_app"].foreign_key_constraints) == 1, "No preservó FK")
    require(sha256_file(source) and len(sha256_file(source)) == 64, "SHA-256 inválido")
    fingerprint_source = table_fingerprint(engine, metadata.tables["usuarios_app"])
    engine.dispose()

    sqlite_consistent_backup(source, snapshot)
    require(snapshot.is_file() and snapshot.stat().st_size > 0, "No creó snapshot consistente")
    conn = sqlite3.connect(snapshot)
    try:
        require(conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok", "Snapshot inválido")
        require(conn.execute("SELECT COUNT(*) FROM usuarios_app").fetchone()[0] == 1, "Snapshot perdió datos")
    finally:
        conn.close()
    snap_engine = create_engine(f"sqlite:///{snapshot.as_posix()}", future=True)
    snap_meta = prepare_metadata(snap_engine)
    require(table_fingerprint(snap_engine, snap_meta.tables["usuarios_app"]) == fingerprint_source, "La huella cambió en el snapshot")
    snap_engine.dispose()

masked = masked_url("postgresql+psycopg://user:secret@db.example:5432/pi")
require("secret" not in masked and "user:***@db.example" in masked, "La URL PostgreSQL no se enmascara")
source_text = (ROOT / "backend/tools/migrate_sqlite_to_postgresql.py").read_text(encoding="utf-8")
for token in [
    "PRAGMA integrity_check",
    "sqlite_consistent_backup",
    "source_sha256",
    "snapshot_sha256",
    "target_rows",
    "reset_sequences",
    "--verify-only",
    "--cleanup-on-error",
    "DRY_RUN_OK",
]:
    require(token in source_text, f"La herramienta de migración no contiene {token}")
for helper in [
    "CONFIGURAR_POSTGRESQL_LOCAL.bat",
    "MIGRAR_SQLITE_A_POSTGRESQL.bat",
    "RESPALDAR_POSTGRESQL.bat",
    "RESTAURAR_POSTGRESQL.bat",
]:
    require((ROOT / helper).is_file(), f"Falta {helper}")
print("Migración SQLite/PostgreSQL: PASS")
