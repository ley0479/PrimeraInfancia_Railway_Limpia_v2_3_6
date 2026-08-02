from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime
from typing import Any, Iterable

from .schema import SCHEMA_SQL, TIPOS_ACTIVIDAD_DEFAULT


def now_iso() -> str:
    return datetime.now().isoformat(timespec='seconds')


def _ctx() -> dict[str, Any]:
    try:
        from modules.seguridad.services import get_request_user_context
        return get_request_user_context()
    except Exception:
        return {'fundacion_id': 1, 'usuario_id': None, 'rol': 'SUPERADMIN', 'username': 'sistema'}


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row is not None else None


class PlaneacionRepository:
    def __init__(self, database_path: str):
        self.database_path = database_path

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.database_path)
        conn.row_factory = sqlite3.Row
        return conn

    def context(self) -> dict[str, Any]:
        return _ctx()

    def init_schema(self) -> None:
        conn = self.connect()
        cur = conn.cursor()
        cur.executescript(SCHEMA_SQL)
        for codigo, nombre in TIPOS_ACTIVIDAD_DEFAULT:
            cur.execute(
                """
                INSERT INTO pp_tipos_actividad (codigo, nombre, descripcion, activo, fecha_creacion)
                SELECT ?, ?, ?, 1, ?
                WHERE NOT EXISTS (SELECT 1 FROM pp_tipos_actividad WHERE codigo = ?)
                """,
                (codigo, nombre, nombre, now_iso(), codigo),
            )
        self._ensure_compatibility(cur)
        conn.commit()
        conn.close()

    def _table_exists(self, cur: sqlite3.Cursor, table: str) -> bool:
        return cur.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone() is not None

    def _cols(self, cur: sqlite3.Cursor, table: str) -> set[str]:
        if not self._table_exists(cur, table):
            return set()
        return {row['name'] for row in cur.execute(f"PRAGMA table_info({table})").fetchall()}

    def _ensure_column(self, cur: sqlite3.Cursor, table: str, column: str, definition: str) -> None:
        if self._table_exists(cur, table) and column not in self._cols(cur, table):
            cur.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    def _ensure_compatibility(self, cur: sqlite3.Cursor) -> None:
        # Asegura columnas mínimas en tablas de calendario/entregables ya creadas por fases previas.
        for table in ['gp_calendario_eventos', 'gp_entregables', 'gp_documentos']:
            if not self._table_exists(cur, table):
                continue
            for col, definition in {
                'fundacion_id': 'INTEGER',
                'usuario_creador_id': 'INTEGER',
                'fecha_actualizacion': 'TEXT',
            }.items():
                self._ensure_column(cur, table, col, definition)
        if self._table_exists(cur, 'gp_calendario_eventos'):
            for col, definition in {
                'unidad': 'TEXT',
                'docente_id': 'INTEGER',
                'docente_nombre': 'TEXT',
                'responsable': 'TEXT',
                'prioridad': "TEXT DEFAULT 'MEDIA'",
                'evidencia_requerida': 'INTEGER DEFAULT 0',
                'fecha_cumplimiento': 'TEXT',
            }.items():
                self._ensure_column(cur, 'gp_calendario_eventos', col, definition)

    def _tag_insert(self, cur: sqlite3.Cursor, sql: str, row_id: int) -> None:
        if not row_id:
            return
        match = re.search(r'INSERT\s+INTO\s+([a-zA-Z0-9_]+)', sql, re.I)
        if not match:
            return
        table = match.group(1)
        if not table.startswith(('pp_', 'gp_')):
            return
        try:
            cols = self._cols(cur, table)
            ctx = self.context()
            updates: list[str] = []
            params: list[Any] = []
            if 'fundacion_id' in cols:
                updates.append('fundacion_id = COALESCE(fundacion_id, ?)')
                params.append(ctx.get('fundacion_id') or 1)
            if 'usuario_creador_id' in cols:
                updates.append('usuario_creador_id = COALESCE(usuario_creador_id, ?)')
                params.append(ctx.get('usuario_id'))
            if 'fecha_actualizacion' in cols:
                updates.append('fecha_actualizacion = COALESCE(fecha_actualizacion, ?)')
                params.append(now_iso())
            if updates:
                params.append(row_id)
                cur.execute(f"UPDATE {table} SET {', '.join(updates)} WHERE id=?", tuple(params))
        except Exception:
            pass

    def fetch_all(self, sql: str, params: Iterable[Any] = ()) -> list[dict[str, Any]]:
        conn = self.connect()
        rows = [dict(row) for row in conn.execute(sql, tuple(params)).fetchall()]
        conn.close()
        return self._scope(rows)

    def fetch_one(self, sql: str, params: Iterable[Any] = ()) -> dict[str, Any] | None:
        rows = self.fetch_all(sql, params)
        return rows[0] if rows else None

    def execute(self, sql: str, params: Iterable[Any] = ()) -> int:
        conn = self.connect()
        cur = conn.cursor()
        cur.execute(sql, tuple(params))
        last_id = int(cur.lastrowid or 0)
        self._tag_insert(cur, sql, last_id)
        conn.commit()
        conn.close()
        return last_id

    def execute_update(self, sql: str, params: Iterable[Any] = ()) -> int:
        conn = self.connect()
        cur = conn.cursor()
        cur.execute(sql, tuple(params))
        count = cur.rowcount
        conn.commit()
        conn.close()
        return count

    def _scope(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        ctx = self.context()
        if ctx.get('rol') == 'SUPERADMIN':
            return rows
        fid = ctx.get('fundacion_id') or 1
        scoped = []
        for row in rows:
            if 'fundacion_id' not in row or row.get('fundacion_id') in (None, '', fid):
                scoped.append(row)
        return scoped

    def scope_clause(self, alias: str = '') -> tuple[str, list[Any]]:
        ctx = self.context()
        if ctx.get('rol') == 'SUPERADMIN':
            return '1=1', []
        field = f'{alias}.fundacion_id' if alias else 'fundacion_id'
        return f'({field} = ? OR {field} IS NULL)', [ctx.get('fundacion_id') or 1]

    def coordinator_filter_clause(self, alias: str = 'p') -> tuple[str, list[Any]]:
        ctx = self.context()
        base, params = self.scope_clause(alias)
        if ctx.get('rol') == 'COORDINADOR':
            coord = self.current_coordinator_id()
            if not coord:
                return '1=0', []
            return f'{base} AND {alias}.coordinador_id = ?', params + [coord]
        if ctx.get('rol') == 'DOCENTE':
            docente = self.current_docente_id()
            if not docente:
                return f'{base}', params
            return f'{base} AND ({alias}.docente_id = ? OR {alias}.docente_id IS NULL)', params + [docente]
        return base, params

    def current_coordinator_id(self) -> int | None:
        ctx = self.context()
        uid = ctx.get('usuario_id')
        email = (ctx.get('email') or '').lower()
        username = (ctx.get('username') or '').lower()
        nombre = (ctx.get('nombre_completo') or '').lower()
        fid = ctx.get('fundacion_id') or 1
        row = self.fetch_one(
            """
            SELECT id FROM gp_coordinadores
            WHERE activo = 1 AND (fundacion_id=? OR fundacion_id IS NULL)
              AND (usuario_id=? OR lower(COALESCE(email,''))=? OR lower(COALESCE(documento,''))=? OR lower(COALESCE(nombre,''))=?)
            ORDER BY id LIMIT 1
            """,
            (fid, uid, email, username, nombre),
        )
        return int(row['id']) if row else None

    def current_docente_id(self) -> int | None:
        ctx = self.context()
        uid = ctx.get('usuario_id')
        email = (ctx.get('email') or '').lower()
        username = (ctx.get('username') or '').lower()
        nombre = (ctx.get('nombre_completo') or '').lower()
        fid = ctx.get('fundacion_id') or 1
        row = self.fetch_one(
            """
            SELECT id FROM gp_docentes
            WHERE activo = 1 AND (fundacion_id=? OR fundacion_id IS NULL)
              AND (usuario_id=? OR lower(COALESCE(email,''))=? OR lower(COALESCE(documento,''))=? OR lower(COALESCE(nombre,''))=?)
            ORDER BY id LIMIT 1
            """,
            (fid, uid, email, username, nombre),
        )
        return int(row['id']) if row else None

    def log(self, accion: str, entidad_tipo: str, entidad_id: int | None = None, anteriores: Any = None, nuevos: Any = None, planeacion_id: int | None = None) -> None:
        ctx = self.context()
        self.execute(
            """
            INSERT INTO pp_historial_planeacion
            (planeacion_id, entidad_tipo, entidad_id, accion, datos_anteriores, datos_nuevos, usuario, fundacion_id, usuario_creador_id, fecha_accion)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                planeacion_id, entidad_tipo, entidad_id, accion,
                json.dumps(anteriores, ensure_ascii=False) if anteriores is not None else None,
                json.dumps(nuevos, ensure_ascii=False) if nuevos is not None else None,
                ctx.get('username') or 'sistema', ctx.get('fundacion_id') or 1, ctx.get('usuario_id'), now_iso(),
            ),
        )

    def list_coordinadores(self) -> list[dict[str, Any]]:
        clause, params = self.scope_clause('c')
        return self.fetch_all(f"SELECT * FROM gp_coordinadores c WHERE {clause} AND c.activo=1 ORDER BY c.nombre", params)

    def list_docentes(self, coordinador_id: int | None = None) -> list[dict[str, Any]]:
        clause, params = self.scope_clause('d')
        if coordinador_id:
            clause += ' AND d.coordinador_id=?'
            params.append(coordinador_id)
        return self.fetch_all(f"SELECT * FROM gp_docentes d WHERE {clause} AND d.activo=1 ORDER BY d.nombre", params)

    def list_planeaciones(self, periodo: str | None = None, estado: str | None = None) -> list[dict[str, Any]]:
        clause, params = self.coordinator_filter_clause('p')
        if periodo:
            clause += ' AND p.periodo=?'
            params.append(periodo)
        if estado:
            clause += ' AND p.estado=?'
            params.append(estado)
        return self.fetch_all(
            f"""
            SELECT p.*, c.nombre AS coordinador_nombre, d.nombre AS docente_nombre
            FROM pp_planeaciones p
            LEFT JOIN gp_coordinadores c ON c.id=p.coordinador_id
            LEFT JOIN gp_docentes d ON d.id=p.docente_id
            WHERE {clause} AND p.activo=1
            ORDER BY p.fecha_creacion DESC, p.id DESC
            """,
            params,
        )

    def get_planeacion(self, planeacion_id: int) -> dict[str, Any] | None:
        clause, params = self.coordinator_filter_clause('p')
        row = self.fetch_one(
            f"""
            SELECT p.*, c.nombre AS coordinador_nombre, d.nombre AS docente_nombre
            FROM pp_planeaciones p
            LEFT JOIN gp_coordinadores c ON c.id=p.coordinador_id
            LEFT JOIN gp_docentes d ON d.id=p.docente_id
            WHERE {clause} AND p.id=? AND p.activo=1
            """,
            params + [planeacion_id],
        )
        if not row:
            return None
        row['actividades'] = self.fetch_all('SELECT * FROM pp_actividades WHERE planeacion_id=? AND activo=1 ORDER BY fecha_programada, id', (planeacion_id,))
        row['documentos_generados'] = self.fetch_all('SELECT * FROM pp_documentos_generados WHERE planeacion_id=? ORDER BY fecha_generacion DESC', (planeacion_id,))
        row['evidencias'] = self.fetch_all('SELECT * FROM pp_evidencias_planeacion WHERE planeacion_id=? AND activo=1 ORDER BY fecha_creacion DESC', (planeacion_id,))
        row['aprobaciones'] = self.fetch_all('SELECT * FROM pp_aprobaciones_planeacion WHERE planeacion_id=? ORDER BY fecha_accion DESC', (planeacion_id,))
        row['historial'] = self.fetch_all('SELECT * FROM pp_historial_planeacion WHERE planeacion_id=? ORDER BY fecha_accion DESC LIMIT 100', (planeacion_id,))
        return row

    def list_plantillas(self, tipo_documento: str | None = None) -> list[dict[str, Any]]:
        clause, params = self.scope_clause('t')
        if tipo_documento:
            clause += ' AND t.tipo_documento=?'
            params.append(tipo_documento)
        return self.fetch_all(f"SELECT * FROM pp_plantillas_documento t WHERE {clause} AND t.activo=1 ORDER BY t.tipo_documento, t.nombre", params)

    def dashboard(self, periodo: str) -> dict[str, Any]:
        clause, params = self.coordinator_filter_clause('p')
        rows = self.fetch_all(f"SELECT estado, COUNT(*) total FROM pp_planeaciones p WHERE {clause} AND p.periodo=? AND p.activo=1 GROUP BY estado", params + [periodo])
        estados = {r['estado']: r['total'] for r in rows}
        acts = self.fetch_all(f"SELECT estado, COUNT(*) total FROM pp_actividades a WHERE (a.fundacion_id=? OR a.fundacion_id IS NULL) AND substr(COALESCE(a.fecha_programada,''),1,7)=? AND a.activo=1 GROUP BY estado", ((self.context().get('fundacion_id') or 1), periodo))
        docs = self.fetch_all(f"SELECT tipo_documento, COUNT(*) total FROM pp_documentos_generados d WHERE (d.fundacion_id=? OR d.fundacion_id IS NULL) AND substr(COALESCE(d.fecha_generacion,''),1,7)=? GROUP BY tipo_documento", ((self.context().get('fundacion_id') or 1), periodo))
        fid = self.context().get('fundacion_id') or 1
        pendientes = self.fetch_one(
            """
            SELECT COUNT(*) total
            FROM pp_actividades
            WHERE (fundacion_id=? OR fundacion_id IS NULL)
              AND evidencia_requerida IS NOT NULL AND evidencia_requerida != ''
              AND estado NOT IN ('CUMPLIDO','ANULADO')
            """,
            (fid,),
        ) or {'total': 0}
        return {
            'periodo': periodo,
            'planeaciones_total': sum(estados.values()),
            'estados': estados,
            'actividades': {r['estado']: r['total'] for r in acts},
            'documentos_generados': {r['tipo_documento']: r['total'] for r in docs},
            'pendientes_evidencia': pendientes,
        }
