from __future__ import annotations

import os
import sys

CURRENT_DIR = os.path.dirname(__file__)
BACKEND_DIR = os.path.abspath(os.path.join(CURRENT_DIR, '..'))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from services.rpp_minutas_service import init_schema


def migrate(database_path: str) -> None:
    init_schema(database_path)


if __name__ == '__main__':
    db = sys.argv[1] if len(sys.argv) > 1 else os.path.join(BACKEND_DIR, 'database.sqlite3')
    migrate(db)
    print(f'ALPHA53 migración aplicada en {db}')
