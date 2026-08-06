"""Gestión central de conexiones para SQLite y PostgreSQL.

SQLite permanece disponible para desarrollo y recuperación local. PostgreSQL es
el backend recomendado para Railway y concurrencia real. Todo acceso nuevo debe
usar este Engine o el adaptador ``modules.dbapi_compat``.
"""
from __future__ import annotations

import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import DBAPIError, OperationalError


class DatabaseManager:
    def __init__(self) -> None:
        self.database_url: str | None = None
        self.database_path: str | None = None
        self.engine: Engine | None = None
        self.sqlite_timeout = 30
        self._sqlite_wal_lock = threading.RLock()
        self._sqlite_wal_initialized_path: str | None = None
        self._pool_lock = threading.RLock()
        self._pool_active = 0
        self._pool_peak = 0
        self._pool_checkouts = 0

    def configure(self, app) -> None:
        database_url = str(app.config["DATABASE_URL"]).strip()
        database_path = str(app.config.get("DATABASE_PATH") or "")
        if self.engine is not None and self.database_url == database_url:
            return
        if self.engine is not None:
            self.engine.dispose()

        self.sqlite_timeout = max(5, int(app.config.get("SQLITE_TIMEOUT_SECONDS", 30)))
        options = dict(app.config.get("SQLALCHEMY_ENGINE_OPTIONS", {}) or {})
        options.setdefault("pool_pre_ping", True)
        options.setdefault("future", True)

        if database_url.startswith("sqlite"):
            connect_args = dict(options.pop("connect_args", {}) or {})
            connect_args.update({"check_same_thread": False, "timeout": self.sqlite_timeout})
            options["connect_args"] = connect_args
            Path(database_path).parent.mkdir(parents=True, exist_ok=True)
        elif database_url.startswith("postgresql"):
            connect_args = dict(options.pop("connect_args", {}) or {})
            connect_args.setdefault("connect_timeout", max(2, int(app.config.get("DB_CONNECT_TIMEOUT_SECONDS", 10))))
            connect_args.setdefault("application_name", str(app.config.get("DB_APPLICATION_NAME", "primera-infancia")))
            statement_timeout = max(1000, int(app.config.get("DB_STATEMENT_TIMEOUT_MS", 30000)))
            connect_args.setdefault("options", f"-c statement_timeout={statement_timeout}")
            options.update({
                "connect_args": connect_args,
                "pool_size": max(1, int(app.config.get("DB_POOL_SIZE", 8))),
                "max_overflow": max(0, int(app.config.get("DB_MAX_OVERFLOW", 12))),
                "pool_timeout": max(1, int(app.config.get("DB_POOL_TIMEOUT_SECONDS", 10))),
                "pool_recycle": max(60, int(app.config.get("DB_POOL_RECYCLE_SECONDS", 900))),
                "pool_use_lifo": True,
                "pool_reset_on_return": "rollback",
            })
        else:
            raise RuntimeError("DATABASE_URL no usa un dialecto admitido (SQLite o PostgreSQL).")

        self.database_url = database_url
        self.database_path = database_path
        self.engine = create_engine(database_url, **options)

        @event.listens_for(self.engine, "checkout")
        def _pool_checkout(_dbapi_connection, _connection_record, _connection_proxy):
            with self._pool_lock:
                self._pool_active += 1
                self._pool_checkouts += 1
                self._pool_peak = max(self._pool_peak, self._pool_active)

        @event.listens_for(self.engine, "checkin")
        def _pool_checkin(_dbapi_connection, _connection_record):
            with self._pool_lock:
                self._pool_active = max(0, self._pool_active - 1)

        if self.is_sqlite:
            self._initialize_sqlite_wal(database_path)

            @event.listens_for(self.engine, "connect")
            def _sqlite_pragmas(dbapi_connection, _connection_record):
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA foreign_keys = ON")
                cursor.execute(f"PRAGMA busy_timeout = {self.sqlite_timeout * 1000}")
                cursor.execute("PRAGMA synchronous = NORMAL")
                cursor.close()
        elif self.is_postgresql:
            @event.listens_for(self.engine, "connect")
            def _postgres_session(dbapi_connection, _connection_record):
                # Configuración por conexión sin abrir transacciones de negocio.
                with dbapi_connection.cursor() as cursor:
                    cursor.execute("SET TIME ZONE 'UTC'")
                dbapi_connection.commit()

        app.extensions["primera_infancia_database"] = self

    def _initialize_sqlite_wal(self, database_path: str) -> None:
        resolved = str(Path(database_path).resolve())
        if self._sqlite_wal_initialized_path == resolved:
            return
        with self._sqlite_wal_lock:
            if self._sqlite_wal_initialized_path == resolved:
                return
            connection = sqlite3.connect(resolved, timeout=self.sqlite_timeout, isolation_level=None)
            try:
                connection.execute(f"PRAGMA busy_timeout = {self.sqlite_timeout * 1000}")
                connection.execute("PRAGMA journal_mode = WAL").fetchone()
                connection.execute("PRAGMA synchronous = NORMAL")
                connection.execute("PRAGMA wal_autocheckpoint = 1000")
                self._sqlite_wal_initialized_path = resolved
            finally:
                connection.close()

    @property
    def dialect_name(self) -> str:
        return self.engine.dialect.name if self.engine is not None else ""

    @property
    def is_sqlite(self) -> bool:
        return self.dialect_name == "sqlite" or bool(self.database_url and self.database_url.startswith("sqlite"))

    @property
    def is_postgresql(self) -> bool:
        return self.dialect_name == "postgresql" or bool(self.database_url and self.database_url.startswith("postgresql"))

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

    def pool_snapshot(self) -> dict[str, Any]:
        with self._pool_lock:
            data = {
                "active": self._pool_active,
                "peak": self._pool_peak,
                "checkouts": self._pool_checkouts,
            }
        pool = getattr(self.engine, "pool", None)
        for name in ("size", "checkedin", "checkedout", "overflow"):
            method = getattr(pool, name, None)
            if callable(method):
                try:
                    data[name] = method()
                except Exception:
                    pass
        return data

    @staticmethod
    def _retryable_transaction_error(exc: Exception) -> bool:
        original = getattr(exc, "orig", None)
        pgcode = getattr(original, "sqlstate", None) or getattr(original, "pgcode", None)
        if pgcode in {"40001", "40P01", "55P03"}:
            return True
        message = str(original or exc).lower()
        return "database is locked" in message or "database is busy" in message

    def execute_transaction(self, callback, *, retries: int = 3, base_delay: float = 0.05):
        """Ejecuta una transacción reintentable para fallos transitorios seguros."""
        last = None
        for attempt in range(max(1, retries)):
            try:
                with self.transaction() as connection:
                    return callback(connection)
            except (OperationalError, DBAPIError) as exc:
                last = exc
                if attempt + 1 >= retries or not self._retryable_transaction_error(exc):
                    raise
                time.sleep(base_delay * (2 ** attempt))
        raise last  # pragma: no cover

    def healthcheck(self) -> dict[str, Any]:
        started = __import__('time').perf_counter()
        try:
            with self.connection() as connection:
                connection.execute(text("SELECT 1"))
            return {
                "ok": True,
                "dialect": self.dialect_name,
                "latency_ms": round((__import__('time').perf_counter() - started) * 1000, 2),
                "pool": self.pool_snapshot(),
            }
        except Exception as exc:
            return {
                "ok": False,
                "dialect": self.dialect_name,
                "latency_ms": round((__import__('time').perf_counter() - started) * 1000, 2),
                "error": type(exc).__name__,
                "pool": self.pool_snapshot(),
            }

    def legacy_sqlite_connection(self):
        if self.is_sqlite:
            if not self.database_path:
                raise RuntimeError("DATABASE_PATH no está configurado.")
            path = Path(self.database_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            connection = sqlite3.connect(str(path), timeout=self.sqlite_timeout)
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute(f"PRAGMA busy_timeout = {self.sqlite_timeout * 1000}")
            connection.execute("PRAGMA synchronous = NORMAL")
            return connection
        # Importación diferida para evitar ciclo de módulos.
        from modules.dbapi_compat import CompatConnection
        return CompatConnection()

    def dispose(self) -> None:
        if self.engine is not None:
            self.engine.dispose()


database = DatabaseManager()


def configure_database(app) -> DatabaseManager:
    database.configure(app)
    return database


def get_db_connection():
    return database.legacy_sqlite_connection()
