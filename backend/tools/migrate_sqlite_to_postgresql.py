#!/usr/bin/env python3
"""Migración segura y verificable de SQLite a PostgreSQL.

Ejemplo:
  python backend/tools/migrate_sqlite_to_postgresql.py \
      --sqlite data/database.sqlite3 \
      --postgres "$DATABASE_URL" \
      --report data/migration_reports/sqlite_to_postgres.json

La herramienta no borra el origen. Crea un respaldo con SHA-256, exige un
PostgreSQL vacío por defecto, preserva identificadores y valida conteos.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from sqlalchemy import MetaData, create_engine, inspect, select, text
from sqlalchemy.engine import Engine

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from config import normalize_database_url  # noqa: E402


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def masked_url(url: str) -> str:
    parts = urlsplit(url.replace('postgresql+psycopg://', 'postgresql://', 1))
    host = parts.hostname or ''
    port = f':{parts.port}' if parts.port else ''
    user = f'{parts.username}:***@' if parts.username else ''
    return urlunsplit((parts.scheme, user + host + port, parts.path, '', ''))


def scalar_count(engine: Engine, table_name: str, schema: str | None = None) -> int:
    qualified = f'"{schema}"."{table_name}"' if schema else f'"{table_name}"'
    with engine.connect() as conn:
        return int(conn.execute(text(f'SELECT COUNT(*) FROM {qualified}')).scalar_one())


def reset_sequences(engine: Engine, table_names: list[str], schema: str) -> list[dict[str, Any]]:
    report: list[dict[str, Any]] = []
    with engine.begin() as conn:
        for table in table_names:
            rows = conn.execute(text("""
                SELECT column_name
                  FROM information_schema.columns
                 WHERE table_schema=:schema
                   AND table_name=:table
                   AND column_default LIKE 'nextval(%'
                 ORDER BY ordinal_position
            """), {'schema': schema, 'table': table}).fetchall()
            for (column,) in rows:
                qualified = f'"{schema}"."{table}"'
                sequence = conn.execute(
                    text("SELECT pg_get_serial_sequence(:table_name, :column_name)"),
                    {'table_name': f'{schema}.{table}', 'column_name': column},
                ).scalar_one_or_none()
                if not sequence:
                    continue
                maximum = conn.execute(text(f'SELECT MAX("{column}") FROM {qualified}')).scalar_one()
                value = int(maximum or 1)
                called = bool(maximum is not None)
                conn.execute(text("SELECT setval(CAST(:seq AS regclass), :value, :called)"), {
                    'seq': sequence, 'value': value, 'called': called,
                })
                report.append({'table': table, 'column': column, 'sequence': sequence, 'value': value})
    return report


def prepare_metadata(sqlite_engine: Engine) -> MetaData:
    metadata = MetaData()
    metadata.reflect(bind=sqlite_engine, views=False)
    # Los ciclos, si existen, deben poder cargarse en una sola transacción.
    for table in metadata.tables.values():
        for constraint in table.foreign_key_constraints:
            constraint.deferrable = True
            constraint.initially = 'DEFERRED'
    return metadata


def target_user_tables(engine: Engine, schema: str) -> list[str]:
    return sorted(inspect(engine).get_table_names(schema=schema))


def copy_table(source: Engine, target: Engine, table, batch_size: int, schema: str) -> int:
    source_table = table
    target_metadata = MetaData()
    target_table = source_table.to_metadata(target_metadata, schema=schema)
    total = 0
    offset = 0
    with source.connect() as source_conn:
        while True:
            rows = source_conn.execute(select(source_table).offset(offset).limit(batch_size)).mappings().all()
            if not rows:
                break
            payload = [dict(row) for row in rows]
            with target.begin() as target_conn:
                target_conn.execute(text('SET CONSTRAINTS ALL DEFERRED'))
                target_conn.execute(target_table.insert(), payload)
            total += len(payload)
            offset += len(payload)
    return total


def main() -> int:
    parser = argparse.ArgumentParser(description='Migrar Primera Infancia de SQLite a PostgreSQL')
    parser.add_argument('--sqlite', required=True, help='Ruta al database.sqlite3 de origen')
    parser.add_argument('--postgres', default=os.getenv('DATABASE_URL'), help='URL PostgreSQL de destino')
    parser.add_argument('--schema', default='public')
    parser.add_argument('--batch-size', type=int, default=1000)
    parser.add_argument('--allow-non-empty', action='store_true')
    parser.add_argument('--truncate-target', action='store_true')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--report', default='data/migration_reports/sqlite_to_postgresql.json')
    args = parser.parse_args()

    source_path = Path(args.sqlite).expanduser().resolve()
    if not source_path.is_file():
        raise SystemExit(f'No existe el SQLite de origen: {source_path}')
    if not args.postgres:
        raise SystemExit('Falta --postgres o DATABASE_URL.')
    target_url = normalize_database_url(args.postgres)
    if not target_url.startswith('postgresql+psycopg://'):
        raise SystemExit('El destino debe ser PostgreSQL.')

    report_path = Path(args.report).expanduser().resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    backup_dir = report_path.parent / 'sqlite_backups'
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup = backup_dir / f'{source_path.stem}_antes_postgresql_{stamp}{source_path.suffix}'
    shutil.copy2(source_path, backup)

    report: dict[str, Any] = {
        'started_at': now_iso(),
        'source': str(source_path),
        'source_sha256': sha256_file(source_path),
        'backup': str(backup),
        'backup_sha256': sha256_file(backup),
        'target': masked_url(target_url),
        'schema': args.schema,
        'dry_run': bool(args.dry_run),
        'tables': [],
        'status': 'RUNNING',
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')

    source = create_engine(f'sqlite:///{source_path.as_posix()}', future=True)
    target = create_engine(target_url, pool_pre_ping=True, future=True)
    try:
        with source.connect() as conn:
            integrity = conn.execute(text('PRAGMA integrity_check')).scalar_one()
        if str(integrity).lower() != 'ok':
            raise RuntimeError(f'Integridad SQLite inválida: {integrity}')
        with target.connect() as conn:
            conn.execute(text('SELECT 1'))

        metadata = prepare_metadata(source)
        source_tables = [t for t in metadata.sorted_tables if not t.name.startswith('sqlite_')]
        target_metadata = MetaData(schema=args.schema)
        target_tables = {
            table.name: table.to_metadata(target_metadata, schema=args.schema)
            for table in source_tables
        }
        report['source_table_count'] = len(source_tables)
        report['source_tables'] = [t.name for t in source_tables]
        existing = target_user_tables(target, args.schema)
        if existing and not args.allow_non_empty and not args.truncate_target:
            raise RuntimeError(
                'PostgreSQL no está vacío. Use una base nueva o --truncate-target de forma consciente. '
                f'Tablas detectadas: {", ".join(existing[:20])}'
            )
        if args.dry_run:
            report['status'] = 'DRY_RUN_OK'
            report['finished_at'] = now_iso()
            report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 0

        if args.truncate_target and existing:
            with target.begin() as conn:
                quoted = ', '.join(f'"{args.schema}"."{name}"' for name in existing)
                conn.execute(text(f'TRUNCATE TABLE {quoted} RESTART IDENTITY CASCADE'))

        # SQLAlchemy traduce tipos SQLite a tipos PostgreSQL y crea las claves.
        # El esquema se crea explícitamente para soportar destinos distintos de public.
        with target.begin() as conn:
            conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{args.schema}"'))
        target_metadata.create_all(target, checkfirst=True)

        migration_errors: list[dict[str, str]] = []
        for table in source_tables:
            source_count = scalar_count(source, table.name)
            item: dict[str, Any] = {'table': table.name, 'source_rows': source_count, 'status': 'PENDING'}
            try:
                target_before = scalar_count(target, table.name, args.schema)
                if target_before and not args.allow_non_empty and not args.truncate_target:
                    raise RuntimeError(f'La tabla destino ya contiene {target_before} filas.')
                copied = copy_table(source, target, table, max(1, args.batch_size), args.schema)
                target_after = scalar_count(target, table.name, args.schema)
                item.update({'copied_rows': copied, 'target_rows': target_after})
                if target_after != source_count + target_before:
                    raise RuntimeError(
                        f'Conteo inconsistente: origen={source_count}, antes={target_before}, destino={target_after}'
                    )
                item['status'] = 'OK'
            except Exception as exc:
                item['status'] = 'ERROR'
                item['error'] = f'{type(exc).__name__}: {exc}'
                migration_errors.append({'table': table.name, 'error': item['error']})
            report['tables'].append(item)
            report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
            if migration_errors:
                break

        if migration_errors:
            raise RuntimeError('Falló la copia de datos: ' + migration_errors[0]['error'])

        report['sequences'] = reset_sequences(target, [t.name for t in source_tables], args.schema)
        report['verification'] = {
            item['table']: {'source': item['source_rows'], 'target': item['target_rows']}
            for item in report['tables']
        }
        report['status'] = 'OK'
        report['finished_at'] = now_iso()
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f'Migración completada. Reporte: {report_path}')
        return 0
    except Exception as exc:
        report['status'] = 'ERROR'
        report['finished_at'] = now_iso()
        report['error'] = f'{type(exc).__name__}: {exc}'
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f'ERROR: {report["error"]}', file=sys.stderr)
        print(f'Reporte: {report_path}', file=sys.stderr)
        return 1
    finally:
        source.dispose()
        target.dispose()


if __name__ == '__main__':
    raise SystemExit(main())
