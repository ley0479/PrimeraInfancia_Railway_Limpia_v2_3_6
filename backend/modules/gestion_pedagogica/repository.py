"""
Acceso a datos para Gestión Pedagógica.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from typing import Any, Iterable

from modules.seguridad.tenant_context import current_tenant_context

from .schema import SCHEMA_SQL, DEFAULT_ENTREGABLES


def now_iso() -> str:
    return datetime.now().isoformat(timespec='seconds')


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row is not None else None


def _security_context() -> dict:
    try:
        from modules.seguridad.services import get_request_user_context
        return get_request_user_context()
    except Exception:
        return {'fundacion_id': 1, 'usuario_id': None, 'rol': 'SUPERADMIN', 'username': 'sistema'}


def _is_superadmin() -> bool:
    return _security_context().get('rol') == 'SUPERADMIN'


def _allow_global() -> bool:
    context = current_tenant_context()
    return context.role == 'SUPERADMIN' and bool(context.allow_global)


def _tenant_id() -> int:
    try:
        return int(_security_context().get('fundacion_id') or 1)
    except Exception:
        return 1


def _scope_rows(rows: list[dict]) -> list[dict]:
    if _allow_global():
        return rows
    fid = _security_context().get('fundacion_id') or 1
    return [row for row in rows if row.get('fundacion_id') in (fid, None, '')]


def _tag_inserted_row(cursor, table: str, row_id: int) -> None:
    if not row_id or not table.startswith(('gp_', 'sn_')):
        return
    ctx = _security_context()
    try:
        cols = {r['name'] for r in cursor.execute(f"PRAGMA table_info({table})").fetchall()}
        updates = []
        params = []
        if 'fundacion_id' in cols:
            updates.append('fundacion_id = COALESCE(fundacion_id, ?)')
            params.append(ctx.get('fundacion_id') or 1)
        if 'usuario_creador_id' in cols:
            updates.append('usuario_creador_id = COALESCE(usuario_creador_id, ?)')
            params.append(ctx.get('usuario_id'))
        if 'fecha_actualizacion' in cols:
            updates.append('fecha_actualizacion = COALESCE(fecha_actualizacion, ?)')
            params.append(datetime.now().isoformat(timespec='seconds'))
        if updates:
            params.append(row_id)
            cursor.execute(f"UPDATE {table} SET {', '.join(updates)} WHERE id = ?", tuple(params))
    except Exception:
        pass


class GestionPedagogicaRepository:
    def __init__(self, database_path: str):
        self.database_path = database_path

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.database_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_schema(self) -> None:
        conn = self.connect()
        cursor = conn.cursor()
        cursor.executescript(SCHEMA_SQL)
        for tipo, categoria, dias_limite, prioridad in DEFAULT_ENTREGABLES:
            cursor.execute(
                """
                INSERT INTO gp_configuracion_entregables
                (tipo, categoria, dias_limite, prioridad, activo, fecha_creacion)
                SELECT ?, ?, ?, ?, 1, ?
                WHERE NOT EXISTS (SELECT 1 FROM gp_configuracion_entregables WHERE tipo = ?)
                """,
                (tipo, categoria, dias_limite, prioridad, now_iso(), tipo),
            )
        # Compatibilidad incremental para instalaciones que ya tenían tablas gp_*.
        def ensure_column(table, column, definition):
            cols = {row['name'] for row in cursor.execute(f"PRAGMA table_info({table})").fetchall()}
            if column not in cols:
                cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

        ensure_column('gp_planeaciones', 'ruta_archivo', 'TEXT')
        conn.commit()
        conn.close()

    def fetch_all(self, sql: str, params: Iterable[Any] = ()) -> list[dict[str, Any]]:
        conn = self.connect()
        rows = conn.execute(sql, tuple(params)).fetchall()
        conn.close()
        return _scope_rows([dict(row) for row in rows])

    def fetch_one(self, sql: str, params: Iterable[Any] = ()) -> dict[str, Any] | None:
        rows = self.fetch_all(sql, params)
        return rows[0] if rows else None

    def execute(self, sql: str, params: Iterable[Any] = ()) -> int:
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute(sql, tuple(params))
        last_id = int(cursor.lastrowid or 0)
        match = __import__('re').search(r'INSERT\s+INTO\s+([a-zA-Z0-9_]+)', sql, __import__('re').I)
        if match:
            _tag_inserted_row(cursor, match.group(1), last_id)
        conn.commit()
        conn.close()
        return int(last_id or 0)

    def execute_many(self, sql: str, rows: list[Iterable[Any]]) -> None:
        conn = self.connect()
        conn.executemany(sql, rows)
        conn.commit()
        conn.close()

    def log(self, accion: str, entidad_tipo: str = '', entidad_id: int | None = None,
            usuario: str = 'sistema', anteriores: Any = None, nuevos: Any = None) -> None:
        self.execute(
            """
            INSERT INTO gp_historial_acciones
            (usuario, accion, entidad_tipo, entidad_id, datos_anteriores, datos_nuevos, fecha_accion)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                usuario,
                accion,
                entidad_tipo,
                entidad_id,
                json.dumps(anteriores, ensure_ascii=False) if anteriores is not None else None,
                json.dumps(nuevos, ensure_ascii=False) if nuevos is not None else None,
                now_iso(),
            ),
        )

    # Coordinadores
    def listar_coordinadores(self, incluir_inactivos: bool = False) -> list[dict[str, Any]]:
        where = "" if incluir_inactivos else "WHERE activo = 1"
        return self.fetch_all(
            f"""
            SELECT *
            FROM gp_coordinadores
            {where}
            ORDER BY activo DESC, nombre
            """
        )

    def obtener_coordinador(self, coordinador_id: int) -> dict[str, Any] | None:
        return self.fetch_one("SELECT * FROM gp_coordinadores WHERE id = ?", (coordinador_id,))

    def crear_coordinador(self, data: dict[str, Any]) -> dict[str, Any]:
        unidades = data.get('unidades') or data.get('unidades_json') or []
        if isinstance(unidades, str):
            unidades_json = unidades
        else:
            unidades_json = json.dumps(unidades, ensure_ascii=False)

        now = now_iso()
        new_id = self.execute(
            """
            INSERT INTO gp_coordinadores
            (contrato_id, contrato, nombre, documento, telefono, email, cargo, zona,
             unidades_json, observaciones, activo, fecha_creacion, fecha_actualizacion)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
            """,
            (
                data.get('contrato_id'),
                data.get('contrato', ''),
                data.get('nombre', '').strip(),
                data.get('documento', '').strip(),
                data.get('telefono', '').strip(),
                data.get('email', '').strip(),
                data.get('cargo', 'COORDINADOR').strip() or 'COORDINADOR',
                data.get('zona', '').strip(),
                unidades_json,
                data.get('observaciones', '').strip(),
                now,
                now,
            ),
        )
        self.log('CREAR_COORDINADOR', 'gp_coordinadores', new_id, nuevos=data)
        return self.obtener_coordinador(new_id) or {}

    def actualizar_coordinador(self, coordinador_id: int, data: dict[str, Any]) -> dict[str, Any] | None:
        anterior = self.obtener_coordinador(coordinador_id)
        if not anterior:
            return None
        unidades = data.get('unidades', data.get('unidades_json', anterior.get('unidades_json') or '[]'))
        unidades_json = unidades if isinstance(unidades, str) else json.dumps(unidades, ensure_ascii=False)
        now = now_iso()
        self.execute(
            """
            UPDATE gp_coordinadores
            SET contrato_id = ?, contrato = ?, nombre = ?, documento = ?, telefono = ?,
                email = ?, cargo = ?, zona = ?, unidades_json = ?, observaciones = ?,
                activo = ?, fecha_actualizacion = ?
            WHERE id = ?
            """,
            (
                data.get('contrato_id', anterior.get('contrato_id')),
                data.get('contrato', anterior.get('contrato', '')),
                data.get('nombre', anterior.get('nombre', '')).strip(),
                data.get('documento', anterior.get('documento', '')).strip(),
                data.get('telefono', anterior.get('telefono', '')).strip(),
                data.get('email', anterior.get('email', '')).strip(),
                data.get('cargo', anterior.get('cargo', 'COORDINADOR')).strip() or 'COORDINADOR',
                data.get('zona', anterior.get('zona', '')).strip(),
                unidades_json,
                data.get('observaciones', anterior.get('observaciones', '')).strip(),
                int(data.get('activo', anterior.get('activo', 1))),
                now,
                coordinador_id,
            ),
        )
        actualizado = self.obtener_coordinador(coordinador_id)
        self.log('ACTUALIZAR_COORDINADOR', 'gp_coordinadores', coordinador_id, anteriores=anterior, nuevos=actualizado)
        return actualizado

    def desactivar_coordinador(self, coordinador_id: int) -> bool:
        anterior = self.obtener_coordinador(coordinador_id)
        if not anterior:
            return False
        self.execute("UPDATE gp_coordinadores SET activo = 0, fecha_actualizacion = ? WHERE id = ?", (now_iso(), coordinador_id))
        self.log('DESACTIVAR_COORDINADOR', 'gp_coordinadores', coordinador_id, anteriores=anterior)
        return True

    # Equipos interdisciplinarios
    def listar_equipos(self, coordinador_id: int | None = None) -> list[dict[str, Any]]:
        params: tuple[Any, ...] = ()
        where = "WHERE e.activo = 1"
        if coordinador_id:
            where += " AND e.coordinador_id = ?"
            params = (coordinador_id,)
        fid = _tenant_id()
        where += f" AND COALESCE(e.fundacion_id, 1)={fid}"
        return self.fetch_all(
            f"""
            SELECT e.*, c.nombre AS coordinador_nombre
            FROM gp_equipos_interdisciplinarios e
            LEFT JOIN gp_coordinadores c
              ON c.id = e.coordinador_id AND COALESCE(c.fundacion_id, 1)={fid}
            {where}
            ORDER BY c.nombre, e.rol, e.nombre
            """,
            params,
        )

    def crear_equipo(self, data: dict[str, Any]) -> dict[str, Any]:
        now = now_iso()
        new_id = self.execute(
            """
            INSERT INTO gp_equipos_interdisciplinarios
            (coordinador_id, nombre, documento, rol, profesion, telefono, email, activo, fecha_creacion, fecha_actualizacion)
            VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
            """,
            (
                data.get('coordinador_id'),
                data.get('nombre', '').strip(),
                data.get('documento', '').strip(),
                data.get('rol', '').strip() or 'Equipo',
                data.get('profesion', '').strip(),
                data.get('telefono', '').strip(),
                data.get('email', '').strip(),
                now,
                now,
            ),
        )
        self.log('CREAR_MIEMBRO_EQUIPO', 'gp_equipos_interdisciplinarios', new_id, nuevos=data)
        return self.fetch_one("SELECT * FROM gp_equipos_interdisciplinarios WHERE id = ?", (new_id,)) or {}

    def actualizar_equipo(self, equipo_id: int, data: dict[str, Any]) -> dict[str, Any] | None:
        anterior = self.fetch_one("SELECT * FROM gp_equipos_interdisciplinarios WHERE id = ?", (equipo_id,))
        if not anterior:
            return None
        self.execute(
            """
            UPDATE gp_equipos_interdisciplinarios
            SET coordinador_id = ?, nombre = ?, documento = ?, rol = ?, profesion = ?,
                telefono = ?, email = ?, activo = ?, fecha_actualizacion = ?
            WHERE id = ?
            """,
            (
                data.get('coordinador_id', anterior.get('coordinador_id')),
                data.get('nombre', anterior.get('nombre', '')).strip(),
                data.get('documento', anterior.get('documento', '')).strip(),
                data.get('rol', anterior.get('rol', '')).strip(),
                data.get('profesion', anterior.get('profesion', '')).strip(),
                data.get('telefono', anterior.get('telefono', '')).strip(),
                data.get('email', anterior.get('email', '')).strip(),
                int(data.get('activo', anterior.get('activo', 1))),
                now_iso(),
                equipo_id,
            ),
        )
        actualizado = self.fetch_one("SELECT * FROM gp_equipos_interdisciplinarios WHERE id = ?", (equipo_id,))
        self.log('ACTUALIZAR_MIEMBRO_EQUIPO', 'gp_equipos_interdisciplinarios', equipo_id, anteriores=anterior, nuevos=actualizado)
        return actualizado

    def desactivar_equipo(self, equipo_id: int) -> bool:
        anterior = self.fetch_one("SELECT * FROM gp_equipos_interdisciplinarios WHERE id = ?", (equipo_id,))
        if not anterior:
            return False
        self.execute("UPDATE gp_equipos_interdisciplinarios SET activo = 0, fecha_actualizacion = ? WHERE id = ?", (now_iso(), equipo_id))
        self.log('DESACTIVAR_MIEMBRO_EQUIPO', 'gp_equipos_interdisciplinarios', equipo_id, anteriores=anterior)
        return True

    # Docentes
    def listar_docentes(self, coordinador_id: int | None = None) -> list[dict[str, Any]]:
        where = "WHERE d.activo = 1"
        params: tuple[Any, ...] = ()
        if coordinador_id:
            where += " AND d.coordinador_id = ?"
            params = (coordinador_id,)
        fid = _tenant_id()
        where += f" AND COALESCE(d.fundacion_id, 1)={fid}"
        return self.fetch_all(
            f"""
            SELECT d.*, c.nombre AS coordinador_nombre
            FROM gp_docentes d
            LEFT JOIN gp_coordinadores c
              ON c.id = d.coordinador_id AND COALESCE(c.fundacion_id, 1)={fid}
            {where}
            ORDER BY c.nombre, d.unidad, d.nombre
            """,
            params,
        )

    def crear_docente(self, data: dict[str, Any]) -> dict[str, Any]:
        now = now_iso()
        new_id = self.execute(
            """
            INSERT INTO gp_docentes
            (coordinador_id, nombre, documento, unidad, telefono, email, cargo, activo, fecha_creacion, fecha_actualizacion)
            VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
            """,
            (
                data.get('coordinador_id'),
                data.get('nombre', '').strip(),
                data.get('documento', '').strip(),
                data.get('unidad', '').strip(),
                data.get('telefono', '').strip(),
                data.get('email', '').strip(),
                data.get('cargo', 'DOCENTE').strip() or 'DOCENTE',
                now,
                now,
            ),
        )
        self.log('CREAR_DOCENTE', 'gp_docentes', new_id, nuevos=data)
        return self.fetch_one("SELECT * FROM gp_docentes WHERE id = ?", (new_id,)) or {}

    def actualizar_docente(self, docente_id: int, data: dict[str, Any]) -> dict[str, Any] | None:
        anterior = self.fetch_one("SELECT * FROM gp_docentes WHERE id = ?", (docente_id,))
        if not anterior:
            return None
        self.execute(
            """
            UPDATE gp_docentes
            SET coordinador_id = ?, nombre = ?, documento = ?, unidad = ?, telefono = ?,
                email = ?, cargo = ?, activo = ?, fecha_actualizacion = ?
            WHERE id = ?
            """,
            (
                data.get('coordinador_id', anterior.get('coordinador_id')),
                data.get('nombre', anterior.get('nombre', '')).strip(),
                data.get('documento', anterior.get('documento', '')).strip(),
                data.get('unidad', anterior.get('unidad', '')).strip(),
                data.get('telefono', anterior.get('telefono', '')).strip(),
                data.get('email', anterior.get('email', '')).strip(),
                data.get('cargo', anterior.get('cargo', 'DOCENTE')).strip(),
                int(data.get('activo', anterior.get('activo', 1))),
                now_iso(),
                docente_id,
            ),
        )
        actualizado = self.fetch_one("SELECT * FROM gp_docentes WHERE id = ?", (docente_id,))
        self.log('ACTUALIZAR_DOCENTE', 'gp_docentes', docente_id, anteriores=anterior, nuevos=actualizado)
        return actualizado

    def desactivar_docente(self, docente_id: int) -> bool:
        anterior = self.fetch_one("SELECT * FROM gp_docentes WHERE id = ?", (docente_id,))
        if not anterior:
            return False
        self.execute("UPDATE gp_docentes SET activo = 0, fecha_actualizacion = ? WHERE id = ?", (now_iso(), docente_id))
        self.log('DESACTIVAR_DOCENTE', 'gp_docentes', docente_id, anteriores=anterior)
        return True

    # Entregables
    def listar_entregables(self, periodo: str | None = None, coordinador_id: int | None = None,
                           estado: str | None = None) -> list[dict[str, Any]]:
        where = ["e.activo = 1"]
        params: list[Any] = []
        if periodo:
            where.append("e.periodo = ?")
            params.append(periodo)
        if coordinador_id:
            where.append("e.coordinador_id = ?")
            params.append(coordinador_id)
        if estado:
            where.append("e.estado = ?")
            params.append(estado)
        fid = _tenant_id()
        where.append(f"COALESCE(e.fundacion_id, 1)={fid}")
        return self.fetch_all(
            f"""
            SELECT e.*, c.nombre AS coordinador_nombre, d.nombre_original AS documento_nombre
            FROM gp_entregables e
            LEFT JOIN gp_coordinadores c
              ON c.id = e.coordinador_id AND COALESCE(c.fundacion_id, 1)={fid}
            LEFT JOIN gp_documentos d
              ON d.id = e.documento_id AND COALESCE(d.fundacion_id, 1)={fid}
            WHERE {' AND '.join(where)}
            ORDER BY e.fecha_limite, e.prioridad DESC, e.tipo
            """,
            params,
        )

    def obtener_entregable(self, entregable_id: int) -> dict[str, Any] | None:
        return self.fetch_one("SELECT * FROM gp_entregables WHERE id = ?", (entregable_id,))

    def crear_entregable(self, data: dict[str, Any]) -> dict[str, Any]:
        now = now_iso()
        new_id = self.execute(
            """
            INSERT INTO gp_entregables
            (coordinador_id, unidad, tipo, titulo, descripcion, periodo, fecha_limite,
             prioridad, estado, responsable, observaciones, activo, fecha_creacion, fecha_actualizacion)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
            """,
            (
                data.get('coordinador_id'),
                data.get('unidad', '').strip(),
                data.get('tipo', 'Entregable').strip() or 'Entregable',
                data.get('titulo', data.get('tipo', 'Entregable')).strip(),
                data.get('descripcion', '').strip(),
                data.get('periodo', datetime.now().strftime('%Y-%m')),
                data.get('fecha_limite', '').strip(),
                data.get('prioridad', 'media').strip() or 'media',
                data.get('estado', 'Pendiente').strip() or 'Pendiente',
                data.get('responsable', '').strip(),
                data.get('observaciones', '').strip(),
                now,
                now,
            ),
        )
        self.log('CREAR_ENTREGABLE', 'gp_entregables', new_id, nuevos=data)
        return self.obtener_entregable(new_id) or {}

    def actualizar_entregable(self, entregable_id: int, data: dict[str, Any]) -> dict[str, Any] | None:
        anterior = self.obtener_entregable(entregable_id)
        if not anterior:
            return None
        self.execute(
            """
            UPDATE gp_entregables
            SET coordinador_id = ?, unidad = ?, tipo = ?, titulo = ?, descripcion = ?,
                periodo = ?, fecha_limite = ?, prioridad = ?, estado = ?, responsable = ?,
                observaciones = ?, fecha_actualizacion = ?, fecha_carga = ?
            WHERE id = ?
            """,
            (
                data.get('coordinador_id', anterior.get('coordinador_id')),
                data.get('unidad', anterior.get('unidad', '')).strip(),
                data.get('tipo', anterior.get('tipo', '')).strip(),
                data.get('titulo', anterior.get('titulo', '')).strip(),
                data.get('descripcion', anterior.get('descripcion', '')).strip(),
                data.get('periodo', anterior.get('periodo', '')).strip(),
                data.get('fecha_limite', anterior.get('fecha_limite', '')).strip(),
                data.get('prioridad', anterior.get('prioridad', 'media')).strip(),
                data.get('estado', anterior.get('estado', 'Pendiente')).strip(),
                data.get('responsable', anterior.get('responsable', '')).strip(),
                data.get('observaciones', anterior.get('observaciones', '')).strip(),
                now_iso(),
                data.get('fecha_carga', anterior.get('fecha_carga')),
                entregable_id,
            ),
        )
        actualizado = self.obtener_entregable(entregable_id)
        self.log('ACTUALIZAR_ENTREGABLE', 'gp_entregables', entregable_id, anteriores=anterior, nuevos=actualizado)
        return actualizado

    def desactivar_entregable(self, entregable_id: int) -> bool:
        anterior = self.obtener_entregable(entregable_id)
        if not anterior:
            return False
        self.execute("UPDATE gp_entregables SET activo = 0, fecha_actualizacion = ? WHERE id = ?", (now_iso(), entregable_id))
        self.log('DESACTIVAR_ENTREGABLE', 'gp_entregables', entregable_id, anteriores=anterior)
        return True
