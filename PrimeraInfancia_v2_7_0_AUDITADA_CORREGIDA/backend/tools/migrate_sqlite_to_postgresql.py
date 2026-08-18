#!/usr/bin/env python3
"""Migración reanudable, no destructiva y verificable de SQLite a PostgreSQL.

La herramienta conserva el SQLite original, crea un snapshot consistente con
la API backup de SQLite, valida esquema/conteos/huellas, restablece secuencias
y deja un reporte JSON. No cambia DATABASE_URL ni activa PostgreSQL por sí sola.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import sys
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlsplit, urlunsplit

from sqlalchemy import MetaData, create_engine, inspect, select, text
from sqlalchemy.engine import Engine

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))
from config import normalize_database_url  # noqa: E402


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def masked_url(url: str) -> str:
    parts = urlsplit(url.replace("postgresql+psycopg://", "postgresql://", 1))
    host = parts.hostname or ""
    port = f":{parts.port}" if parts.port else ""
    user = f"{parts.username}:***@" if parts.username else ""
    return urlunsplit((parts.scheme, user + host + port, parts.path, "", ""))


def quote_identifier(value: str) -> str:
    if not value or "\x00" in value:
        raise ValueError("Identificador SQL inválido")
    return '"' + value.replace('"', '""') + '"'


def sqlite_consistent_backup(source: Path, destination: Path) -> None:
    """Copia consistente incluso cuando SQLite usa WAL."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    src = sqlite3.connect(f"file:{source.as_posix()}?mode=ro", uri=True, timeout=60)
    dst = sqlite3.connect(str(destination), timeout=60)
    try:
        src.execute("PRAGMA busy_timeout=60000")
        src.backup(dst, pages=1000, sleep=0.05)
        result = dst.execute("PRAGMA integrity_check").fetchone()
        if not result or str(result[0]).lower() != "ok":
            raise RuntimeError(f"Snapshot SQLite inválido: {result}")
    finally:
        dst.close()
        src.close()


def scalar_count(engine: Engine, table_name: str, schema: str | None = None) -> int:
    qualified = f"{quote_identifier(schema)}.{quote_identifier(table_name)}" if schema else quote_identifier(table_name)
    with engine.connect() as conn:
        return int(conn.execute(text(f"SELECT COUNT(*) FROM {qualified}")).scalar_one())


def normalize_value(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        return format(value, ".17g")
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, (bytes, bytearray, memoryview)):
        return bytes(value).hex()
    return str(value)


def table_fingerprint(engine: Engine, table, *, schema: str | None = None, batch_size: int = 2000) -> str:
    """Huella estable por contenido ordenado por PK o por todas las columnas."""
    metadata = MetaData()
    reflected = table
    if schema is not None:
        metadata.reflect(bind=engine, schema=schema, only=[table.name])
        reflected = metadata.tables[f"{schema}.{table.name}"]
    order_columns = list(reflected.primary_key.columns) or list(reflected.columns)
    digest = hashlib.sha256()
    offset = 0
    with engine.connect() as conn:
        while True:
            stmt = select(reflected)
            if order_columns:
                stmt = stmt.order_by(*order_columns)
            rows = conn.execute(stmt.offset(offset).limit(batch_size)).mappings().all()
            if not rows:
                break
            for row in rows:
                payload = [normalize_value(row[col.name]) for col in reflected.columns]
                digest.update(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
                digest.update(b"\n")
            offset += len(rows)
    return digest.hexdigest()


def reset_sequences(engine: Engine, table_names: list[str], schema: str) -> list[dict[str, Any]]:
    report: list[dict[str, Any]] = []
    with engine.begin() as conn:
        for table in table_names:
            rows = conn.execute(text("""
                SELECT column_name
                  FROM information_schema.columns
                 WHERE table_schema=:schema AND table_name=:table
                   AND column_default LIKE 'nextval(%'
                 ORDER BY ordinal_position
            """), {"schema": schema, "table": table}).fetchall()
            for (column,) in rows:
                qualified = f"{quote_identifier(schema)}.{quote_identifier(table)}"
                sequence = conn.execute(
                    text("SELECT pg_get_serial_sequence(:table_name, :column_name)"),
                    {"table_name": f"{schema}.{table}", "column_name": column},
                ).scalar_one_or_none()
                if not sequence:
                    continue
                maximum = conn.execute(text(f"SELECT MAX({quote_identifier(column)}) FROM {qualified}")).scalar_one()
                value = int(maximum or 1)
                called = maximum is not None
                conn.execute(text("SELECT setval(CAST(:seq AS regclass), :value, :called)"), {
                    "seq": sequence, "value": value, "called": called,
                })
                report.append({"table": table, "column": column, "sequence": sequence, "value": value})
    return report


def prepare_metadata(sqlite_engine: Engine) -> MetaData:
    metadata = MetaData()
    metadata.reflect(bind=sqlite_engine, views=False)
    for table in metadata.tables.values():
        for constraint in table.foreign_key_constraints:
            constraint.deferrable = True
            constraint.initially = "DEFERRED"
    return metadata


def target_user_tables(engine: Engine, schema: str) -> list[str]:
    return sorted(inspect(engine).get_table_names(schema=schema))


def schema_contract(engine: Engine, table_names: Iterable[str], schema: str | None = None) -> dict[str, Any]:
    inspector = inspect(engine)
    contract: dict[str, Any] = {}
    for name in table_names:
        contract[name] = {
            "columns": [
                {"name": c["name"], "nullable": bool(c.get("nullable", True)), "type": str(c.get("type"))}
                for c in inspector.get_columns(name, schema=schema)
            ],
            "primary_key": list((inspector.get_pk_constraint(name, schema=schema) or {}).get("constrained_columns") or []),
            "foreign_keys": sorted([
                {
                    "columns": list(fk.get("constrained_columns") or []),
                    "target_table": fk.get("referred_table"),
                    "target_columns": list(fk.get("referred_columns") or []),
                }
                for fk in inspector.get_foreign_keys(name, schema=schema)
            ], key=lambda x: (x["target_table"] or "", x["columns"])),
            "unique_constraints": sorted([
                sorted(item.get("column_names") or []) for item in inspector.get_unique_constraints(name, schema=schema)
            ]),
            "indexes": sorted([
                {"columns": list(item.get("column_names") or []), "unique": bool(item.get("unique"))}
                for item in inspector.get_indexes(name, schema=schema)
            ], key=lambda x: (x["columns"], x["unique"])),
        }
    return contract


def copy_table(source: Engine, target: Engine, table, batch_size: int, schema: str, *, start_offset: int = 0) -> int:
    target_metadata = MetaData()
    target_table = table.to_metadata(target_metadata, schema=schema)
    order_columns = list(table.primary_key.columns) or list(table.columns)
    total = 0
    offset = max(0, start_offset)
    with source.connect() as source_conn:
        while True:
            stmt = select(table)
            if order_columns:
                stmt = stmt.order_by(*order_columns)
            rows = source_conn.execute(stmt.offset(offset).limit(batch_size)).mappings().all()
            if not rows:
                break
            payload = [dict(row) for row in rows]
            with target.begin() as target_conn:
                target_conn.execute(text("SET CONSTRAINTS ALL DEFERRED"))
                target_conn.execute(target_table.insert(), payload)
            total += len(payload)
            offset += len(payload)
    return total


def validate_foreign_keys(target: Engine, schema: str) -> list[dict[str, Any]]:
    """PostgreSQL valida FKs al insertar; además reporta restricciones no validadas."""
    with target.connect() as conn:
        rows = conn.execute(text("""
            SELECT n.nspname AS schema_name, c.relname AS table_name, con.conname
              FROM pg_constraint con
              JOIN pg_class c ON c.oid=con.conrelid
              JOIN pg_namespace n ON n.oid=c.relnamespace
             WHERE n.nspname=:schema AND con.contype='f' AND NOT con.convalidated
             ORDER BY c.relname, con.conname
        """), {"schema": schema}).mappings().all()
    return [dict(row) for row in rows]


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrar Primera Infancia de SQLite a PostgreSQL")
    parser.add_argument("--sqlite", required=True)
    parser.add_argument("--postgres", default=os.getenv("DATABASE_URL"))
    parser.add_argument("--schema", default="public")
    parser.add_argument("--batch-size", type=int, default=1000)
    parser.add_argument("--allow-non-empty", action="store_true")
    parser.add_argument("--truncate-target", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument("--fingerprints", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--cleanup-on-error", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--report", default="data/migration_reports/sqlite_to_postgresql.json")
    args = parser.parse_args()

    source_path = Path(args.sqlite).expanduser().resolve()
    if not source_path.is_file():
        raise SystemExit(f"No existe el SQLite de origen: {source_path}")
    if not args.postgres:
        raise SystemExit("Falta --postgres o DATABASE_URL.")
    target_url = normalize_database_url(args.postgres)
    if not target_url.startswith("postgresql+psycopg://"):
        raise SystemExit("El destino debe ser PostgreSQL con psycopg.")

    report_path = Path(args.report).expanduser().resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    backup_dir = report_path.parent / "sqlite_backups"
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = backup_dir / f"{source_path.stem}_snapshot_{stamp}{source_path.suffix}"
    sqlite_consistent_backup(source_path, backup)

    report: dict[str, Any] = {
        "schema_version": 2,
        "started_at": now_iso(),
        "source": str(source_path),
        "source_sha256": sha256_file(source_path),
        "snapshot": str(backup),
        "snapshot_sha256": sha256_file(backup),
        "target": masked_url(target_url),
        "schema": args.schema,
        "dry_run": args.dry_run,
        "verify_only": args.verify_only,
        "fingerprints_enabled": args.fingerprints,
        "tables": [],
        "status": "RUNNING",
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    source = create_engine(f"sqlite:///{backup.as_posix()}", future=True)
    target = create_engine(target_url, pool_pre_ping=True, future=True)
    created_tables: list[str] = []
    target_was_empty = False
    try:
        with source.connect() as conn:
            integrity = conn.execute(text("PRAGMA integrity_check")).scalar_one()
        if str(integrity).lower() != "ok":
            raise RuntimeError(f"Integridad SQLite inválida: {integrity}")
        with target.connect() as conn:
            version = str(conn.execute(text("SHOW server_version")).scalar_one())
            conn.execute(text("SELECT 1"))
        report["postgres_version"] = version

        metadata = prepare_metadata(source)
        source_tables = [t for t in metadata.sorted_tables if not t.name.startswith("sqlite_")]
        names = [t.name for t in source_tables]
        report["source_table_count"] = len(names)
        report["source_tables"] = names
        report["source_schema_contract"] = schema_contract(source, names)
        existing = target_user_tables(target, args.schema)
        target_was_empty = not existing
        report["target_tables_before"] = existing
        if existing and not args.allow_non_empty and not args.truncate_target and not args.verify_only:
            raise RuntimeError("PostgreSQL no está vacío; use una base nueva o --truncate-target de forma consciente.")

        if args.dry_run:
            report["status"] = "DRY_RUN_OK"
            report["finished_at"] = now_iso()
            report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 0

        if not args.verify_only:
            if args.truncate_target and existing:
                with target.begin() as conn:
                    quoted = ", ".join(f"{quote_identifier(args.schema)}.{quote_identifier(name)}" for name in existing)
                    conn.execute(text(f"TRUNCATE TABLE {quoted} RESTART IDENTITY CASCADE"))
            with target.begin() as conn:
                conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {quote_identifier(args.schema)}"))
            target_metadata = MetaData(schema=args.schema)
            for table in source_tables:
                table.to_metadata(target_metadata, schema=args.schema)
            before_create = set(target_user_tables(target, args.schema))
            target_metadata.create_all(target, checkfirst=True)
            created_tables = sorted(set(target_user_tables(target, args.schema)) - before_create)

            for table in source_tables:
                source_count = scalar_count(source, table.name)
                target_before = scalar_count(target, table.name, args.schema)
                item: dict[str, Any] = {"table": table.name, "source_rows": source_count, "target_before": target_before, "status": "PENDING"}
                try:
                    if target_before and not args.allow_non_empty and not args.truncate_target:
                        raise RuntimeError(f"La tabla destino ya contiene {target_before} filas")
                    copied = copy_table(source, target, table, max(1, args.batch_size), args.schema, start_offset=target_before if args.allow_non_empty else 0)
                    target_after = scalar_count(target, table.name, args.schema)
                    expected = source_count if not args.allow_non_empty else target_before + copied
                    if target_after != expected:
                        raise RuntimeError(f"Conteo inconsistente esperado={expected}, destino={target_after}")
                    item.update({"copied_rows": copied, "target_rows": target_after, "status": "OK"})
                except Exception as exc:
                    item.update({"status": "ERROR", "error": f"{type(exc).__name__}: {exc}"})
                    report["tables"].append(item)
                    raise
                report["tables"].append(item)
                report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            report["sequences"] = reset_sequences(target, names, args.schema)

        missing_target = sorted(set(names) - set(target_user_tables(target, args.schema)))
        if missing_target:
            raise RuntimeError("Tablas faltantes en PostgreSQL: " + ", ".join(missing_target))
        verification = {}
        for table in source_tables:
            source_count = scalar_count(source, table.name)
            target_count = scalar_count(target, table.name, args.schema)
            item = {"source_rows": source_count, "target_rows": target_count, "count_match": source_count == target_count}
            if args.fingerprints:
                item["source_sha256"] = table_fingerprint(source, table)
                item["target_sha256"] = table_fingerprint(target, table, schema=args.schema)
                item["fingerprint_match"] = item["source_sha256"] == item["target_sha256"]
            verification[table.name] = item
        count_errors = [name for name, item in verification.items() if not item["count_match"]]
        fingerprint_errors = [name for name, item in verification.items() if args.fingerprints and not item.get("fingerprint_match")]
        report["verification"] = verification
        report["target_schema_contract"] = schema_contract(target, names, args.schema)
        report["foreign_keys_not_validated"] = validate_foreign_keys(target, args.schema)
        if count_errors or fingerprint_errors or report["foreign_keys_not_validated"]:
            raise RuntimeError(
                f"Verificación fallida: conteos={count_errors}, huellas={fingerprint_errors}, "
                f"fk_no_validadas={len(report['foreign_keys_not_validated'])}"
            )
        report["status"] = "VERIFIED" if args.verify_only else "OK"
        report["finished_at"] = now_iso()
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Migración verificada. Reporte: {report_path}")
        return 0
    except Exception as exc:
        if args.cleanup_on_error and target_was_empty and created_tables:
            try:
                with target.begin() as conn:
                    for table in reversed(created_tables):
                        conn.execute(text(
                            f"DROP TABLE IF EXISTS {quote_identifier(args.schema)}.{quote_identifier(table)} CASCADE"
                        ))
                report["cleanup"] = {"status": "OK", "dropped_tables": created_tables}
            except Exception as cleanup_exc:
                report["cleanup"] = {"status": "ERROR", "error": f"{type(cleanup_exc).__name__}: {cleanup_exc}"}
        report["status"] = "ERROR"
        report["finished_at"] = now_iso()
        report["error"] = f"{type(exc).__name__}: {exc}"
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"ERROR: {report['error']}", file=sys.stderr)
        print(f"Reporte: {report_path}", file=sys.stderr)
        return 1
    finally:
        source.dispose()
        target.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
