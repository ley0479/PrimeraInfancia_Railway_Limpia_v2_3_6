from __future__ import annotations

import json
from datetime import datetime, date, timedelta
from typing import Any, Iterable

from flask import g, request, has_request_context

from .schema import BILLING_SCHEMA_SQL, DEFAULT_PLANES, DEFAULT_PAQUETES, ALL_MODULES
from modules.sqlalchemy_compat import CoreCompatRepository


def now_iso() -> str:
    return datetime.now().isoformat(timespec='seconds')


def today_iso() -> str:
    return date.today().isoformat()


def parse_date(value: Any, default: date | None = None) -> date:
    if isinstance(value, date):
        return value
    text = str(value or '').strip()[:10]
    if not text:
        return default or date.today()
    try:
        return date.fromisoformat(text)
    except Exception:
        return default or date.today()


def add_months(d: date, months: int = 1) -> date:
    month = d.month - 1 + months
    year = d.year + month // 12
    month = month % 12 + 1
    import calendar
    day = min(d.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def row_to_dict(row: dict[str, Any] | None) -> dict[str, Any] | None:
    return dict(row) if row is not None else None


def json_loads(value: Any, default: Any = None) -> Any:
    if value in (None, ''):
        return default
    try:
        return json.loads(value)
    except Exception:
        return default


class BillingRepository(CoreCompatRepository):
    def __init__(self, database_path: str):
        self.database_path = database_path  # compatibilidad con firma histórica

    def context(self) -> dict[str, Any]:
        try:
            from modules.seguridad.services import get_request_user_context
            ctx = get_request_user_context() if has_request_context() else {}
        except Exception:
            ctx = {}
        user = (getattr(g, 'current_user', None) or {}) if has_request_context() else {}
        ctx.setdefault('usuario_id', user.get('id'))
        ctx.setdefault('fundacion_id', user.get('fundacion_id') or 1)
        # Fuera de una petición se ejecuta bootstrap de catálogo central. Dentro
        # de una petición, el rol siempre proviene de la sesión validada.
        ctx.setdefault('rol', user.get('rol') or ('SYSTEM' if not has_request_context() else ''))
        ctx.setdefault('username', user.get('username') or 'sistema')
        return ctx

    def table_exists(self, cur_or_table: Any, table: str | None = None) -> bool:
        table_name = table or str(cur_or_table)
        return CoreCompatRepository.table_exists(self, table_name)

    def cols(self, cur_or_table: Any, table: str | None = None) -> set[str]:
        table_name = table or str(cur_or_table)
        return CoreCompatRepository.columns(self, table_name)

    def ensure_column(self, cur: Any, table: str, column: str, definition: str) -> None:
        if self.table_exists(table) and column not in self.cols(table):
            from modules.sqlalchemy_compat import normalize_ddl_for_engine
            cur.execute(normalize_ddl_for_engine(f"ALTER TABLE {table} ADD COLUMN {column} {definition}"))

    def init_schema(self) -> None:
        conn = self.connect()
        cur = conn.cursor()
        cur.executescript(BILLING_SCHEMA_SQL)
        self._seed_planes(cur)
        self._seed_paquetes(cur)
        self._ensure_foundation_columns(cur)
        self._ensure_subscriptions_for_foundations(cur)
        conn.commit()
        conn.close()

    def _ensure_foundation_columns(self, cur: Any) -> None:
        if not self.table_exists(cur, 'fundaciones'):
            return
        for col, definition in {
            'nit': 'TEXT',
            'representante': 'TEXT',
            'email': 'TEXT',
            'telefono': 'TEXT',
            'direccion': 'TEXT',
            'municipio': 'TEXT',
            'departamento': 'TEXT',
            'fecha_inicio': 'TEXT',
            'fecha_vencimiento': 'TEXT',
            'plan_id': 'INTEGER',
            'suscripcion_estado': "TEXT DEFAULT 'ACTIVA'",
            'creditos_disponibles': 'INTEGER DEFAULT 0',
            'fecha_actualizacion': 'TEXT',
        }.items():
            self.ensure_column(cur, 'fundaciones', col, definition)

    def _seed_planes(self, cur: Any) -> None:
        for plan in DEFAULT_PLANES:
            modules = json.dumps(plan.get('modulos_habilitados') or ALL_MODULES, ensure_ascii=False)
            cur.execute(
                """
                INSERT INTO planes_suscripcion
                (nombre, descripcion, precio_mensual, limite_usuarios, limite_coordinadores,
                 limite_unidades, creditos_incluidos, modulos_habilitados, estado, personalizado,
                 fecha_creacion, fecha_actualizacion)
                SELECT ?, ?, ?, ?, ?, ?, ?, ?, 'ACTIVO', ?, ?, ?
                WHERE NOT EXISTS (SELECT 1 FROM planes_suscripcion WHERE nombre = ?)
                """,
                (
                    plan['nombre'], plan.get('descripcion', ''), plan.get('precio_mensual', 0),
                    plan.get('limite_usuarios', 0), plan.get('limite_coordinadores', 0), plan.get('limite_unidades', 0),
                    plan.get('creditos_incluidos', 0), modules, int(plan.get('personalizado', 0)), now_iso(), now_iso(), plan['nombre']
                ),
            )
            row = cur.execute("SELECT id FROM planes_suscripcion WHERE nombre=?", (plan['nombre'],)).fetchone()
            if row:
                for modulo in plan.get('modulos_habilitados') or ALL_MODULES:
                    cur.execute(
                        """
                        INSERT INTO modulos_plan (plan_id, modulo_codigo, habilitado, fecha_creacion)
                        SELECT ?, ?, 1, ?
                        WHERE NOT EXISTS (SELECT 1 FROM modulos_plan WHERE plan_id=? AND modulo_codigo=?)
                        """,
                        (row['id'], modulo, now_iso(), row['id'], modulo),
                    )

    def _seed_paquetes(self, cur: Any) -> None:
        for nombre, creditos, precio, personalizado in DEFAULT_PAQUETES:
            cur.execute(
                """
                INSERT INTO paquetes_credito
                (nombre, creditos, precio, estado, personalizado, fecha_creacion, fecha_actualizacion)
                SELECT ?, ?, ?, 'ACTIVO', ?, ?, ?
                WHERE NOT EXISTS (SELECT 1 FROM paquetes_credito WHERE nombre = ?)
                """,
                (nombre, creditos, precio, personalizado, now_iso(), now_iso(), nombre),
            )

    def _ensure_subscriptions_for_foundations(self, cur: Any) -> None:
        if not self.table_exists(cur, 'fundaciones'):
            return
        premium = cur.execute("SELECT * FROM planes_suscripcion WHERE nombre='PREMIUM'").fetchone()
        basico = cur.execute("SELECT * FROM planes_suscripcion WHERE nombre='BASICO'").fetchone()
        default_plan = premium or basico
        if not default_plan:
            return
        foundations = cur.execute("SELECT * FROM fundaciones").fetchall()
        for f in foundations:
            existing = cur.execute("SELECT id FROM suscripciones_fundacion WHERE fundacion_id=?", (f['id'],)).fetchone()
            if existing:
                continue
            inicio = parse_date(f['fecha_inicio'] if 'fecha_inicio' in f.keys() else None, date.today())
            venc = parse_date(f['fecha_vencimiento'] if 'fecha_vencimiento' in f.keys() else None, add_months(inicio, 1))
            estado = 'ACTIVA' if venc >= date.today() else 'VENCIDA'
            cur.execute(
                """
                INSERT INTO suscripciones_fundacion
                (fundacion_id, plan_id, estado, fecha_inicio, fecha_vencimiento, dias_gracia,
                 creditos_disponibles, creditos_incluidos_periodo, modulos_habilitados, fecha_creacion, fecha_actualizacion)
                VALUES (?, ?, ?, ?, ?, 5, ?, ?, ?, ?, ?)
                """,
                (
                    f['id'], default_plan['id'], estado, inicio.isoformat(), venc.isoformat(),
                    default_plan['creditos_incluidos'], default_plan['creditos_incluidos'],
                    default_plan['modulos_habilitados'], now_iso(), now_iso()
                ),
            )
        try:
            cur.execute(
                """
                UPDATE fundaciones
                SET plan_id = COALESCE(plan_id, (SELECT plan_id FROM suscripciones_fundacion s WHERE s.fundacion_id=fundaciones.id)),
                    suscripcion_estado = COALESCE(suscripcion_estado, (SELECT estado FROM suscripciones_fundacion s WHERE s.fundacion_id=fundaciones.id)),
                    creditos_disponibles = COALESCE(creditos_disponibles, (SELECT creditos_disponibles FROM suscripciones_fundacion s WHERE s.fundacion_id=fundaciones.id))
                WHERE id IN (SELECT fundacion_id FROM suscripciones_fundacion)
                """
            )
        except Exception:
            pass

    # execute, execute_update, fetch_all y fetch_one se heredan de
    # CoreCompatRepository para ejecutar SQL histórico con SQLAlchemy Core.

    def current_fundacion_id(self) -> int:
        return int(self.context().get('fundacion_id') or 1)

    def current_user_id(self) -> int | None:
        uid = self.context().get('usuario_id')
        return int(uid) if uid else None

    def is_superadmin(self) -> bool:
        return self.context().get('rol') == 'SUPERADMIN'

    def fundacion_scope_clause(self, alias: str = '') -> tuple[str, list[Any]]:
        if self.is_superadmin():
            return '1=1', []
        field = f'{alias}.fundacion_id' if alias else 'fundacion_id'
        return f'{field} = ?', [self.current_fundacion_id()]

    def log(self, accion: str, tabla: str | None = None, registro_id: int | None = None, antes: Any = None, despues: Any = None) -> None:
        ctx = self.context()
        try:
            self.execute(
                """
                INSERT INTO auditoria_facturacion
                (usuario_id, username, fundacion_id, accion, tabla_afectada, registro_id,
                 datos_anteriores, datos_nuevos, ip, user_agent, fecha)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    ctx.get('usuario_id'), ctx.get('username'), ctx.get('fundacion_id'), accion,
                    tabla, registro_id,
                    json.dumps(antes, ensure_ascii=False) if antes is not None else None,
                    json.dumps(despues, ensure_ascii=False) if despues is not None else None,
                    request.remote_addr if request else None,
                    request.headers.get('User-Agent') if request else None,
                    now_iso(),
                ),
            )
        except Exception:
            pass
