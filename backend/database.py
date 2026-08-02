"""Acceso transaccional a SQLite con ajustes seguros para el despliegue."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Connection, Engine


class DatabaseManager:
    def __init__(self) -> None:
        self.database_url: str | None = None
        self.database_path: str | None = None
        self.engine: Engine | None = None
        self.sqlite_timeout = 30

    def configure(self, app) -> None:
        database_url = str(app.config["DATABASE_URL"])
        database_path = str(app.config["DATABASE_PATH"])
        if self.engine is not None and self.database_url == database_url:
            return
        if self.engine is not None:
            self.engine.dispose()

        self.sqlite_timeout = max(5, int(app.config.get("SQLITE_TIMEOUT_SECONDS", 30)))
        options = dict(app.config.get("SQLALCHEMY_ENGINE_OPTIONS", {}))
        if database_url.startswith("sqlite"):
            connect_args = dict(options.pop("connect_args", {}) or {})
            connect_args.update({"check_same_thread": False, "timeout": self.sqlite_timeout})
            options["connect_args"] = connect_args
        else:
            options.setdefault("pool_size", 5)
            options.setdefault("max_overflow", 10)
            options.setdefault("pool_recycle", 1800)

        self.database_url = database_url
        self.database_path = database_path
        if database_url.startswith("sqlite"):
            Path(database_path).parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine(database_url, **options)

        if database_url.startswith("sqlite"):
            @event.listens_for(self.engine, "connect")
            def _sqlite_pragmas(dbapi_connection, _connection_record):
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA foreign_keys = ON")
                cursor.execute(f"PRAGMA busy_timeout = {self.sqlite_timeout * 1000}")
                cursor.execute("PRAGMA journal_mode = WAL")
                cursor.execute("PRAGMA synchronous = NORMAL")
                cursor.close()

        app.extensions["primera_infancia_database"] = self

    @property
    def is_sqlite(self) -> bool:
        return bool(self.database_url and self.database_url.startswith("sqlite"))

    @contextmanager
    def connection(self) -> Iterator[Connection]:
        if self.engine is None:
            raise RuntimeError("DatabaseManager no ha sido configurado.")
        with self.engine.connect() as connection:
            yield connection

    @contextmanager
    def transaction(self) -> Iterator[Connection]:
        if self.engine is None:
            raise RuntimeError("DatabaseManager no ha sido configurado.")
        with self.engine.begin() as connection:
            yield connection

    def healthcheck(self) -> bool:
        try:
            with self.connection() as connection:
                connection.execute(text("SELECT 1"))
            return True
        except Exception:
            return False

    def legacy_sqlite_connection(self) -> sqlite3.Connection:
        if not self.is_sqlite:
            raise RuntimeError(
                "Este módulo aún usa el adaptador SQLite legado. "
                "Debe migrarse antes de activar PostgreSQL."
            )
        if not self.database_path:
            raise RuntimeError("DATABASE_PATH no está configurado.")
        path = Path(self.database_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(str(path), timeout=self.sqlite_timeout)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute(f"PRAGMA busy_timeout = {self.sqlite_timeout * 1000}")
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA synchronous = NORMAL")
        return connection

    def dispose(self) -> None:
        if self.engine is not None:
            self.engine.dispose()


database = DatabaseManager()


def configure_database(app) -> DatabaseManager:
    database.configure(app)
    return database


def get_db_connection() -> sqlite3.Connection:
    return database.legacy_sqlite_connection()
