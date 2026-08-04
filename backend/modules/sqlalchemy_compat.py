"""Compatibilidad transicional SQLite -> SQLAlchemy Core.

Este módulo permite migrar repositorios por etapas sin reescribir servicios
completos: acepta SQL histórico con placeholders ``?`` y lo ejecuta sobre el
Engine central de ``backend/database.py`` usando parámetros nombrados.

No activa PostgreSQL completo; solo elimina nuevas conexiones directas sqlite3
para los módulos migrados en Fase 2C.5.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence

from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection

from database import database

# El cortafuegos multi-fundación se comparte con sqlite3 directo. Se importa
# de forma normal porque tenant_sql_guard no depende de SQLAlchemy.
from modules.seguridad.tenant_context import current_tenant_context, strict_tenant_mode
from modules.seguridad.tenant_sql_guard import (
    TenantIsolationError,
    rewrite_tenant_sql,
    tenant_script_is_schema_only,
)

_CORE_TENANT_SCHEMA_CACHE: dict[str, bool] = {}


def _core_table_has_tenant(table: str) -> bool:
    table = str(table or '').lower()
    if not table or not re.fullmatch(r'[A-Za-z_]\w*', table):
        return False
    cached = _CORE_TENANT_SCHEMA_CACHE.get(table)
    if cached is not None:
        return cached
    if database.engine is None:
        return False
    try:
        columns = inspect(database.engine).get_columns(table)
        has_tenant = any(str(col.get('name') or '').lower() == 'fundacion_id' for col in columns)
    except Exception:
        has_tenant = False
    _CORE_TENANT_SCHEMA_CACHE[table] = has_tenant
    return has_tenant


def _guard_core_sql(sql: str, params: Any = ()) -> str:
    return rewrite_tenant_sql(sql, params, _core_table_has_tenant)


def _to_list(params: Iterable[Any] | Mapping[str, Any] | None = None) -> list[Any]:
    if params is None:
        return []
    if isinstance(params, Mapping):
        return list(params.values())
    if isinstance(params, (list, tuple)):
        return list(params)
    return list(params)


def convert_qmark_sql(sql: str, params: Iterable[Any] | Mapping[str, Any] | None = None) -> tuple[str, dict[str, Any]]:
    """Convierte placeholders SQLite ``?`` a ``:p0``, ``:p1``.

    Acepta también diccionarios para SQL que ya usa parámetros nombrados
    ``:nombre``. Esto permite migrar funciones históricas de app.py que mezclan
    placeholders SQLite y placeholders nombrados sin abrir conexiones sqlite3
    directas durante la Fase 2C.6.
    """
    if isinstance(params, Mapping):
        # Si el SQL ya usa parámetros nombrados, no convertir el bind. Si hay
        # signos ? en una consulta con dict, se considera error de uso interno.
        if '?' not in sql:
            return sql, dict(params)
        values = list(params.values())
    else:
        values = _to_list(params)

    result: list[str] = []
    bind: dict[str, Any] = {}
    idx = 0
    in_single = False
    in_double = False
    escape_next = False

    for ch in sql:
        if escape_next:
            result.append(ch)
            escape_next = False
            continue
        if ch == "\\":
            result.append(ch)
            escape_next = True
            continue
        if ch == "'" and not in_double:
            in_single = not in_single
            result.append(ch)
            continue
        if ch == '"' and not in_single:
            in_double = not in_double
            result.append(ch)
            continue
        if ch == '?' and not in_single and not in_double:
            name = f"p{idx}"
            result.append(f":{name}")
            bind[name] = values[idx] if idx < len(values) else None
            idx += 1
        else:
            result.append(ch)
    return ''.join(result), bind


def split_sql_script(script: str) -> list[str]:
    """Divide un script SQL simple respetando comillas básicas."""
    statements: list[str] = []
    current: list[str] = []
    in_single = False
    in_double = False
    escape_next = False
    for ch in script:
        if escape_next:
            current.append(ch)
            escape_next = False
            continue
        if ch == "\\":
            current.append(ch)
            escape_next = True
            continue
        if ch == "'" and not in_double:
            in_single = not in_single
            current.append(ch)
            continue
        if ch == '"' and not in_single:
            in_double = not in_double
            current.append(ch)
            continue
        if ch == ';' and not in_single and not in_double:
            statement = ''.join(current).strip()
            if statement:
                statements.append(statement)
            current = []
        else:
            current.append(ch)
    trailing = ''.join(current).strip()
    if trailing:
        statements.append(trailing)
    return statements


def normalize_ddl_for_engine(sql: str) -> str:
    """Normaliza DDL histórico para el dialecto activo.

    En SQLite se conserva prácticamente igual. En PostgreSQL se traduce una
    parte mínima para staging; las migraciones Alembic completas siguen siendo
    la fuente de verdad productiva.
    """
    engine = database.engine
    dialect = engine.dialect.name if engine is not None else 'sqlite'
    out = sql
    if dialect == 'postgresql':
        out = out.replace('INTEGER PRIMARY KEY AUTOINCREMENT', 'SERIAL PRIMARY KEY')
        out = out.replace('REAL', 'DOUBLE PRECISION')
        out = re.sub(r"DEFAULT\s+'?ACTIVA'?", "DEFAULT 'ACTIVA'", out, flags=re.I)
        out = re.sub(r"DEFAULT\s+'?ACTIVO'?", "DEFAULT 'ACTIVO'", out, flags=re.I)
    return out


def rows_to_dicts(result) -> list[dict[str, Any]]:
    return [dict(row._mapping) for row in result]


@dataclass
class CoreResult:
    rows: list[dict[str, Any]]
    rowcount: int = 0
    lastrowid: int = 0

    def fetchone(self) -> dict[str, Any] | None:
        return self.rows[0] if self.rows else None

    def fetchall(self) -> list[dict[str, Any]]:
        return list(self.rows)

    def __iter__(self):
        return iter(self.rows)

    def __len__(self) -> int:
        return len(self.rows)


class CoreCursor:
    def __init__(self, connection: Connection):
        self.connection = connection
        self._last_result = CoreResult([])
        self.lastrowid = 0
        self.rowcount = 0

    def execute(self, sql: str, params: Iterable[Any] | Mapping[str, Any] | None = None) -> CoreResult:
        guarded_sql = _guard_core_sql(sql, params or ())
        if re.match(r"^\s*(CREATE|ALTER|DROP)\b", guarded_sql, re.I):
            _CORE_TENANT_SCHEMA_CACHE.clear()
        sql2, bind = convert_qmark_sql(guarded_sql, params)
        result = self.connection.execute(text(sql2), bind)
        rows: list[dict[str, Any]] = []
        if result.returns_rows:
            rows = rows_to_dicts(result)
        self.rowcount = int(result.rowcount or 0)
        self.lastrowid = int(getattr(result, 'lastrowid', 0) or 0)
        self._last_result = CoreResult(rows, self.rowcount, self.lastrowid)
        return self._last_result

    def executemany(self, sql: str, seq_of_params: Sequence[Iterable[Any] | Mapping[str, Any]] | None = None) -> CoreResult:
        """Ejecuta inserciones/actualizaciones masivas con SQL histórico.

        ALPHA35: varios módulos antiguos esperan que ``cursor.executemany``
        exista como en ``sqlite3``. Este wrapper usa SQLAlchemy Core, por eso
        antes devolvía ``CoreCursor`` sin ese método y fallaba el procesamiento
        de Base Maestra con: ``CoreCursor object has no attribute executemany``.
        """
        rows_in = list(seq_of_params or [])
        if not rows_in:
            self.rowcount = 0
            self._last_result = CoreResult([], 0, self.lastrowid)
            return self._last_result

        first = rows_in[0]
        guarded_sql = _guard_core_sql(sql, first)
        # Cuando fundacion_id viene explícita, valida cada fila del lote.
        if 'fundacion_id' in sql.lower():
            for row in rows_in:
                _guard_core_sql(sql, row)
        if isinstance(first, Mapping) and '?' not in guarded_sql:
            sql2 = guarded_sql
            bind_rows = [dict(row) for row in rows_in]  # type: ignore[arg-type]
        else:
            sql2, _ = convert_qmark_sql(guarded_sql, first)
            bind_rows = [convert_qmark_sql(guarded_sql, row)[1] for row in rows_in]

        result = self.connection.execute(text(sql2), bind_rows)
        rowcount = int(result.rowcount if result.rowcount is not None and result.rowcount >= 0 else len(rows_in))
        self.rowcount = rowcount
        self.lastrowid = int(getattr(result, 'lastrowid', 0) or self.lastrowid or 0)
        self._last_result = CoreResult([], rowcount, self.lastrowid)
        return self._last_result

    def executescript(self, script: str) -> None:
        context = current_tenant_context()
        if (
            strict_tenant_mode()
            and context.tenant_id
            and not context.allow_global
            and not tenant_script_is_schema_only(script)
        ):
            raise TenantIsolationError(
                'execute_script con DML no está permitido dentro de una operación multi-fundación.'
            )
        for statement in split_sql_script(script):
            statement = normalize_ddl_for_engine(statement)
            self.connection.execute(text(statement))
        _CORE_TENANT_SCHEMA_CACHE.clear()
        self._last_result = CoreResult([])

    def fetchone(self) -> dict[str, Any] | None:
        return self._last_result.fetchone()

    def fetchall(self) -> list[dict[str, Any]]:
        return self._last_result.fetchall()


class CoreConnection:
    """Wrapper mínimo que imita lo necesario de sqlite3.Connection."""

    def __init__(self) -> None:
        if database.engine is None:
            raise RuntimeError('DatabaseManager no ha sido configurado.')
        self.connection = database.engine.connect()
        if database.is_sqlite:
            # ALPHA35: cada conexión usada por jobs en segundo plano configura
            # timeout/WAL para reducir bloqueos de SQLite durante lotes grandes.
            for pragma in (
                "PRAGMA busy_timeout=30000",
                "PRAGMA foreign_keys=ON",
                "PRAGMA journal_mode=WAL",
            ):
                try:
                    self.connection.exec_driver_sql(pragma)
                except Exception:
                    pass
            try:
                self.connection.commit()
            except Exception:
                pass
        self.transaction = self.connection.begin()
        self._cursor = CoreCursor(self.connection)

    def __enter__(self) -> "CoreConnection":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if exc_type is not None:
            self.rollback()
        self.close()

    def cursor(self) -> CoreCursor:
        return self._cursor

    def execute(self, sql: str, params: Iterable[Any] | None = None) -> CoreResult:
        return self._cursor.execute(sql, params)

    def executemany(self, sql: str, seq_of_params: Sequence[Iterable[Any] | Mapping[str, Any]] | None = None) -> CoreResult:
        return self._cursor.executemany(sql, seq_of_params)

    def executescript(self, script: str) -> None:
        return self._cursor.executescript(script)

    def commit(self) -> None:
        if self.transaction.is_active:
            self.transaction.commit()
        self.transaction = self.connection.begin()

    def rollback(self) -> None:
        if self.transaction.is_active:
            self.transaction.rollback()
        self.transaction = self.connection.begin()

    def close(self) -> None:
        try:
            if self.transaction.is_active:
                self.transaction.rollback()
        finally:
            self.connection.close()


class CoreCompatRepository:
    """Repositorio base transicional para módulos migrados a SQLAlchemy Core."""

    def connect(self) -> CoreConnection:
        return CoreConnection()

    def table_exists(self, table: str) -> bool:
        if database.engine is None:
            return False
        return inspect(database.engine).has_table(table)

    def columns(self, table: str) -> set[str]:
        if database.engine is None or not self.table_exists(table):
            return set()
        inspector = inspect(database.engine)
        return {col['name'] for col in inspector.get_columns(table)}

    def ensure_column(self, table: str, column: str, definition: str) -> None:
        if column in self.columns(table):
            return
        ddl = normalize_ddl_for_engine(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
        with database.transaction() as conn:
            conn.execute(text(ddl))

    def execute(
        self,
        sql: str,
        params: Iterable[Any] | Mapping[str, Any] | None = None,
    ) -> int:
        guarded_sql = _guard_core_sql(sql, params or ())
        if re.match(r"^\s*(CREATE|ALTER|DROP)\b", guarded_sql, re.I):
            _CORE_TENANT_SCHEMA_CACHE.clear()
        with database.transaction() as conn:
            sql2, bind = convert_qmark_sql(guarded_sql, params)
            result = conn.execute(text(sql2), bind)
            try:
                return int(getattr(result, 'lastrowid', 0) or 0)
            except Exception:
                return 0

    def execute_update(
        self,
        sql: str,
        params: Iterable[Any] | Mapping[str, Any] | None = None,
    ) -> int:
        guarded_sql = _guard_core_sql(sql, params or ())
        with database.transaction() as conn:
            sql2, bind = convert_qmark_sql(guarded_sql, params)
            result = conn.execute(text(sql2), bind)
            return int(result.rowcount or 0)

    def fetch_all(
        self,
        sql: str,
        params: Iterable[Any] | Mapping[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        guarded_sql = _guard_core_sql(sql, params or ())
        with database.connection() as conn:
            sql2, bind = convert_qmark_sql(guarded_sql, params)
            result = conn.execute(text(sql2), bind)
            return rows_to_dicts(result)

    def fetch_one(
        self,
        sql: str,
        params: Iterable[Any] | Mapping[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        rows = self.fetch_all(sql, params)
        return rows[0] if rows else None

    def execute_script(self, script: str) -> None:
        context = current_tenant_context()
        if (
            strict_tenant_mode()
            and context.tenant_id
            and not context.allow_global
            and not tenant_script_is_schema_only(script)
        ):
            raise TenantIsolationError(
                'execute_script con DML no está permitido dentro de una operación multi-fundación.'
            )
        with database.transaction() as conn:
            for statement in split_sql_script(script):
                normalized = normalize_ddl_for_engine(statement)
                conn.execute(text(normalized))
        _CORE_TENANT_SCHEMA_CACHE.clear()

    def execute_many(
        self,
        sql: str,
        rows: Iterable[Iterable[Any] | Mapping[str, Any]] | None = None,
    ) -> int:
        rows_list = list(rows or [])
        if not rows_list:
            return 0

        guarded_sql = _guard_core_sql(sql, rows_list[0])
        # Cuando fundacion_id viene explícita, cada fila debe pertenecer al
        # tenant activo. Esto evita que una carga masiva mezcle fundaciones.
        if 'fundacion_id' in sql.lower():
            for params in rows_list:
                _guard_core_sql(sql, params)

        with database.transaction() as conn:
            total = 0
            for params in rows_list:
                sql2, bind = convert_qmark_sql(guarded_sql, params)
                result = conn.execute(text(sql2), bind)
                try:
                    total += int(result.rowcount or 0)
                except Exception:
                    pass
            return total

