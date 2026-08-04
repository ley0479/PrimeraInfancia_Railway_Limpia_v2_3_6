from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, date
from typing import Any, Iterable

from flask import g, request

from modules.seguridad.tenant_context import current_tenant_context

from .schema import SCHEMA_SQL, EXISTING_GP_TABLES, MULTITENANT_COLUMNS, CALENDAR_EXTRA_COLUMNS, COORDINADOR_EXTRA_COLUMNS


def now_iso() -> str:
    return datetime.now().isoformat(timespec='seconds')


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row is not None else None


def normalizar_texto(valor: Any) -> str:
    return str(valor or '').strip()


class GestionCoordinadorRepository:
    def __init__(self, database_path: str):
        self.database_path = database_path

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.database_path)
        conn.row_factory = sqlite3.Row
        return conn

    def context(self) -> dict[str, Any]:
        try:
            from modules.seguridad.services import get_request_user_context
            ctx = get_request_user_context()
        except Exception:
            ctx = {}
        user = getattr(g, 'current_user', None) or {}
        ctx.setdefault('usuario_id', user.get('id'))
        ctx.setdefault('fundacion_id', user.get('fundacion_id') or 1)
        ctx.setdefault('rol', user.get('rol') or 'SUPERADMIN')
        ctx.setdefault('username', user.get('username') or 'sistema')
        ctx.setdefault('email', user.get('email') or '')
        ctx.setdefault('nombre_completo', user.get('nombre_completo') or user.get('username') or '')
        return ctx

    def init_schema(self) -> None:
        conn = self.connect()
        cur = conn.cursor()
        cur.executescript(SCHEMA_SQL)

        def table_exists(table: str) -> bool:
            return cur.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone() is not None

        def cols(table: str) -> set[str]:
            if not table_exists(table):
                return set()
            return {row['name'] for row in cur.execute(f"PRAGMA table_info({table})").fetchall()}

        def ensure_column(table: str, column: str, definition: str) -> None:
            if table_exists(table) and column not in cols(table):
                cur.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

        for table in EXISTING_GP_TABLES:
            for column, definition in MULTITENANT_COLUMNS.items():
                ensure_column(table, column, definition)
            if table == 'gp_coordinadores':
                for column, definition in COORDINADOR_EXTRA_COLUMNS.items():
                    ensure_column(table, column, definition)
            if table == 'gp_calendario_eventos':
                for column, definition in CALENDAR_EXTRA_COLUMNS.items():
                    ensure_column(table, column, definition)
            if table == 'gp_docentes':
                ensure_column(table, 'fundacion_id', 'INTEGER')
                ensure_column(table, 'usuario_id', 'INTEGER')
            if table == 'gp_equipos_interdisciplinarios':
                ensure_column(table, 'fundacion_id', 'INTEGER')

        # Etiqueta datos históricos con la fundación principal para que la FASE 1 siga operando.
        for table in EXISTING_GP_TABLES:
            if table_exists(table) and 'fundacion_id' in cols(table):
                try:
                    cur.execute(f"UPDATE {table} SET fundacion_id = 1 WHERE fundacion_id IS NULL")
                except Exception:
                    pass
        conn.commit()
        conn.close()

    def execute(self, sql: str, params: Iterable[Any] = ()) -> int:
        conn = self.connect()
        cur = conn.cursor()
        cur.execute(sql, tuple(params))
        last_id = int(cur.lastrowid or 0)
        self._tag_insert(cur, sql, last_id)
        conn.commit()
        conn.close()
        return last_id

    def _tag_insert(self, cur: sqlite3.Cursor, sql: str, row_id: int) -> None:
        if not row_id:
            return
        import re
        match = re.search(r'INSERT\s+INTO\s+([a-zA-Z0-9_]+)', sql, re.I)
        if not match:
            return
        table = match.group(1)
        try:
            cols = {r['name'] for r in cur.execute(f"PRAGMA table_info({table})").fetchall()}
            updates = []
            params: list[Any] = []
            ctx = self.context()
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
                cur.execute(f"UPDATE {table} SET {', '.join(updates)} WHERE id = ?", params)
        except Exception:
            pass

    def fetch_all(self, sql: str, params: Iterable[Any] = ()) -> list[dict[str, Any]]:
        conn = self.connect()
        rows = [dict(row) for row in conn.execute(sql, tuple(params)).fetchall()]
        conn.close()
        return rows

    def fetch_one(self, sql: str, params: Iterable[Any] = ()) -> dict[str, Any] | None:
        rows = self.fetch_all(sql, params)
        return rows[0] if rows else None

    def fundacion_clause(self, alias: str = '') -> tuple[str, list[Any]]:
        ctx = self.context()
        tenant_context = current_tenant_context()
        if tenant_context.role == 'SUPERADMIN' and tenant_context.allow_global:
            return '1=1', []
        field = f"{alias}.fundacion_id" if alias else 'fundacion_id'
        return f"({field} = ? OR {field} IS NULL)", [ctx.get('fundacion_id') or 1]

    def current_coordinator_id(self) -> int | None:
        ctx = self.context()
        if ctx.get('rol') != 'COORDINADOR':
            return None
        fid = ctx.get('fundacion_id') or 1
        uid = ctx.get('usuario_id')
        email = (ctx.get('email') or '').lower()
        username = (ctx.get('username') or '').lower()
        nombre = (ctx.get('nombre_completo') or '').lower()
        conn = self.connect()
        row = conn.execute(
            """
            SELECT id FROM gp_coordinadores
            WHERE activo = 1 AND (fundacion_id = ? OR fundacion_id IS NULL)
              AND (
                usuario_id = ?
                OR lower(COALESCE(email,'')) = ?
                OR lower(COALESCE(documento,'')) = ?
                OR lower(COALESCE(nombre,'')) = ?
              )
            ORDER BY id LIMIT 1
            """,
            (fid, uid, email, username, nombre),
        ).fetchone()
        conn.close()
        return int(row['id']) if row else None

    def coordinator_scope_clause(self, alias: str = 'c') -> tuple[str, list[Any]]:
        ctx = self.context()
        fund_clause, params = self.fundacion_clause(alias)
        if ctx.get('rol') == 'COORDINADOR':
            cid = self.current_coordinator_id()
            if not cid:
                return '1=0', []
            return f"{fund_clause} AND {alias}.id = ?", params + [cid]
        return fund_clause, params

    def entity_scope_clause(self, alias: str = '', coordinator_field: str = 'coordinador_id') -> tuple[str, list[Any]]:
        ctx = self.context()
        fund_clause, params = self.fundacion_clause(alias)
        if ctx.get('rol') == 'COORDINADOR':
            cid = self.current_coordinator_id()
            if not cid:
                return '1=0', []
            field = f"{alias}.{coordinator_field}" if alias else coordinator_field
            return f"{fund_clause} AND {field} = ?", params + [cid]
        return fund_clause, params

    def log(self, accion: str, entidad_tipo: str, entidad_id: int | None = None, anteriores: Any = None, nuevos: Any = None) -> None:
        ctx = self.context()
        try:
            self.execute(
                """
                INSERT INTO gp_historial_acciones
                (usuario, accion, entidad_tipo, entidad_id, datos_anteriores, datos_nuevos, fundacion_id, usuario_creador_id, fecha_accion)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    ctx.get('username') or 'sistema', accion, entidad_tipo, entidad_id,
                    json.dumps(anteriores, ensure_ascii=False) if anteriores is not None else None,
                    json.dumps(nuevos, ensure_ascii=False) if nuevos is not None else None,
                    ctx.get('fundacion_id') or 1, ctx.get('usuario_id'), now_iso(),
                ),
            )
        except Exception:
            pass

    def list_coordinators_summary(self, periodo: str) -> list[dict[str, Any]]:
        where, params = self.coordinator_scope_clause('c')
        fid = int(self.context().get('fundacion_id') or 1)
        coordinadores = self.fetch_all(
            f"""
            SELECT c.*,
                   (SELECT COUNT(*) FROM gp_docentes d
                     WHERE d.coordinador_id=c.id AND d.activo=1
                       AND COALESCE(d.fundacion_id, 1)={fid}) AS docentes_asignados,
                   (SELECT COUNT(*) FROM gp_equipos_interdisciplinarios e
                     WHERE e.coordinador_id=c.id AND e.activo=1
                       AND COALESCE(e.fundacion_id, 1)={fid}) AS equipo_asignado,
                   (SELECT COUNT(*) FROM gp_entregables en
                     WHERE en.coordinador_id=c.id AND en.activo=1 AND en.periodo=?
                       AND COALESCE(en.fundacion_id, 1)={fid}
                       AND COALESCE(en.estado,'Pendiente') NOT IN ('Aprobado','Cumplido fuera de fecha')) AS pendientes_mes,
                   (SELECT COUNT(*) FROM gp_alertas a
                     WHERE a.coordinador_id=c.id AND a.leida=0
                       AND COALESCE(a.fundacion_id, 1)={fid}) AS alertas_abiertas
            FROM gp_coordinadores c
            WHERE {where} AND c.activo=1
            ORDER BY c.nombre
            """,
            [periodo] + params,
        )
        for coord in coordinadores:
            unidades = self.list_units_for_coordinator(coord)
            coord['unidades_asignadas'] = len(unidades)
            coord['unidades'] = unidades
            coord['cumplimiento'] = self.compliance_for_coordinator(coord['id'], periodo)
            coord['estado_cumplimiento'] = coord['cumplimiento'].get('semaforo', 'GRIS')
        return coordinadores

    def list_units_for_coordinator(self, coord: dict[str, Any] | int) -> list[str]:
        if isinstance(coord, dict):
            cid = coord.get('id')
            unidades_json = coord.get('unidades_json') or '[]'
        else:
            cid = coord
            row = self.fetch_one('SELECT unidades_json FROM gp_coordinadores WHERE id=?', (cid,)) or {}
            unidades_json = row.get('unidades_json') or '[]'
        unidades = set()
        try:
            parsed = json.loads(unidades_json) if isinstance(unidades_json, str) else unidades_json
            if isinstance(parsed, list):
                unidades.update(str(x).strip() for x in parsed if str(x).strip())
        except Exception:
            if unidades_json:
                unidades.update(x.strip() for x in str(unidades_json).split(',') if x.strip())
        rows = self.fetch_all("SELECT unidad FROM gp_unidades_asignadas WHERE coordinador_id=? AND estado='activo'", (cid,))
        unidades.update(row['unidad'] for row in rows if row.get('unidad'))
        rows = self.fetch_all("SELECT DISTINCT unidad FROM gp_docentes WHERE coordinador_id=? AND activo=1 AND COALESCE(unidad,'')!=''", (cid,))
        unidades.update(row['unidad'] for row in rows if row.get('unidad'))
        return sorted(unidades)

    def compliance_for_coordinator(self, coordinador_id: int, periodo: str) -> dict[str, Any]:
        entregables = self.fetch_all(
            """
            SELECT * FROM gp_entregables
            WHERE coordinador_id=? AND activo=1 AND periodo=?
            """,
            (coordinador_id, periodo),
        )
        actividades = self.fetch_all(
            """
            SELECT * FROM gp_calendario_eventos
            WHERE coordinador_id=? AND substr(fecha,1,7)=?
            """,
            (coordinador_id, periodo),
        )
        total = len(entregables) + len(actividades)
        cumplidas = sum(1 for x in entregables if str(x.get('estado')).upper() in {'APROBADO', 'CUMPLIDO', 'CUMPLIDO FUERA DE FECHA'})
        cumplidas += sum(1 for x in actividades if str(x.get('estado')).upper() in {'CUMPLIDO', 'APROBADO'})
        vencidas = sum(1 for x in entregables if str(x.get('estado')).upper() == 'VENCIDO')
        vencidas += sum(1 for x in actividades if str(x.get('estado')).upper() == 'VENCIDO')
        anuladas = sum(1 for x in actividades if str(x.get('estado')).upper() == 'ANULADO')
        pendientes = max(0, total - cumplidas - vencidas - anuladas)
        porcentaje = round((cumplidas / total) * 100, 1) if total else 0
        semaforo = 'VERDE' if porcentaje >= 80 and vencidas == 0 else 'AMARILLO' if porcentaje >= 50 else 'ROJO' if total else 'GRIS'
        data = {
            'coordinador_id': coordinador_id,
            'periodo': periodo,
            'total_actividades': total,
            'cumplidas': cumplidas,
            'pendientes': pendientes,
            'vencidas': vencidas,
            'anuladas': anuladas,
            'porcentaje': porcentaje,
            'semaforo': semaforo,
        }
        self.upsert_compliance(data)
        return data

    def upsert_compliance(self, data: dict[str, Any]) -> None:
        ctx = self.context()
        fundacion_id = ctx.get('fundacion_id') or 1
        usuario_id = ctx.get('usuario_id')
        self.execute(
            """
            INSERT INTO gp_estado_cumplimiento
            (coordinador_id, periodo, total_actividades, cumplidas, pendientes, vencidas, anuladas,
             porcentaje, semaforo, fundacion_id, usuario_creador_id, fecha_creacion, fecha_actualizacion)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(coordinador_id, periodo, fundacion_id) DO UPDATE SET
                total_actividades=excluded.total_actividades,
                cumplidas=excluded.cumplidas,
                pendientes=excluded.pendientes,
                vencidas=excluded.vencidas,
                anuladas=excluded.anuladas,
                porcentaje=excluded.porcentaje,
                semaforo=excluded.semaforo,
                fecha_actualizacion=excluded.fecha_actualizacion
            """,
            (
                data['coordinador_id'], data['periodo'], data['total_actividades'], data['cumplidas'],
                data['pendientes'], data['vencidas'], data['anuladas'], data['porcentaje'], data['semaforo'],
                fundacion_id, usuario_id, now_iso(), now_iso(),
            ),
        )

    def coordinator_panel(self, coordinador_id: int, periodo: str) -> dict[str, Any] | None:
        where, params = self.coordinator_scope_clause('c')
        coord = self.fetch_one(f"SELECT c.* FROM gp_coordinadores c WHERE {where} AND c.id=?", params + [coordinador_id])
        if not coord:
            return None
        return {
            'coordinador': coord,
            'unidades': self.list_units_for_coordinator(coord),
            'docentes': self.fetch_all("SELECT * FROM gp_docentes WHERE coordinador_id=? AND activo=1 ORDER BY unidad, nombre", (coordinador_id,)),
            'equipo': self.fetch_all("SELECT * FROM gp_equipos_interdisciplinarios WHERE coordinador_id=? AND activo=1 ORDER BY rol, nombre", (coordinador_id,)),
            'talento_asignado': self.fetch_all("SELECT * FROM gp_asignaciones_coordinador WHERE coordinador_id=? AND estado='ACTIVO' ORDER BY tipo_talento, nombre", (coordinador_id,)),
            'planeaciones': self.fetch_all("SELECT * FROM gp_planeaciones WHERE coordinador_id=? AND periodo=? ORDER BY fecha_creacion DESC", (coordinador_id, periodo)),
            'informes': self.fetch_all("SELECT * FROM gp_entregables WHERE coordinador_id=? AND periodo=? AND lower(tipo) LIKE '%informe%' ORDER BY fecha_limite", (coordinador_id, periodo)),
            'evidencias': self.fetch_all("SELECT * FROM gp_evidencias WHERE coordinador_id=? ORDER BY fecha_creacion DESC LIMIT 100", (coordinador_id,)),
            'cuentas_cobro': self.fetch_all("SELECT * FROM gp_entregables WHERE coordinador_id=? AND periodo=? AND lower(tipo) LIKE '%cuenta%' ORDER BY fecha_limite", (coordinador_id, periodo)),
            'pendientes': self.fetch_all("SELECT * FROM gp_entregables WHERE coordinador_id=? AND periodo=? AND estado NOT IN ('Aprobado','Cumplido fuera de fecha') ORDER BY fecha_limite", (coordinador_id, periodo)),
            'cumplimiento': self.compliance_for_coordinator(coordinador_id, periodo),
            'historial': self.fetch_all("SELECT * FROM gp_historial_acciones WHERE entidad_tipo IN ('gp_entregables','gp_calendario_eventos','gp_asignaciones_coordinador') AND fecha_accion >= ? ORDER BY fecha_accion DESC LIMIT 100", (periodo + '-01',)),
        }

    def list_assignments(self, coordinador_id: int | None = None) -> list[dict[str, Any]]:
        where, params = self.entity_scope_clause('a')
        if coordinador_id:
            where += ' AND a.coordinador_id=?'
            params.append(coordinador_id)
        fid = int(self.context().get('fundacion_id') or 1)
        return self.fetch_all(
            f"""
            SELECT a.*, c.nombre AS coordinador_nombre
            FROM gp_asignaciones_coordinador a
            LEFT JOIN gp_coordinadores c
              ON c.id=a.coordinador_id AND COALESCE(c.fundacion_id, 1)={fid}
            WHERE {where}
            ORDER BY a.estado DESC, c.nombre, a.tipo_talento, a.nombre
            """,
            params,
        )

    def create_assignment(self, data: dict[str, Any]) -> dict[str, Any]:
        now = now_iso()
        new_id = self.execute(
            """
            INSERT INTO gp_asignaciones_coordinador
            (coordinador_id, tipo_talento, origen_tabla, origen_id, nombre, documento, cargo, rol, unidad,
             telefono, email, estado, fecha_inicio, observaciones, fecha_creacion, fecha_actualizacion)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'ACTIVO', ?, ?, ?, ?)
            """,
            (
                data.get('coordinador_id'), data.get('tipo_talento', 'DOCENTE'), data.get('origen_tabla'), data.get('origen_id'),
                normalizar_texto(data.get('nombre')), normalizar_texto(data.get('documento')), normalizar_texto(data.get('cargo')),
                normalizar_texto(data.get('rol')), normalizar_texto(data.get('unidad')), normalizar_texto(data.get('telefono')),
                normalizar_texto(data.get('email')), data.get('fecha_inicio') or now[:10], normalizar_texto(data.get('observaciones')),
                now, now,
            ),
        )
        self.log('CREAR_ASIGNACION_COORDINADOR', 'gp_asignaciones_coordinador', new_id, nuevos=data)
        return self.fetch_one('SELECT * FROM gp_asignaciones_coordinador WHERE id=?', (new_id,)) or {}

    def update_assignment(self, asignacion_id: int, data: dict[str, Any]) -> dict[str, Any] | None:
        anterior = self.fetch_one('SELECT * FROM gp_asignaciones_coordinador WHERE id=?', (asignacion_id,))
        if not anterior:
            return None
        now = now_iso()
        self.execute(
            """
            UPDATE gp_asignaciones_coordinador
            SET coordinador_id=?, tipo_talento=?, nombre=?, documento=?, cargo=?, rol=?, unidad=?, telefono=?, email=?,
                estado=?, fecha_inicio=?, fecha_fin=?, observaciones=?, fecha_actualizacion=?
            WHERE id=?
            """,
            (
                data.get('coordinador_id', anterior.get('coordinador_id')),
                data.get('tipo_talento', anterior.get('tipo_talento')),
                normalizar_texto(data.get('nombre', anterior.get('nombre'))),
                normalizar_texto(data.get('documento', anterior.get('documento'))),
                normalizar_texto(data.get('cargo', anterior.get('cargo'))),
                normalizar_texto(data.get('rol', anterior.get('rol'))),
                normalizar_texto(data.get('unidad', anterior.get('unidad'))),
                normalizar_texto(data.get('telefono', anterior.get('telefono'))),
                normalizar_texto(data.get('email', anterior.get('email'))),
                data.get('estado', anterior.get('estado') or 'ACTIVO'),
                data.get('fecha_inicio', anterior.get('fecha_inicio')),
                data.get('fecha_fin', anterior.get('fecha_fin')),
                normalizar_texto(data.get('observaciones', anterior.get('observaciones'))),
                now,
                asignacion_id,
            ),
        )
        actualizado = self.fetch_one('SELECT * FROM gp_asignaciones_coordinador WHERE id=?', (asignacion_id,))
        self.execute(
            """
            INSERT INTO gp_historial_asignaciones
            (asignacion_id, coordinador_origen_id, coordinador_destino_id, accion, datos_anteriores, datos_nuevos, usuario, fecha_accion)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                asignacion_id, anterior.get('coordinador_id'), data.get('coordinador_id', anterior.get('coordinador_id')),
                'REASIGNAR' if data.get('coordinador_id') and data.get('coordinador_id') != anterior.get('coordinador_id') else 'ACTUALIZAR',
                json.dumps(anterior, ensure_ascii=False), json.dumps(actualizado, ensure_ascii=False),
                self.context().get('username'), now,
            ),
        )
        self.log('ACTUALIZAR_ASIGNACION_COORDINADOR', 'gp_asignaciones_coordinador', asignacion_id, anteriores=anterior, nuevos=actualizado)
        return actualizado

    def deactivate_assignment(self, asignacion_id: int) -> bool:
        anterior = self.fetch_one('SELECT * FROM gp_asignaciones_coordinador WHERE id=?', (asignacion_id,))
        if not anterior:
            return False
        now = now_iso()
        self.execute("UPDATE gp_asignaciones_coordinador SET estado='INACTIVO', fecha_fin=?, fecha_actualizacion=? WHERE id=?", (now[:10], now, asignacion_id))
        self.log('INACTIVAR_ASIGNACION_COORDINADOR', 'gp_asignaciones_coordinador', asignacion_id, anteriores=anterior)
        return True

    def list_activities(self, filters: dict[str, Any]) -> list[dict[str, Any]]:
        where, params = self.entity_scope_clause('ev')
        if filters.get('periodo'):
            where += ' AND substr(ev.fecha,1,7)=?'
            params.append(filters['periodo'])
        if filters.get('coordinador_id'):
            where += ' AND ev.coordinador_id=?'
            params.append(filters['coordinador_id'])
        if filters.get('unidad'):
            where += ' AND ev.unidad=?'
            params.append(filters['unidad'])
        if filters.get('docente_id'):
            where += ' AND ev.docente_id=?'
            params.append(filters['docente_id'])
        if filters.get('tipo'):
            where += ' AND ev.tipo=?'
            params.append(filters['tipo'])
        if filters.get('estado'):
            where += ' AND ev.estado=?'
            params.append(filters['estado'])
        if filters.get('fecha'):
            where += ' AND ev.fecha=?'
            params.append(filters['fecha'])
        fid = int(self.context().get('fundacion_id') or 1)
        return self.fetch_all(
            f"""
            SELECT ev.*, c.nombre AS coordinador_nombre, d.nombre AS docente_nombre_real
            FROM gp_calendario_eventos ev
            LEFT JOIN gp_coordinadores c
              ON c.id=ev.coordinador_id AND COALESCE(c.fundacion_id, 1)={fid}
            LEFT JOIN gp_docentes d
              ON d.id=ev.docente_id AND COALESCE(d.fundacion_id, 1)={fid}
            WHERE {where}
            ORDER BY ev.fecha, COALESCE(ev.hora,''), ev.titulo
            """,
            params,
        )

    def create_activity(self, data: dict[str, Any]) -> dict[str, Any]:
        now = now_iso()
        estado = data.get('estado') or 'PROGRAMADO'
        color = self.color_for_state(estado)
        new_id = self.execute(
            """
            INSERT INTO gp_calendario_eventos
            (coordinador_id, entregable_id, titulo, tipo, fecha, hora, estado, descripcion, color,
             unidad, docente_id, docente_nombre, responsable, prioridad, evidencia_requerida,
             fecha_creacion, fecha_actualizacion)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                data.get('coordinador_id'), data.get('entregable_id'), normalizar_texto(data.get('titulo')),
                data.get('tipo') or 'Actividad', data.get('fecha'), data.get('hora') or '', estado,
                normalizar_texto(data.get('descripcion')), color, normalizar_texto(data.get('unidad')),
                data.get('docente_id'), normalizar_texto(data.get('docente_nombre')),
                normalizar_texto(data.get('responsable')), data.get('prioridad') or 'MEDIA',
                1 if data.get('evidencia_requerida') else 0, now, now,
            ),
        )
        activity = self.fetch_one('SELECT * FROM gp_calendario_eventos WHERE id=?', (new_id,)) or {}
        self.log('CREAR_ACTIVIDAD_CALENDARIO', 'gp_calendario_eventos', new_id, nuevos=activity)
        return activity

    def update_activity(self, activity_id: int, data: dict[str, Any]) -> dict[str, Any] | None:
        anterior = self.fetch_one('SELECT * FROM gp_calendario_eventos WHERE id=?', (activity_id,))
        if not anterior:
            return None
        estado = data.get('estado', anterior.get('estado') or 'PROGRAMADO')
        color = self.color_for_state(estado)
        now = now_iso()
        self.execute(
            """
            UPDATE gp_calendario_eventos
            SET coordinador_id=?, entregable_id=?, titulo=?, tipo=?, fecha=?, hora=?, estado=?, descripcion=?, color=?,
                unidad=?, docente_id=?, docente_nombre=?, responsable=?, prioridad=?, evidencia_requerida=?,
                fecha_cumplimiento=?, reprogramado_de=?, fecha_actualizacion=?
            WHERE id=?
            """,
            (
                data.get('coordinador_id', anterior.get('coordinador_id')),
                data.get('entregable_id', anterior.get('entregable_id')),
                normalizar_texto(data.get('titulo', anterior.get('titulo'))),
                data.get('tipo', anterior.get('tipo')),
                data.get('fecha', anterior.get('fecha')),
                data.get('hora', anterior.get('hora')),
                estado,
                normalizar_texto(data.get('descripcion', anterior.get('descripcion'))),
                color,
                normalizar_texto(data.get('unidad', anterior.get('unidad'))),
                data.get('docente_id', anterior.get('docente_id')),
                normalizar_texto(data.get('docente_nombre', anterior.get('docente_nombre'))),
                normalizar_texto(data.get('responsable', anterior.get('responsable'))),
                data.get('prioridad', anterior.get('prioridad')),
                1 if data.get('evidencia_requerida', anterior.get('evidencia_requerida')) else 0,
                data.get('fecha_cumplimiento', anterior.get('fecha_cumplimiento')),
                data.get('reprogramado_de', anterior.get('reprogramado_de')),
                now,
                activity_id,
            ),
        )
        actualizado = self.fetch_one('SELECT * FROM gp_calendario_eventos WHERE id=?', (activity_id,))
        self.log('ACTUALIZAR_ACTIVIDAD_CALENDARIO', 'gp_calendario_eventos', activity_id, anteriores=anterior, nuevos=actualizado)
        return actualizado

    def delete_activity(self, activity_id: int) -> bool:
        anterior = self.fetch_one('SELECT * FROM gp_calendario_eventos WHERE id=?', (activity_id,))
        if not anterior:
            return False
        self.execute("UPDATE gp_calendario_eventos SET estado='ANULADO', color=?, fecha_actualizacion=? WHERE id=?", (self.color_for_state('ANULADO'), now_iso(), activity_id))
        self.log('ANULAR_ACTIVIDAD_CALENDARIO', 'gp_calendario_eventos', activity_id, anteriores=anterior)
        return True

    @staticmethod
    def color_for_state(estado: str) -> str:
        estado = str(estado or '').upper()
        return {
            'CUMPLIDO': 'verde',
            'PENDIENTE': 'amarillo',
            'VENCIDO': 'rojo',
            'PROGRAMADO': 'azul',
            'REPROGRAMADO': 'azul',
            'ANULADO': 'gris',
        }.get(estado, 'gris')
