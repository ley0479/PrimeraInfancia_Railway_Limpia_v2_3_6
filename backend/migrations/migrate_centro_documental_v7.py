from __future__ import annotations

import os

from modules.dbapi_compat import sqlite3
from modules.centro_documental.schema import DOCUMENTS_SCHEMA_SQL, DOCUMENTS_SCHEMA_VERSION


def migrate(database_path: str) -> dict:
    previous = os.environ.get("APP_SCHEMA_MIGRATION_MODE")
    os.environ["APP_SCHEMA_MIGRATION_MODE"] = "1"
    try:
        connection = sqlite3.connect(str(database_path))
        try:
            connection.executescript(DOCUMENTS_SCHEMA_SQL)
            connection.commit()
        finally:
            connection.close()
    finally:
        if previous is None:
            os.environ.pop("APP_SCHEMA_MIGRATION_MODE", None)
        else:
            os.environ["APP_SCHEMA_MIGRATION_MODE"] = previous
    return {"ok": True, "documents_schema_version": DOCUMENTS_SCHEMA_VERSION}


if __name__ == "__main__":
    from config import Config
    print(migrate(str(Config.DATABASE_PATH)))
