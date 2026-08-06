"""Compatibilidad DB-API para SQLite y PostgreSQL.

La plataforma histórica usa una gran superficie de ``sqlite3.Connection`` y SQL
con placeholders ``?``. Este módulo conserva esa API para SQLite y, cuando el
Engine central usa PostgreSQL, ejecuta el mismo flujo mediante SQLAlchemy.

No pretende ocultar indefinidamente diferencias de dialecto: centraliza las
traducciones necesarias para que la migración sea reversible y auditable, y
permite retirar progresivamente el SQL legado sin mantener conexiones SQLite en
producción.
"""
from __future__ import annotations

import re
import sqlite3 as _sqlite3
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from sqlalchemy import MetaData, Table, inspect, text
from sqlalchemy.engine import Connection as SAConnection
from sqlalchemy.exc import DBAPIError, IntegrityError as SAIntegrityError, OperationalError as SAOperationalError
from sqlalchemy.schema import CreateTable

from database import database
from modules.seguridad.tenant_context import current_tenant_context, strict_tenant_mode
from modules.seguridad.tenant_sql_guard import TenantIsolationError, rewrite_tenant_sql, tenant_script_is_schema_only


class CompatRow(Mapping[str, Any]):
    """Fila compatible con acceso por nombre e índice, como ``sqlite3.Row``."""

    def __init__(self, keys: Sequence[str], values: Sequence[Any]):
        self._keys = tuple(str(k) for k in keys)
        self._values = tuple(values)
        self._map = dict(zip(self._keys, self._values))

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, Any]) -> "CompatRow":
        return cls(list(mapping.keys()), list(mapping.values()))

    def __getitem__(self, key):
        if isinstance(key, int):
            return self._values[key]
        return self._map[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._keys)

    def __len__(self) -> int:
        return len(self._keys)

    def keys(self):
        return list(self._keys)

    def values(self):
        return list(self._values)

    def items(self):
        return list(self._map.items())

    def __repr__(self) -> str:  # pragma: no cover - diagnóstico
        return f"CompatRow({self._map!r})"


@dataclass
class _SyntheticResult:
    rows: list[CompatRow]
    rowcount: int = 0
    lastrowid: int = 0


_QMARK_RE = re.compile(r"\?")
_TABLE_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

_TENANT_SCHEMA_CACHE: dict[str, bool] = {}

def _table_has_tenant(table: str) -> bool:
    table = str(table or '').lower()
    if not _TABLE_NAME_RE.fullmatch(table):
        return False
    if table in _TENANT_SCHEMA_CACHE:
        return _TENANT_SCHEMA_CACHE[table]
    try:
        insp = inspect(database.engine)
        value = any(str(col.get("name") or "").lower() == "fundacion_id" for col in insp.get_columns(table))
    except Exception:
        value = False
    _TENANT_SCHEMA_CACHE[table] = value
    return value

def _guard_sql(sql: str, params: Any) -> str:
    return rewrite_tenant_sql(sql, params or (), _table_has_tenant)



def _convert_qmark(sql: str, params: Sequence[Any] | Mapping[str, Any] | None):
    if isinstance(params, Mapping):
        if "?" not in sql:
            return sql, dict(params)
        values = list(params.values())
    else:
        values = list(params or [])
    out: list[str] = []
    bind: dict[str, Any] = {}
    idx = 0
    single = False
    double = False
    escape = False
    for ch in sql:
        if escape:
            out.append(ch)
            escape = False
            continue
        if ch == "\\":
            out.append(ch)
            escape = True
            continue
        if ch == "'" and not double:
            single = not single
            out.append(ch)
            continue
        if ch == '"' and not single:
            double = not double
            out.append(ch)
            continue
        if ch == "?" and not single and not double:
            name = f"p{idx}"
            out.append(f":{name}")
            bind[name] = values[idx] if idx < len(values) else None
            idx += 1
        else:
            out.append(ch)
    return "".join(out), bind


def _replace_sqlite_double_quoted_literals(sql: str) -> str:
    # SQLite admite "texto" como literal en varios contextos; PostgreSQL lo
    # interpreta como identificador. Solo se corrigen contextos inequívocos.
    patterns = [
        (r"(=|<>|!=|LIKE|NOT\s+LIKE)\s*\"([^\"]*)\"", lambda m: f"{m.group(1)} '{m.group(2).replace(chr(39), chr(39)*2)}'"),
        (r"\bDEFAULT\s+\"([^\"]*)\"", lambda m: "DEFAULT '" + m.group(1).replace("'", "''") + "'"),
    ]
    out = sql
    for pattern, repl in patterns:
        out = re.sub(pattern, repl, out, flags=re.I)
    return out


def _translate_group_concat(sql: str) -> str:
    # Cubre las formas usadas por la plataforma: GROUP_CONCAT(col, 'sep').
    pattern = re.compile(r"GROUP_CONCAT\(\s*([^,()]+?)\s*,\s*('(?:''|[^'])*')\s*\)", re.I)
    return pattern.sub(r"STRING_AGG(CAST(\1 AS TEXT), \2)", sql)


def _translate_julianday(sql: str) -> str:
    """Traduce el subconjunto de ``julianday`` usado por el runtime.

    SQLite devuelve días como número real. PostgreSQL no ofrece esa función,
    por lo que se normaliza a epoch/86400. Los casos operativos actuales usan
    ``'now'`` o una columna/expresión de fecha sin llamadas anidadas.
    """
    out = re.sub(
        r"julianday\s*\(\s*(['\"]now['\"])\s*\)",
        "(EXTRACT(EPOCH FROM CURRENT_TIMESTAMP) / 86400.0)",
        sql,
        flags=re.I,
    )
    pattern = re.compile(r"julianday\s*\(\s*([^()]+?)\s*\)", re.I)

    def repl(match: re.Match[str]) -> str:
        expression = match.group(1).strip()
        return f"(EXTRACT(EPOCH FROM CAST({expression} AS TIMESTAMP)) / 86400.0)"

    return pattern.sub(repl, out)


def _sql_like(value: str, pattern: str) -> bool:
    escaped = re.escape(pattern).replace(r"%", ".*").replace(r"_", ".")
    return re.fullmatch(escaped, value, flags=re.I) is not None


def _translate_sqlite_sql(sql: str) -> str:
    out = str(sql or "").strip()
    out = _replace_sqlite_double_quoted_literals(out)
    out = re.sub(r"\[([^\]]+)\]", r'"\1"', out)
    out = re.sub(r"\bIFNULL\s*\(", "COALESCE(", out, flags=re.I)
    out = re.sub(r"\s+COLLATE\s+NOCASE\b", "", out, flags=re.I)
    out = _translate_group_concat(out)
    out = _translate_julianday(out)
    out = re.sub(r"\bdate\s*\(\s*'now'\s*\)", "CURRENT_DATE", out, flags=re.I)
    out = re.sub(r"\bdatetime\s*\(\s*'now'\s*\)", "CURRENT_TIMESTAMP", out, flags=re.I)
    out = re.sub(r"\bdatetime\s*\(\s*\"now\"\s*\)", "CURRENT_TIMESTAMP", out, flags=re.I)
    out = re.sub(r"strftime\s*\(\s*'%Y'\s*,\s*([^\)]+)\)", r"TO_CHAR(CAST(\1 AS TIMESTAMP), 'YYYY')", out, flags=re.I)
    out = re.sub(r"strftime\s*\(\s*'%m'\s*,\s*([^\)]+)\)", r"TO_CHAR(CAST(\1 AS TIMESTAMP), 'MM')", out, flags=re.I)
    out = re.sub(
        r"printf\s*\(\s*['\"]%0(\d+)d['\"]\s*,\s*([^\)]+)\)",
        lambda m: f"LPAD(CAST({m.group(2).strip()} AS TEXT), {int(m.group(1))}, '0')",
        out,
        flags=re.I,
    )
    out = re.sub(r"\bINSERT\s+OR\s+IGNORE\s+INTO\b", "INSERT INTO", out, flags=re.I)
    # La cláusula se agrega al final si la consulta no ya tiene ON CONFLICT.
    if re.match(r"^\s*INSERT\s+INTO\b", out, re.I) and " OR IGNORE " not in sql.upper() and "ON CONFLICT" not in out.upper():
        pass
    elif re.search(r"\bINSERT\s+OR\s+IGNORE\s+INTO\b", sql, re.I) and "ON CONFLICT" not in out.upper():
        out = out.rstrip().rstrip(";") + " ON CONFLICT DO NOTHING"
    return out


def _translate_ddl(sql: str) -> str:
    out = _translate_sqlite_sql(sql)
    out = re.sub(r"\bINTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT\b", "BIGSERIAL PRIMARY KEY", out, flags=re.I)
    out = re.sub(r"\bINTEGER\s+PRIMARY\s+KEY\b", "BIGSERIAL PRIMARY KEY", out, flags=re.I)
    out = re.sub(r"\bAUTOINCREMENT\b", "", out, flags=re.I)
    out = re.sub(r"\bREAL\b", "DOUBLE PRECISION", out, flags=re.I)
    out = re.sub(r"\bBLOB\b", "BYTEA", out, flags=re.I)
    out = re.sub(r"DEFAULT\s*\(\s*CURRENT_TIMESTAMP\s*\)", "DEFAULT CURRENT_TIMESTAMP", out, flags=re.I)
    return out


def _split_script(script: str) -> list[str]:
    statements: list[str] = []
    current: list[str] = []
    single = False
    double = False
    escape = False
    for ch in script:
        if escape:
            current.append(ch)
            escape = False
            continue
        if ch == "\\":
            current.append(ch)
            escape = True
            continue
        if ch == "'" and not double:
            single = not single
        elif ch == '"' and not single:
            double = not double
        if ch == ";" and not single and not double:
            statement = "".join(current).strip()
            if statement:
                statements.append(statement)
            current = []
        else:
            current.append(ch)
    tail = "".join(current).strip()
    if tail:
        statements.append(tail)
    return statements


def _table_pk_name(table_name: str) -> str | None:
    if not database.engine or not _TABLE_NAME_RE.fullmatch(table_name or ""):
        return None
    try:
        pk = inspect(database.engine).get_pk_constraint(table_name).get("constrained_columns") or []
        return str(pk[0]) if len(pk) == 1 else None
    except Exception:
        return None


def _insert_table_name(sql: str) -> str | None:
    match = re.match(r'^\s*INSERT\s+INTO\s+"?([A-Za-z_][A-Za-z0-9_]*)"?', sql, re.I)
    return match.group(1) if match else None


class CompatCursor:
    def __init__(self, connection: "CompatConnection"):
        self._owner = connection
        self._result = _SyntheticResult([])
        self.rowcount = -1
        self.lastrowid = 0
        self.description = None

    def _set_rows(self, rows: list[CompatRow], rowcount: int | None = None, lastrowid: int = 0):
        self._result = _SyntheticResult(rows, len(rows) if rowcount is None else rowcount, lastrowid)
        self.rowcount = self._result.rowcount
        self.lastrowid = lastrowid
        self._owner._lastrowid = lastrowid or self._owner._lastrowid
        self.description = [(k, None, None, None, None, None, None) for k in (rows[0].keys() if rows else [])]
        return self

    def _pragma(self, sql: str):
        raw = sql.strip().rstrip(';')
        m = re.match(r'PRAGMA\s+table_info\s*\(\s*["\']?([A-Za-z_][A-Za-z0-9_]*)["\']?\s*\)', raw, re.I)
        if m:
            table = m.group(1)
            inspector = inspect(database.engine)
            cols = inspector.get_columns(table) if inspector.has_table(table) else []
            pk_cols = set((inspector.get_pk_constraint(table) or {}).get('constrained_columns') or []) if cols else set()
            rows = []
            for idx, col in enumerate(cols):
                rows.append(CompatRow(
                    ['cid', 'name', 'type', 'notnull', 'dflt_value', 'pk'],
                    [idx, col['name'], str(col.get('type') or ''), 0 if col.get('nullable', True) else 1,
                     str(col.get('default')) if col.get('default') is not None else None,
                     1 if col['name'] in pk_cols else 0],
                ))
            return self._set_rows(rows)
        if re.match(r'PRAGMA\s+integrity_check', raw, re.I):
            return self._set_rows([CompatRow(['integrity_check'], ['ok'])])
        if re.match(r'PRAGMA\s+foreign_key_check', raw, re.I):
            return self._set_rows([])
        if re.match(r'PRAGMA\s+(foreign_keys|busy_timeout|synchronous|journal_mode|wal_autocheckpoint)', raw, re.I):
            return self._set_rows([])
        return self._set_rows([])

    def _sqlite_master(self, sql: str, params):
        inspector = inspect(database.engine)
        names = inspector.get_table_names()
        lower = sql.lower()
        wanted = None
        values = list(params.values()) if isinstance(params, Mapping) else list(params or [])
        if re.search(r"name\s*=\s*\?", lower) and values:
            wanted = str(values[0])
            names = [n for n in names if n == wanted]
        positive_patterns = re.findall(r"name\s+like\s+['\"]([^'\"]+)['\"]", sql, flags=re.I)
        negative_patterns = re.findall(r"name\s+not\s+like\s+['\"]([^'\"]+)['\"]", sql, flags=re.I)
        # Quitar los patrones NOT LIKE de la lista positiva porque el regex de
        # LIKE también los captura como subcadena.
        positive_patterns = [p for p in positive_patterns if p not in negative_patterns]
        if positive_patterns:
            names = [name for name in names if any(_sql_like(name, pattern) for pattern in positive_patterns)]
        if negative_patterns:
            names = [name for name in names if all(not _sql_like(name, pattern) for pattern in negative_patterns)]
        rows: list[CompatRow] = []
        if re.search(r"select\s+sql\s+from\s+sqlite_master", lower):
            for name in names:
                try:
                    md = MetaData()
                    table = Table(name, md, autoload_with=database.engine)
                    ddl = str(CreateTable(table).compile(database.engine))
                except Exception:
                    ddl = None
                rows.append(CompatRow(['sql'], [ddl]))
        elif re.search(r"select\s+type\s*,\s*name\s*,\s*sql", lower):
            for name in names:
                try:
                    md = MetaData()
                    table = Table(name, md, autoload_with=database.engine)
                    ddl = str(CreateTable(table).compile(database.engine))
                except Exception:
                    ddl = None
                rows.append(CompatRow(['type', 'name', 'sql'], ['table', name, ddl]))
        else:
            rows = [CompatRow(['name'], [name]) for name in names]
        return self._set_rows(rows)

    def execute(self, sql: str, params: Sequence[Any] | Mapping[str, Any] | None = None):
        raw = _guard_sql(str(sql or '').strip(), params)
        upper = raw.upper()
        if upper.startswith('PRAGMA'):
            return self._pragma(raw)
        if 'SQLITE_MASTER' in upper:
            return self._sqlite_master(raw, params)
        if re.match(r'^\s*SELECT\s+LAST_INSERT_ROWID\s*\(\s*\)', raw, re.I):
            return self._set_rows([CompatRow(['last_insert_rowid()'], [self._owner._lastrowid])])
        if re.match(r'^\s*BEGIN(?:\s+IMMEDIATE|\s+EXCLUSIVE)?\s*$', raw, re.I):
            self._owner._ensure_transaction()
            return self._set_rows([], 0)
        if re.match(r'^\s*(COMMIT|END)\s*$', raw, re.I):
            self._owner.commit()
            return self._set_rows([], 0)
        if re.match(r'^\s*ROLLBACK\s*$', raw, re.I):
            self._owner.rollback()
            return self._set_rows([], 0)

        translated = _translate_ddl(raw) if re.match(r'^\s*(CREATE|ALTER|DROP)\b', raw, re.I) else _translate_sqlite_sql(raw)
        table_name = _insert_table_name(translated)
        pk_name = _table_pk_name(table_name) if table_name else None
        add_returning = bool(
            table_name and pk_name and re.match(r'^\s*INSERT\s+INTO\b', translated, re.I)
            and ' RETURNING ' not in translated.upper()
        )
        if add_returning:
            translated = translated.rstrip().rstrip(';') + f' RETURNING "{pk_name}"'

        sql2, bind = _convert_qmark(translated, params)
        self._owner._ensure_transaction()
        try:
            result = self._owner._connection.execute(text(sql2), bind)
        except SAIntegrityError as exc:
            raise _sqlite3.IntegrityError(str(getattr(exc, "orig", exc))) from exc
        except SAOperationalError as exc:
            raise _sqlite3.OperationalError(str(getattr(exc, "orig", exc))) from exc
        except DBAPIError as exc:
            raise _sqlite3.DatabaseError(str(getattr(exc, "orig", exc))) from exc
        rows: list[CompatRow] = []
        lastrowid = 0
        if result.returns_rows:
            mappings = result.mappings().all()
            rows = [CompatRow.from_mapping(m) for m in mappings]
            if add_returning and rows:
                try:
                    lastrowid = int(rows[0][pk_name])
                except Exception:
                    lastrowid = 0
                # sqlite INSERT no devuelve filas; ocultar RETURNING al llamador.
                rows = []
        rowcount = int(result.rowcount if result.rowcount is not None and result.rowcount >= 0 else len(rows))
        return self._set_rows(rows, rowcount, lastrowid)

    def executemany(self, sql: str, seq_of_params: Iterable[Sequence[Any] | Mapping[str, Any]]):
        rows = list(seq_of_params or [])
        if not rows:
            return self._set_rows([], 0)
        raw = _guard_sql(str(sql or '').strip(), rows[0] if rows else ())
        if 'fundacion_id' in raw.lower():
            for item in rows:
                _guard_sql(str(sql or '').strip(), item)
        translated = _translate_ddl(raw) if re.match(r'^\s*(CREATE|ALTER|DROP)\b', raw, re.I) else _translate_sqlite_sql(raw)
        first = rows[0]
        if isinstance(first, Mapping) and '?' not in translated:
            sql2 = translated
            binds = [dict(r) for r in rows]  # type: ignore[arg-type]
        else:
            sql2, _ = _convert_qmark(translated, first)
            binds = [_convert_qmark(translated, row)[1] for row in rows]
        self._owner._ensure_transaction()
        try:
            result = self._owner._connection.execute(text(sql2), binds)
        except SAIntegrityError as exc:
            raise _sqlite3.IntegrityError(str(getattr(exc, "orig", exc))) from exc
        except SAOperationalError as exc:
            raise _sqlite3.OperationalError(str(getattr(exc, "orig", exc))) from exc
        except DBAPIError as exc:
            raise _sqlite3.DatabaseError(str(getattr(exc, "orig", exc))) from exc
        count = int(result.rowcount if result.rowcount is not None and result.rowcount >= 0 else len(rows))
        return self._set_rows([], count)

    def executescript(self, script: str):
        context = current_tenant_context()
        if strict_tenant_mode() and context.tenant_id and not context.allow_global and not tenant_script_is_schema_only(script):
            raise TenantIsolationError('executescript con DML no está permitido dentro de una operación multi-fundación.')
        for statement in _split_script(script):
            self.execute(statement)
        return self

    def fetchone(self):
        return self._result.rows[0] if self._result.rows else None

    def fetchall(self):
        return list(self._result.rows)

    def fetchmany(self, size: int | None = None):
        return list(self._result.rows[: int(size or 1)])

    def __iter__(self):
        return iter(self._result.rows)

    def close(self):
        return None


class CompatConnection:
    def __init__(self):
        if database.engine is None:
            raise RuntimeError('El Engine central no está configurado.')
        self._connection: SAConnection = database.engine.connect()
        self._transaction = None
        self._lastrowid = 0
        self.row_factory = CompatRow
        self.isolation_level = None
        self.total_changes = 0
        self._cursor = CompatCursor(self)

    def _ensure_transaction(self):
        if self._transaction is None or not self._transaction.is_active:
            self._transaction = self._connection.begin()

    @property
    def in_transaction(self) -> bool:
        return bool(self._transaction is not None and self._transaction.is_active)

    def cursor(self):
        return self._cursor

    def execute(self, sql, params=None):
        return self._cursor.execute(sql, params)

    def executemany(self, sql, rows):
        return self._cursor.executemany(sql, rows)

    def executescript(self, script):
        return self._cursor.executescript(script)

    def commit(self):
        if self._transaction is not None and self._transaction.is_active:
            self._transaction.commit()
        self._transaction = None

    def rollback(self):
        if self._transaction is not None and self._transaction.is_active:
            self._transaction.rollback()
        self._transaction = None

    def close(self):
        try:
            if self.in_transaction:
                self.rollback()
        finally:
            self._connection.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        try:
            if exc_type is None:
                self.commit()
            else:
                self.rollback()
        finally:
            self.close()
        return False

    def backup(self, target, *args, **kwargs):
        raise RuntimeError('La copia DB-API de SQLite no aplica a PostgreSQL. Use pg_dump o la herramienta de respaldo de la plataforma.')

    def iterdump(self):
        raise RuntimeError('iterdump no aplica a PostgreSQL. Use pg_dump.')


class _SQLiteProxy:
    # El atributo debe seguir siendo sqlite3.Row para que conexiones SQLite
    # explícitas (pruebas, migraciones y respaldos) conserven su row_factory.
    # CompatConnection produce CompatRow internamente y no depende de este valor.
    Row = _sqlite3.Row
    Connection = CompatConnection
    Cursor = CompatCursor
    Error = DBAPIError
    DatabaseError = DBAPIError
    OperationalError = _sqlite3.OperationalError
    IntegrityError = _sqlite3.IntegrityError
    PARSE_DECLTYPES = _sqlite3.PARSE_DECLTYPES
    PARSE_COLNAMES = _sqlite3.PARSE_COLNAMES
    Binary = staticmethod(_sqlite3.Binary)

    def connect(self, database_arg=None, *args, **kwargs):
        """Abre una conexión compatible sin secuestrar SQLite explícito.

        Los módulos de negocio históricos llaman ``sqlite3.connect`` con el
        ``DATABASE_PATH`` configurado. En PostgreSQL ese camino debe usar el
        adaptador. En cambio, herramientas de migración, pruebas y respaldos
        pueden abrir de forma deliberada *otro* archivo SQLite; esas conexiones
        deben conservar el driver nativo aun cuando el Engine principal sea
        PostgreSQL.
        """
        if database.engine is None or database.is_sqlite:
            return _sqlite3.connect(database_arg, *args, **kwargs)

        # ``:memory:`` y rutas SQLite explícitas distintas del DATABASE_PATH
        # pertenecen a pruebas, importaciones o respaldos, no al backend
        # PostgreSQL de la aplicación.
        if database_arg not in (None, ""):
            raw = str(database_arg)
            if raw == ":memory:" or raw.startswith("file:"):
                return _sqlite3.connect(database_arg, *args, **kwargs)
            try:
                from pathlib import Path

                explicit = Path(raw).expanduser().resolve()
                configured_raw = str(database.database_path or "").strip()
                configured = Path(configured_raw).expanduser().resolve() if configured_raw else None
                if configured is None or explicit != configured:
                    return _sqlite3.connect(database_arg, *args, **kwargs)
            except (OSError, RuntimeError, ValueError):
                # Una ruta no resoluble no debe convertirse silenciosamente en
                # la base productiva. Mantener el comportamiento sqlite3.
                return _sqlite3.connect(database_arg, *args, **kwargs)

        return CompatConnection()

    def __getattr__(self, name):
        return getattr(_sqlite3, name)


sqlite3 = _SQLiteProxy()
connect = sqlite3.connect
Row = _sqlite3.Row
Connection = CompatConnection
Cursor = CompatCursor
OperationalError = _sqlite3.OperationalError
IntegrityError = _sqlite3.IntegrityError
