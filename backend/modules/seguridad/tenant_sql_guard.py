"""Cortafuegos SQL de aislamiento por fundación para SQLite legado.

La plataforma todavía contiene consultas históricas escritas directamente con
``sqlite3``. Este guard agrega el predicado de fundación a sentencias simples y
falla de forma cerrada ante JOIN/subconsultas multi-tabla que no declaren su
alcance. No sustituye las pruebas de negocio, pero evita que una consulta nueva
sin filtro entregue datos de otra fundación silenciosamente.
"""
from __future__ import annotations

import re
import sqlite3
import threading
from typing import Any, Iterable, Mapping, Sequence

from .tenant_context import current_tenant_context, strict_tenant_mode


class TenantIsolationError(sqlite3.DatabaseError):
    """La sentencia no demuestra aislamiento suficiente para ejecutarse."""


_ORIGINAL_CONNECT = sqlite3.connect
_INSTALL_LOCK = threading.RLock()
_INSTALLED = False

# Tablas de control central: sus accesos se autorizan en la capa de roles/rutas.
CONTROL_TABLES = frozenset({
    "fundaciones", "usuarios_app", "sesiones_usuario", "recuperacion_password",
    "auth_intentos", "roles_sistema", "permisos_sistema", "rol_permiso",
    "planes_suscripcion", "modulos_plan", "paquetes_credito",
    "suscripciones_fundacion", "historial_suscripcion", "pagos_suscripcion",
    "movimientos_credito", "auditoria_facturacion", "configuracion",
})

# Catálogos institucionales que pueden tener fila global (NULL) y sobreescritura por tenant.
SHARED_OR_TENANT_TABLES = frozenset({
    "tm_temas", "sn_referencias_oms", "sn_entregables_catalogo",
    "pp_tipos_actividad", "gp_configuracion_entregables", "estandares_icbf",
})

# Rutas donde SUPERADMIN debe consultar el registro central de todos los clientes.
SUPERADMIN_GLOBAL_PREFIXES = (
    "/api/fundaciones", "/api/usuarios", "/api/seguridad",
    "/api/panel-comercial", "/api/gerencia-general", "/api/facturacion",
)

_SQL_START = re.compile(r"^\s*(SELECT|INSERT|REPLACE|UPDATE|DELETE)\b", re.I | re.S)
_IDENTIFIER = r'(?:"([A-Za-z_]\w*)"|`([A-Za-z_]\w*)`|\[([A-Za-z_]\w*)\]|([A-Za-z_]\w*))'


def _unquote_identifier(match: re.Match[str]) -> str:
    return next((g for g in match.groups() if g is not None), "")


def _mask_sql(sql: str) -> str:
    """Enmascara literales/comentarios conservando índices y paréntesis."""
    chars = list(sql)
    i = 0
    n = len(chars)
    state: str | None = None
    while i < n:
        ch = chars[i]
        nxt = chars[i + 1] if i + 1 < n else ""
        if state == "single":
            if ch == "'" and nxt == "'":
                chars[i] = chars[i + 1] = " "
                i += 2
                continue
            chars[i] = " "
            if ch == "'":
                state = None
            i += 1
            continue
        if state == "double":
            # Identificadores entre comillas se conservan para poder analizarlos.
            if ch == '"':
                state = None
            i += 1
            continue
        if state == "line_comment":
            chars[i] = " "
            if ch == "\n":
                state = None
            i += 1
            continue
        if state == "block_comment":
            chars[i] = " "
            if ch == "*" and nxt == "/":
                chars[i + 1] = " "
                i += 2
                state = None
                continue
            i += 1
            continue
        if ch == "'":
            chars[i] = " "
            state = "single"
        elif ch == '"':
            state = "double"
        elif ch == "-" and nxt == "-":
            chars[i] = chars[i + 1] = " "
            i += 2
            state = "line_comment"
            continue
        elif ch == "/" and nxt == "*":
            chars[i] = chars[i + 1] = " "
            i += 2
            state = "block_comment"
            continue
        i += 1
    return "".join(chars)


def _depth_map(masked: str) -> list[int]:
    depths: list[int] = [0] * (len(masked) + 1)
    depth = 0
    for i, ch in enumerate(masked):
        depths[i] = depth
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
    depths[len(masked)] = depth
    return depths


def _word_positions(masked: str, depth: list[int], words: Iterable[str], wanted_depth: int = 0) -> list[tuple[int, str]]:
    pattern = re.compile(r"\b(" + "|".join(re.escape(w) for w in words) + r")\b", re.I)
    return [(m.start(), m.group(1).upper()) for m in pattern.finditer(masked) if depth[m.start()] == wanted_depth]


def _first_clause_position(masked: str, depth: list[int], start: int = 0) -> int:
    clauses = ("GROUP", "HAVING", "ORDER", "LIMIT", "OFFSET", "RETURNING", "UNION", "EXCEPT", "INTERSECT")
    positions = [pos for pos, _ in _word_positions(masked, depth, clauses) if pos >= start]
    semicolon = masked.rfind(";")
    if semicolon >= start and depth[semicolon] == 0:
        positions.append(semicolon)
    return min(positions) if positions else len(masked)


def _has_top_level_where(masked: str, depth: list[int], before: int) -> bool:
    return any(pos < before for pos, word in _word_positions(masked, depth, ("WHERE",)) if word == "WHERE")


def _contains_nested_select(masked: str, depth: list[int]) -> bool:
    return any(depth[m.start()] > 0 for m in re.finditer(r"\bSELECT\b", masked, re.I))


def _find_simple_table(sql: str, operation: str) -> tuple[str, str] | None:
    """Retorna (tabla, alias) para una sentencia de una sola tabla."""
    masked = _mask_sql(sql)
    if operation == "SELECT":
        pattern = re.compile(r"\bFROM\s+" + _IDENTIFIER + r"(?:\s+(?:AS\s+)?([A-Za-z_]\w*))?", re.I)
    elif operation == "UPDATE":
        pattern = re.compile(r"\bUPDATE\s+" + _IDENTIFIER + r"(?:\s+(?:AS\s+)?([A-Za-z_]\w*))?", re.I)
    elif operation == "DELETE":
        pattern = re.compile(r"\bDELETE\s+FROM\s+" + _IDENTIFIER + r"(?:\s+(?:AS\s+)?([A-Za-z_]\w*))?", re.I)
    else:
        return None
    depth = _depth_map(masked)
    matches = [m for m in pattern.finditer(masked) if depth[m.start()] == 0]
    if len(matches) != 1:
        return None
    m = matches[0]
    groups = m.groups()
    table = next((g for g in groups[:4] if g), "").lower()
    alias = groups[4] if len(groups) > 4 else None
    if alias and alias.upper() in {
        "WHERE", "JOIN", "LEFT", "RIGHT", "INNER", "OUTER", "CROSS", "ON",
        "ORDER", "GROUP", "LIMIT", "OFFSET", "RETURNING", "SET",
    }:
        alias = None
    return table, (alias or table)


def _append_predicate(sql: str, condition: str, operation: str) -> str:
    masked = _mask_sql(sql)
    depth = _depth_map(masked)
    if operation == "UPDATE":
        # WHERE solo puede buscarse después de SET.
        set_match = next((m for m in re.finditer(r"\bSET\b", masked, re.I) if depth[m.start()] == 0), None)
        search_start = set_match.end() if set_match else 0
    else:
        search_start = 0
    boundary = _first_clause_position(masked, depth, search_start)
    has_where = any(
        pos >= search_start and pos < boundary
        for pos, _ in _word_positions(masked, depth, ("WHERE",))
    )
    connector = " AND " if has_where else " WHERE "
    return sql[:boundary].rstrip() + connector + condition + " " + sql[boundary:].lstrip()


def _parse_insert(sql: str) -> tuple[str, list[str], int, int, int, int] | None:
    """Tabla, columnas y posiciones del cierre de columnas/valores."""
    masked = _mask_sql(sql)
    m = re.search(r"\b(?:INSERT|REPLACE)(?:\s+OR\s+\w+)?\s+INTO\s+" + _IDENTIFIER + r"\s*\(", masked, re.I)
    if not m:
        return None
    table = next((g for g in m.groups()[:4] if g), "").lower()
    col_open = masked.find("(", m.start())
    depth = 1
    col_close = -1
    for i in range(col_open + 1, len(masked)):
        if masked[i] == "(": depth += 1
        elif masked[i] == ")":
            depth -= 1
            if depth == 0:
                col_close = i
                break
    if col_close < 0:
        return None
    values_match = re.search(r"\bVALUES\s*\(", masked[col_close + 1:], re.I)
    if not values_match:
        return None
    val_open = col_close + 1 + masked[col_close + 1:].find("(", values_match.start())
    depth = 1
    val_close = -1
    for i in range(val_open + 1, len(masked)):
        if masked[i] == "(": depth += 1
        elif masked[i] == ")":
            depth -= 1
            if depth == 0:
                val_close = i
                break
    if val_close < 0:
        return None
    raw_cols = sql[col_open + 1:col_close]
    columns = [c.strip().strip('"`[]').lower() for c in raw_cols.split(",")]
    return table, columns, col_open, col_close, val_open, val_close


def _split_csv(expr: str) -> list[str]:
    masked = _mask_sql(expr)
    depth = 0
    start = 0
    items: list[str] = []
    for i, ch in enumerate(masked):
        if ch == "(": depth += 1
        elif ch == ")": depth = max(0, depth - 1)
        elif ch == "," and depth == 0:
            items.append(expr[start:i].strip())
            start = i + 1
    items.append(expr[start:].strip())
    return items


def _qmark_index_before(sql: str, position: int) -> int:
    masked = _mask_sql(sql[:position])
    return masked.count("?")


def tenant_script_is_schema_only(sql_script: str) -> bool:
    """Permite únicamente DDL/PRAGMA en ``executescript`` durante requests.

    Los repositorios inicializan sus tablas de forma idempotente al entrar a
    ciertos módulos. Esos scripts no leen ni modifican filas de negocio. Los
    scripts con DML quedan bloqueados para evitar un bypass del cortafuegos.
    """
    masked = _mask_sql(sql_script)
    statements: list[str] = []
    start = 0
    depth = 0
    for index, char in enumerate(masked):
        if char == "(":
            depth += 1
        elif char == ")":
            depth = max(0, depth - 1)
        elif char == ";" and depth == 0:
            statement = masked[start:index].strip()
            if statement:
                statements.append(statement)
            start = index + 1
    tail = masked[start:].strip()
    if tail:
        statements.append(tail)
    if not statements:
        return True
    allowed = re.compile(
        r"^(?:CREATE(?:\s+UNIQUE)?|ALTER|DROP|PRAGMA|BEGIN|COMMIT|ROLLBACK|"
        r"SAVEPOINT|RELEASE|VACUUM|ANALYZE)\b",
        re.I | re.S,
    )
    return all(bool(allowed.match(statement)) for statement in statements)


def _validate_insert_tenant(
    sql: str,
    parameters: Any,
    columns: list[str],
    val_open: int,
    val_close: int,
    tenant_id: int,
) -> None:
    idx = columns.index("fundacion_id")
    values = _split_csv(sql[val_open + 1:val_close])
    if idx >= len(values):
        raise TenantIsolationError("INSERT con fundacion_id sin valor correspondiente.")
    token = values[idx].strip()
    if token == "?":
        qidx = _qmark_index_before(sql, val_open + 1)
        qidx += sum(item.count("?") for item in values[:idx])
        try:
            value = parameters[qidx]
        except Exception as exc:
            raise TenantIsolationError("No se pudo validar fundacion_id posicional.") from exc
    elif token.startswith(":") and isinstance(parameters, Mapping):
        value = parameters.get(token[1:])
    elif re.fullmatch(r"\d+", token):
        value = int(token)
    elif token.upper() in {"NULL", "NONE"}:
        value = None
    else:
        # Expresiones SQL no verificables se rechazan en modo estricto.
        raise TenantIsolationError("fundacion_id debe ser un entero o parámetro verificable.")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise TenantIsolationError("fundacion_id de INSERT es inválido.") from exc
    if parsed != tenant_id:
        raise TenantIsolationError(
            f"INSERT intentó escribir en fundación {parsed}; el contexto autenticado es {tenant_id}."
        )




def _bound_value(sql: str, token: str, token_position: int, parameters: Any) -> Any:
    """Resuelve un literal/parámetro SQL sin ejecutar la sentencia."""
    token = token.strip()
    if token == "?":
        index = _qmark_index_before(sql, token_position)
        try:
            return parameters[index]
        except Exception as exc:
            raise TenantIsolationError("No se pudo validar el parámetro de fundación.") from exc
    if token.startswith(":"):
        if not isinstance(parameters, Mapping):
            raise TenantIsolationError("La consulta usa parámetro nombrado sin un mapa de valores.")
        return parameters.get(token[1:])
    if re.fullmatch(r"\d+", token):
        return int(token)
    return None


def _complex_scope_is_safe(
    sql: str,
    parameters: Any,
    tenant_refs: list[tuple[str, str]],
    tenant_id: int,
) -> tuple[bool, list[str]]:
    """Valida que cada alias tenant de una consulta compleja esté anclado al tenant autenticado.

    No basta con encontrar el texto ``fundacion_id``: un parámetro suministrado
    por el cliente podría apuntar a otra fundación. Aquí se resuelven los
    parámetros posicionales/nombrados y se exige que cada alias esté comparado
    con el tenant actual o conectado a otro alias ya anclado.
    """
    masked = _mask_sql(sql)
    required = {str(alias or table).lower() for table, alias in tenant_refs}
    anchored: set[str] = set()
    edges: dict[str, set[str]] = {alias: set() for alias in required}
    unqualified_current = False

    # Expresión de fundación, con o sin COALESCE y con alias opcional.
    fund_expr = (
        r"(?:COALESCE\s*\(\s*(?:(?P<alias1>[A-Za-z_]\w*)\s*\.)?fundacion_id\s*,[^)]*\)"
        r"|(?:(?P<alias2>[A-Za-z_]\w*)\s*\.)?fundacion_id)"
    )
    rhs = r"(?P<rhs>\?|:[A-Za-z_]\w*|\d+|[A-Za-z_]\w*\.fundacion_id)"
    patterns = [
        re.compile(fund_expr + r"\s*(?:=|IS)\s*" + rhs, re.I),
        re.compile(rhs.replace("?P<rhs>", "?P<lhs>") + r"\s*(?:=|IS)\s*" + fund_expr, re.I),
    ]

    for idx, pattern in enumerate(patterns):
        for match in pattern.finditer(masked):
            groups = match.groupdict()
            alias = (groups.get("alias1") or groups.get("alias2") or "").lower()
            token_name = "rhs" if idx == 0 else "lhs"
            token = str(groups.get(token_name) or "").strip()
            if not token:
                continue
            other_alias = None
            if re.fullmatch(r"[A-Za-z_]\w*\.fundacion_id", token, re.I):
                other_alias = token.split(".", 1)[0].lower()

            if other_alias:
                if alias and alias in required and other_alias in required:
                    edges.setdefault(alias, set()).add(other_alias)
                    edges.setdefault(other_alias, set()).add(alias)
                continue

            token_position = match.start(token_name)
            value = _bound_value(sql, token, token_position, parameters)
            try:
                is_current = int(value) == int(tenant_id)
            except (TypeError, ValueError):
                is_current = False
            if not is_current:
                raise TenantIsolationError(
                    f"Consulta compleja intentó usar fundacion_id={value!r}; "
                    f"el contexto autenticado es {tenant_id}."
                )
            if alias:
                if alias in required:
                    anchored.add(alias)
            else:
                unqualified_current = True

    if unqualified_current:
        if len(required) == 1:
            anchored.update(required)
        else:
            # Un fundacion_id sin alias solo puede atribuirse con seguridad a
            # una referencia de tabla que tampoco tenga alias explícito.
            candidates = {alias for table, alias in tenant_refs if alias.lower() == table.lower()}
            if len(candidates) == 1:
                anchored.update(a.lower() for a in candidates)

    # Propaga confianza por igualdades alias.fundacion_id = otro.fundacion_id.
    changed = True
    while changed:
        changed = False
        for alias, neighbours in edges.items():
            if alias in anchored:
                for neighbour in neighbours:
                    if neighbour not in anchored:
                        anchored.add(neighbour)
                        changed = True
            elif any(neighbour in anchored for neighbour in neighbours):
                anchored.add(alias)
                changed = True

    missing = sorted(required - anchored)
    return not missing, missing

def global_tenant_access_allowed() -> bool:
    """Indica si la ruta actual puede consultar datos de todas las fundaciones."""
    context = current_tenant_context()
    if context.allow_global and context.role == "SUPERADMIN":
        return True
    if context.role != "SUPERADMIN" or not context.source.startswith("http:"):
        return False
    path = context.source.split(":", 1)[1]
    return any(path.startswith(prefix) for prefix in SUPERADMIN_GLOBAL_PREFIXES)


def rewrite_tenant_sql(
    sql: str,
    parameters: Any,
    table_has_tenant,
) -> str:
    """Reescribe una sentencia SQL usando el contexto de fundación actual.

    ``table_has_tenant`` es un callback que recibe el nombre de tabla. Esto
    permite aplicar la misma barrera tanto a ``sqlite3`` como a SQLAlchemy Core.
    """
    if not isinstance(sql, str) or not strict_tenant_mode():
        return sql
    context = current_tenant_context()
    tenant_id = context.tenant_id
    if not tenant_id or global_tenant_access_allowed():
        return sql
    start = _SQL_START.match(sql)
    if not start:
        return sql
    operation = start.group(1).upper()
    if operation == "REPLACE":
        operation = "INSERT"

    if operation == "INSERT":
        parsed = _parse_insert(sql)
        if not parsed:
            m = re.search(r"\bINTO\s+" + _IDENTIFIER, _mask_sql(sql), re.I)
            table = next((g for g in m.groups()[:4] if g), "").lower() if m else ""
            # Los catálogos compartidos usan INSERT ... SELECT idempotente. Se
            # permiten porque sus filas globales son deliberadas y no contienen
            # información personal de una fundación.
            if table in SHARED_OR_TENANT_TABLES:
                return sql
            if table and table_has_tenant(table):
                raise TenantIsolationError(
                    f"INSERT no compatible con aislamiento automático en {table}; declare columnas y VALUES."
                )
            return sql
        table, columns, _co, col_close, _vo, val_close = parsed
        if not table_has_tenant(table):
            return sql
        if table in SHARED_OR_TENANT_TABLES and "fundacion_id" not in columns:
            # Inserción de catálogo global intencional. Las sobreescrituras por
            # fundación deben declarar fundacion_id de forma explícita.
            return sql
        if "fundacion_id" in columns:
            _validate_insert_tenant(sql, parameters, columns, parsed[4], parsed[5], int(tenant_id))
            return sql
        # Se usa un literal entero derivado del contexto autenticado; no altera
        # el orden de parámetros ya existentes.
        return (
            sql[:col_close].rstrip()
            + ", fundacion_id"
            + sql[col_close:val_close].rstrip()
            + f", {int(tenant_id)}"
            + sql[val_close:]
        )

    simple = _find_simple_table(sql, operation)
    masked = _mask_sql(sql)
    depth = _depth_map(masked)
    tenant_refs: list[tuple[str, str]] = []
    keywords = ("FROM", "JOIN") if operation == "SELECT" else (("UPDATE",) if operation == "UPDATE" else ("FROM",))
    for keyword in keywords:
        pattern = re.compile(r"\b" + keyword + r"\s+" + _IDENTIFIER + r"(?:\s+(?:AS\s+)?([A-Za-z_]\w*))?", re.I)
        for m in pattern.finditer(masked):
            table = next((g for g in m.groups()[:4] if g), "").lower()
            alias = m.groups()[4] if len(m.groups()) > 4 else None
            alias = (
                alias
                if alias and alias.upper() not in {
                    "WHERE", "JOIN", "LEFT", "RIGHT", "INNER", "OUTER", "CROSS",
                    "ON", "ORDER", "GROUP", "LIMIT", "OFFSET", "RETURNING", "SET",
                }
                else table
            )
            if table_has_tenant(table):
                tenant_refs.append((table, alias or table))
    if not tenant_refs:
        return sql

    complex_query = (
        simple is None
        or (
            operation == "SELECT"
            and (
                _contains_nested_select(masked, depth)
                or bool(re.search(r"\bJOIN\b|\bUNION\b|\bINTERSECT\b|\bEXCEPT\b", masked, re.I))
            )
        )
    )
    if complex_query:
        safe, missing = _complex_scope_is_safe(
            sql, parameters, tenant_refs, int(tenant_id)
        )
        if not safe:
            raise TenantIsolationError(
                "Consulta multi-tabla sin aislamiento verificable para: "
                + ", ".join(missing)
            )
        return sql

    table, alias = simple
    if not table_has_tenant(table):
        return sql
    qualified = alias if re.fullmatch(r"[A-Za-z_]\w*", alias) else table
    if table in SHARED_OR_TENANT_TABLES:
        condition = f"({qualified}.fundacion_id IS NULL OR {qualified}.fundacion_id = {int(tenant_id)})"
    else:
        condition = f"COALESCE({qualified}.fundacion_id, 1) = {int(tenant_id)}"
    return _append_predicate(sql, condition, operation)


class TenantCursor(sqlite3.Cursor):
    def execute(self, sql: str, parameters: Any = ()):
        rewritten = self.connection._tenant_rewrite(sql, parameters, many=False)  # type: ignore[attr-defined]
        return super().execute(rewritten, parameters)

    def executemany(self, sql: str, seq_of_parameters: Iterable[Any]):
        params = list(seq_of_parameters)
        sample = params[0] if params else ()
        rewritten = self.connection._tenant_rewrite(sql, sample, many=True)  # type: ignore[attr-defined]
        if "fundacion_id" in sql.lower() and params:
            # Valida cada lote cuando la columna viene explícita.
            for item in params:
                self.connection._tenant_rewrite(sql, item, many=True)  # type: ignore[attr-defined]
        return super().executemany(rewritten, params)


class TenantConnection(sqlite3.Connection):
    _tenant_schema_cache: dict[str, bool] | None = None

    def cursor(self, factory=None):
        return super().cursor(factory or TenantCursor)

    def execute(self, sql: str, parameters: Any = ()):
        return self.cursor().execute(sql, parameters)

    def executemany(self, sql: str, seq_of_parameters: Iterable[Any]):
        return self.cursor().executemany(sql, seq_of_parameters)

    def executescript(self, sql_script: str):
        # Los módulos pueden ejecutar DDL idempotente dentro de una petición.
        # Cualquier script con SELECT/INSERT/UPDATE/DELETE sigue bloqueado para
        # que ``executescript`` no se convierta en un bypass del aislamiento.
        context = current_tenant_context()
        if (
            strict_tenant_mode()
            and context.tenant_id
            and not context.allow_global
            and not tenant_script_is_schema_only(sql_script)
        ):
            raise TenantIsolationError(
                "executescript con DML no está permitido dentro de una operación multi-fundación."
            )
        self._tenant_schema_cache = None
        return super().executescript(sql_script)

    def _table_has_tenant(self, table: str) -> bool:
        table = table.lower()
        if table in CONTROL_TABLES:
            return False
        if self._tenant_schema_cache is None:
            self._tenant_schema_cache = {}
        if table in self._tenant_schema_cache:
            return self._tenant_schema_cache[table]
        if not re.fullmatch(r"[a-zA-Z_]\w*", table):
            self._tenant_schema_cache[table] = False
            return False
        try:
            rows = sqlite3.Connection.execute(self, f'PRAGMA table_info("{table}")').fetchall()
            has_column = any(str(row[1]).lower() == "fundacion_id" for row in rows)
        except Exception:
            has_column = False
        self._tenant_schema_cache[table] = has_column
        return has_column

    def _global_allowed(self) -> bool:
        return global_tenant_access_allowed()

    def _tenant_rewrite(self, sql: str, parameters: Any, many: bool = False) -> str:
        rewritten = rewrite_tenant_sql(sql, parameters, self._table_has_tenant)
        if isinstance(sql, str) and re.match(
            r"^\s*(CREATE|ALTER|DROP|PRAGMA|BEGIN|COMMIT|ROLLBACK|SAVEPOINT|RELEASE|VACUUM|ANALYZE)\b",
            sql,
            re.I,
        ):
            self._tenant_schema_cache = None
        return rewritten


def guarded_connect(*args, **kwargs):
    factory = kwargs.get("factory")
    if factory is not None and factory is not sqlite3.Connection:
        return _ORIGINAL_CONNECT(*args, **kwargs)
    kwargs["factory"] = TenantConnection
    return _ORIGINAL_CONNECT(*args, **kwargs)


def install_sqlite_tenant_guard() -> None:
    global _INSTALLED
    with _INSTALL_LOCK:
        if _INSTALLED:
            return
        sqlite3.connect = guarded_connect  # type: ignore[assignment]
        _INSTALLED = True


def uninstall_sqlite_tenant_guard() -> None:
    global _INSTALLED
    with _INSTALL_LOCK:
        if not _INSTALLED:
            return
        sqlite3.connect = _ORIGINAL_CONNECT  # type: ignore[assignment]
        _INSTALLED = False
