"""Migración segura ALPHA32 - logo institucional por corporación/fundación.

No borra datos, no reemplaza tablas y solo agrega la columna logo_path cuando no existe.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from datetime import datetime


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    row = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
    if not row:
        return set()
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def migrate(database_path: str) -> dict[str, object]:
    db = Path(database_path)
    db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db))
    added: list[str] = []
    try:
        for table in ['corporaciones', 'fundaciones']:
            cols = _columns(conn, table)
            if cols and 'logo_path' not in cols:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN logo_path TEXT")
                added.append(f'{table}.logo_path')
        backend_dir = db.parent
        (backend_dir / 'static' / 'uploads' / 'logos').mkdir(parents=True, exist_ok=True)
        (backend_dir / 'static' / 'img').mkdir(parents=True, exist_ok=True)
        conn.commit()
        return {'ok': True, 'added': added, 'timestamp': datetime.now().isoformat(timespec='seconds')}
    finally:
        conn.close()


if __name__ == '__main__':
    print(migrate(str(Path(__file__).resolve().parents[1] / 'database.sqlite3')))
