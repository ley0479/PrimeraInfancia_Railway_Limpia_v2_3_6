from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.base_maestra.repository import BaseMaestraRepository  # noqa: E402


def main() -> None:
    database_path = os.environ.get('DATABASE_PATH') or str(ROOT / 'database.sqlite3')
    repo = BaseMaestraRepository(database_path)
    repo.init_schema()
    print(f'Migración Base Maestra aplicada correctamente sobre: {database_path}')


if __name__ == '__main__':
    main()
