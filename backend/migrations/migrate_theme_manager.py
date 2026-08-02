from __future__ import annotations

import os
from pathlib import Path

from modules.theme_manager.services import init_schema


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    db_path = os.environ.get('DATABASE_PATH') or str(root / 'database.sqlite3')
    init_schema(db_path)
    print(f'Migración Theme Manager aplicada sobre: {db_path}')


if __name__ == '__main__':
    main()
