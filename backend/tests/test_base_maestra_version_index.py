from __future__ import annotations

import sqlite3
import sys
from contextlib import closing
from pathlib import Path


BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from modules.base_maestra.repository import BaseMaestraRepository


def test_init_schema_repairs_legacy_unique_index_for_inactive_versions(tmp_path):
    database_path = tmp_path / 'base-maestra.sqlite3'
    repo = BaseMaestraRepository(str(database_path))
    repo.init_schema()

    with closing(sqlite3.connect(database_path)) as conn:
        conn.execute('DROP INDEX idx_master_version_activa')
        conn.execute(
            'CREATE UNIQUE INDEX idx_master_version_activa '
            'ON master_versiones(fundacion_id, activa)'
        )
        conn.execute(
            """
            INSERT INTO master_versiones
            (version_numero, fundacion_id, estado, activa, fecha_creacion)
            VALUES (1, 1, 'BORRADOR', 0, '2026-08-12T00:00:00')
            """
        )
        conn.commit()

    repo.init_schema()

    with closing(sqlite3.connect(database_path)) as conn:
        conn.execute(
            """
            INSERT INTO master_versiones
            (version_numero, fundacion_id, estado, activa, fecha_creacion)
            VALUES (2, 1, 'BORRADOR', 0, '2026-08-12T00:00:01')
            """
        )
        index_sql = conn.execute(
            "SELECT sql FROM sqlite_master WHERE name = 'idx_master_version_activa'"
        ).fetchone()[0]
        conn.commit()

    assert 'WHERE activa = 1' in index_sql
