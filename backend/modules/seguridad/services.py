from __future__ import annotations

import hashlib
import html
import json
import re
import secrets
import sqlite3
import threading
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from functools import wraps
from pathlib import Path
from typing import Any, Mapping

from flask import current_app, g, has_request_context, jsonify, redirect, request
from werkzeug.security import generate_password_hash

from .schema import (
    MULTITENANT_COLUMNS,
    MULTITENANT_TABLES,
    PERMISOS_BASE,
    ROLES_SISTEMA,
    SEGURIDAD_SCHEMA_SQL,
)

PUBLIC_PATHS = {
    '/api/auth/login',
    '/api/auth/recuperar',
    '/api/auth/restablecer',
    '/api/health',
}
PASSWORD_CHANGE_ALLOWED_PATHS = {
    '/api/auth/me',
    '/api/auth/logout',
    '/api/auth/cambiar-password',
}

ROLE_MENU_PERMISSIONS = {
    'SUPERADMIN': ['dashboard', 'buscador-beneficiarios', 'calendario-inteligente', 'administracion', 'panel-comercial', 'gerencia-general', 'acceso-compartido', 'configuracion-institucional', 'ajustes', 'administrador-disenos', 'backups', 'calidad-datos', 'base-maestra', 'manual-operativo', 'motor-plantillas', 'plantillas-oficiales', 'paquete-mensual', 'reportes-gerenciales', 'facturacion', 'planeacion-pedagogica', 'gestion-pedagogica', 'gestion-coordinador', 'cuentas-cobro', 'relacion-mes', 'formatos', 'nutricion', 'salud-nutricion', 'talento', 'cumplimiento'],
    'GERENTE': ['dashboard', 'buscador-beneficiarios', 'calendario-inteligente', 'administracion', 'panel-comercial', 'gerencia-general', 'acceso-compartido', 'configuracion-institucional', 'ajustes', 'administrador-disenos', 'backups', 'calidad-datos', 'base-maestra', 'manual-operativo', 'motor-plantillas', 'plantillas-oficiales', 'paquete-mensual', 'reportes-gerenciales', 'facturacion', 'planeacion-pedagogica', 'gestion-pedagogica', 'gestion-coordinador', 'cuentas-cobro', 'relacion-mes', 'formatos', 'nutricion', 'salud-nutricion', 'talento', 'cumplimiento'],
    'COORDINADOR': ['dashboard', 'buscador-beneficiarios', 'calendario-inteligente', 'manual-operativo', 'ajustes', 'calidad-datos', 'base-maestra', 'paquete-mensual', 'reportes-gerenciales', 'planeacion-pedagogica', 'gestion-pedagogica', 'gestion-coordinador', 'formatos', 'relacion-mes', 'cumplimiento'],
    'DOCENTE': ['dashboard', 'buscador-beneficiarios', 'calendario-inteligente', 'manual-operativo', 'ajustes', 'planeacion-pedagogica', 'gestion-pedagogica', 'gestion-coordinador', 'formatos'],
    'NUTRICIONISTA': ['dashboard', 'buscador-beneficiarios', 'calendario-inteligente', 'manual-operativo', 'ajustes', 'calidad-datos', 'base-maestra', 'salud-nutricion', 'nutricion'],
    'PSICOSOCIAL': ['dashboard', 'buscador-beneficiarios', 'calendario-inteligente', 'manual-operativo', 'ajustes', 'planeacion-pedagogica', 'gestion-pedagogica', 'gestion-coordinador'],
    'AUXILIAR_ADMINISTRATIVO': ['dashboard', 'buscador-beneficiarios', 'calendario-inteligente', 'manual-operativo', 'ajustes', 'calidad-datos', 'base-maestra', 'motor-plantillas', 'plantillas-oficiales', 'paquete-mensual', 'reportes-gerenciales', 'facturacion', 'planeacion-pedagogica', 'gestion-pedagogica', 'gestion-coordinador', 'cuentas-cobro', 'relacion-mes', 'formatos', 'talento', 'cumplimiento'],
}

ALL_ROLES = frozenset(ROLES_SISTEMA)
MANAGEMENT = frozenset({'SUPERADMIN', 'GERENTE'})
ADMIN_OPERATIONS = frozenset({'SUPERADMIN', 'GERENTE', 'COORDINADOR', 'AUXILIAR_ADMINISTRATIVO'})
DATA_OPERATIONS = frozenset({'SUPERADMIN', 'GERENTE', 'COORDINADOR', 'AUXILIAR_ADMINISTRATIVO', 'NUTRICIONISTA'})
PEDAGOGICAL = frozenset({'SUPERADMIN', 'GERENTE', 'COORDINADOR', 'DOCENTE', 'PSICOSOCIAL', 'AUXILIAR_ADMINISTRATIVO'})
NUTRITION = frozenset({'SUPERADMIN', 'GERENTE', 'NUTRICIONISTA'})

# Toda familia de rutas /api debe aparecer explícitamente. Lo no declarado se deniega.
PATH_ROLE_RULES = sorted([
    ('/api/auth', ALL_ROLES),
    ('/api/panel-comercial', MANAGEMENT),
    ('/api/gerencia-general', MANAGEMENT),
    ('/api/acceso', MANAGEMENT),
    ('/api/backups', frozenset({'SUPERADMIN'})),
    ('/api/configuracion-institucional', MANAGEMENT),
    ('/api/institucional-archivos', ALL_ROLES),
    ('/api/identidad-visual', MANAGEMENT),
    ('/api/fundaciones', MANAGEMENT),
    ('/api/usuarios', MANAGEMENT),
    ('/api/roles', MANAGEMENT),
    ('/api/seguridad', MANAGEMENT),
    ('/api/facturacion', frozenset({'SUPERADMIN', 'GERENTE', 'AUXILIAR_ADMINISTRATIVO'})),
    ('/api/cuentas-cobro', frozenset({'SUPERADMIN', 'GERENTE', 'AUXILIAR_ADMINISTRATIVO'})),
    ('/api/talento-core', frozenset({'SUPERADMIN', 'GERENTE', 'AUXILIAR_ADMINISTRATIVO'})),
    ('/api/talento', frozenset({'SUPERADMIN', 'GERENTE', 'AUXILIAR_ADMINISTRATIVO'})),
    ('/api/motor-plantillas', frozenset({'SUPERADMIN', 'GERENTE', 'AUXILIAR_ADMINISTRATIVO'})),
    ('/api/plantillas-oficiales', frozenset({'SUPERADMIN', 'GERENTE', 'AUXILIAR_ADMINISTRATIVO'})),
    ('/api/paquete-mensual', ADMIN_OPERATIONS),
    ('/api/reportes-gerenciales', ADMIN_OPERATIONS),
    ('/api/calidad-datos', DATA_OPERATIONS),
    ('/api/base-maestra', DATA_OPERATIONS),
    ('/api/cruce-bases', frozenset({'SUPERADMIN', 'GERENTE', 'COORDINADOR', 'DOCENTE', 'NUTRICIONISTA'})),
    ('/api/planeacion-pedagogica', PEDAGOGICAL),
    ('/api/gestion-pedagogica', PEDAGOGICAL),
    ('/api/gestion-coordinador', PEDAGOGICAL),
    ('/api/salud-nutricion', NUTRITION),
    ('/api/nutricion', NUTRITION),
    ('/api/cumplimiento', ADMIN_OPERATIONS),
    ('/api/documentos-institucionales', frozenset({'SUPERADMIN', 'GERENTE', 'COORDINADOR', 'PSICOSOCIAL', 'AUXILIAR_ADMINISTRATIVO'})),
    ('/api/entregables-operacion', ADMIN_OPERATIONS),
    ('/api/informes', ADMIN_OPERATIONS),
    ('/api/relacion-mes', ADMIN_OPERATIONS),
    ('/api/sincronizar', ADMIN_OPERATIONS),
    ('/api/calendario-inteligente', ALL_ROLES),
    ('/api/calendario', ALL_ROLES),
    ('/api/ajustes-ui', ALL_ROLES),
    ('/api/theme-manager', ALL_ROLES),
    ('/api/manual-operativo', ALL_ROLES),
    ('/api/asistente-icbf', ALL_ROLES),
    ('/api/corporaciones', ALL_ROLES),
    ('/api/beneficiarios', ALL_ROLES),
    ('/api/buscador', ALL_ROLES),
    ('/api/unidades', ALL_ROLES),
    ('/api/estadisticas', ALL_ROLES),
    ('/api/alertas', ALL_ROLES),
    ('/api/historial', ALL_ROLES),
    ('/api/jobs', ALL_ROLES),
    ('/api/procesar', ALL_ROLES),
    ('/api/formatos', ALL_ROLES),
    ('/api/plantillas', ALL_ROLES),
    ('/api/rpp', ALL_ROLES),
    ('/api/bienestarina', ALL_ROLES),
    ('/api/descargar-archivo', ALL_ROLES),
    ('/api/descargar', ALL_ROLES),
], key=lambda item: len(item[0]), reverse=True)


def now_iso() -> str:
    return datetime.now().isoformat(timespec='seconds')


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


_WAL_INIT_LOCK = threading.RLock()
_WAL_INITIALIZED_DATABASES: set[str] = set()


def _database_cache_key(database_path: str) -> str:
    raw = str(database_path or '')
    if raw == ':memory:' or raw.startswith('file::memory:'):
        return raw
    try:
        return str(Path(raw).expanduser().resolve())
    except Exception:
        return raw


def connect(database_path: str) -> sqlite3.Connection:
    """Abre SQLite con espera y WAL sin bloquear cada petición.

    Ejecutar ``PRAGMA journal_mode=WAL`` en *todas* las conexiones puede pedir
    un bloqueo exclusivo. Bajo un túnel, donde healthchecks y login pueden
    coincidir, ese patrón producía errores intermitentes ``database is locked``.
    El modo WAL ahora se configura una sola vez por proceso y, si la base está
    temporalmente ocupada, la conexión continúa con el modo ya existente.
    """
    timeout = 30
    if has_request_context():
        timeout = max(5, int(current_app.config.get('SQLITE_TIMEOUT_SECONDS', 30)))
    conn = sqlite3.connect(database_path, timeout=timeout)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA foreign_keys = ON')
        conn.execute(f'PRAGMA busy_timeout = {timeout * 1000}')

        cache_key = _database_cache_key(database_path)
        if cache_key not in _WAL_INITIALIZED_DATABASES:
            with _WAL_INIT_LOCK:
                if cache_key not in _WAL_INITIALIZED_DATABASES:
                    try:
                        conn.execute('PRAGMA journal_mode = WAL').fetchone()
                        _WAL_INITIALIZED_DATABASES.add(cache_key)
                    except sqlite3.OperationalError as exc:
                        message = str(exc).lower()
                        if 'locked' not in message and 'busy' not in message:
                            raise
                        # Otro request puede estar terminando una escritura. El
                        # busy_timeout seguirá protegiendo las operaciones reales.
        conn.execute('PRAGMA synchronous = NORMAL')
        return conn
    except Exception:
        conn.close()
        raise


def table_exists(cursor: sqlite3.Cursor, table: str) -> bool:
    row = cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
    return row is not None


def table_columns(cursor: sqlite3.Cursor, table: str) -> set[str]:
    try:
        return {row['name'] for row in cursor.execute(f"PRAGMA table_info({table})").fetchall()}
    except Exception:
        return set()


def ensure_column(cursor: sqlite3.Cursor, table: str, col: str, definition: str) -> None:
    if table_exists(cursor, table) and col not in table_columns(cursor, table):
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {col} {definition}")


def ensure_security_schema(database_path: str) -> None:
    conn = connect(database_path)
    cur = conn.cursor()
    cur.executescript(SEGURIDAD_SCHEMA_SQL)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS usuarios_app (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            rol TEXT NOT NULL DEFAULT 'DOCENTE',
            unidades TEXT,
            activo INTEGER DEFAULT 1,
            fecha_creacion TEXT NOT NULL,
            fecha_ultima_conexion TEXT
        )
    """)
    for col, definition in {
        'fundacion_id': 'INTEGER',
        'nombre_completo': 'TEXT',
        'telefono': 'TEXT',
        'estado': "TEXT DEFAULT 'ACTIVO'",
        'reset_token_hash': 'TEXT',
        'reset_expira': 'TEXT',
        'fecha_actualizacion': 'TEXT',
        'debe_cambiar_password': 'INTEGER DEFAULT 0',
        'eliminado_en': 'TEXT',
        'eliminado_por': 'INTEGER',
        'motivo_eliminacion': 'TEXT',
    }.items():
        ensure_column(cur, 'usuarios_app', col, definition)

    for col, definition in {
        'eliminado_en': 'TEXT',
        'eliminado_por': 'INTEGER',
        'motivo_eliminacion': 'TEXT',
    }.items():
        ensure_column(cur, 'fundaciones', col, definition)

    for col, definition in {
        'fundacion_id': 'INTEGER',
        'metodo': "TEXT DEFAULT 'EMAIL_LINK'",
        'solicitado_por': 'INTEGER',
        'ip': 'TEXT',
    }.items():
        ensure_column(cur, 'recuperacion_password', col, definition)

    for table in MULTITENANT_TABLES:
        for col, definition in MULTITENANT_COLUMNS.items():
            ensure_column(cur, table, col, definition)

    module_tables = cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND (name LIKE 'gp_%' OR name LIKE 'sn_%')"
    ).fetchall()
    for row in module_tables:
        for col, definition in MULTITENANT_COLUMNS.items():
            ensure_column(cur, row['name'], col, definition)

    now = now_iso()
    cur.execute("""
        INSERT INTO fundaciones
        (id, nombre, nit, representante, estado, plan, fecha_inicio, fecha_vencimiento, fecha_creacion)
        SELECT 1, 'Entorno de pruebas', NULL, NULL, 'ACTIVA', 'PRUEBA', ?, ?, ?
        WHERE NOT EXISTS (SELECT 1 FROM fundaciones WHERE id = 1)
    """, (now[:10], (datetime.now() + timedelta(days=3650)).date().isoformat(), now))

    for rol in ROLES_SISTEMA:
        cur.execute("""
            INSERT INTO roles_sistema (nombre, descripcion, activo, fecha_creacion)
            SELECT ?, ?, 1, ? WHERE NOT EXISTS (SELECT 1 FROM roles_sistema WHERE nombre = ?)
        """, (rol, f'Rol {rol}', now, rol))

    permisos = sorted({perm for perms in PERMISOS_BASE.values() for perm in perms})
    for perm in permisos:
        cur.execute("""
            INSERT INTO permisos_sistema (codigo, descripcion, modulo, fecha_creacion)
            SELECT ?, ?, ?, ? WHERE NOT EXISTS (SELECT 1 FROM permisos_sistema WHERE codigo = ?)
        """, (perm, perm, perm.split('.')[0] if '.' in perm else 'GLOBAL', now, perm))
    for rol, perms in PERMISOS_BASE.items():
        for perm in perms:
            cur.execute("""
                INSERT INTO rol_permiso (rol, permiso_codigo, fecha_creacion)
                SELECT ?, ?, ? WHERE NOT EXISTS (
                    SELECT 1 FROM rol_permiso WHERE rol = ? AND permiso_codigo = ?
                )
            """, (rol, perm, now, rol, perm))

    # La migración de registros históricos se ejecuta una sola vez, no en cada petición.
    for table in MULTITENANT_TABLES:
        if table_exists(cur, table) and 'fundacion_id' in table_columns(cur, table):
            try:
                cur.execute(f"UPDATE {table} SET fundacion_id = 1 WHERE fundacion_id IS NULL")
            except Exception:
                pass
    conn.commit()
    conn.close()


def password_policy_errors(password: str, minimum: int | None = None) -> list[str]:
    if minimum is None:
        minimum = int(current_app.config.get('MIN_PASSWORD_LENGTH', 12)) if has_request_context() else 12
    errors: list[str] = []
    if len(password or '') < minimum:
        errors.append(f'mínimo {minimum} caracteres')
    if not re.search(r'[A-ZÁÉÍÓÚÑ]', password or ''):
        errors.append('una mayúscula')
    if not re.search(r'[a-záéíóúñ]', password or ''):
        errors.append('una minúscula')
    if not re.search(r'\d', password or ''):
        errors.append('un número')
    if not re.search(r'[^A-Za-z0-9ÁÉÍÓÚÑáéíóúñ]', password or ''):
        errors.append('un símbolo')
    return errors


def bootstrap_initial_admin(database_path: str, config: Mapping[str, Any]) -> dict[str, Any]:
    """Crea una sola vez el administrador definido mediante variables privadas.

    Después de la primera inicialización, las variables INITIAL_ADMIN_* pueden
    retirarse: nunca se restablece una contraseña ni se eleva una cuenta existente.
    """
    ensure_security_schema(database_path)
    username = str(config.get('INITIAL_ADMIN_USERNAME', '')).strip()
    email = str(config.get('INITIAL_ADMIN_EMAIL', '')).strip()
    password = str(config.get('INITIAL_ADMIN_PASSWORD', ''))

    conn = connect(database_path)
    existing_superadmin = conn.execute(
        "SELECT id, username, email, rol FROM usuarios_app WHERE rol='SUPERADMIN' ORDER BY id LIMIT 1"
    ).fetchone()

    if not username or not email or not password:
        if existing_superadmin:
            result = {
                'created': False,
                'id': existing_superadmin['id'],
                'username': existing_superadmin['username'],
                'initial_credentials_retired': True,
            }
            conn.close()
            return result
        conn.close()
        raise RuntimeError(
            'Faltan INITIAL_ADMIN_USERNAME, INITIAL_ADMIN_EMAIL o INITIAL_ADMIN_PASSWORD '
            'y todavía no existe un SUPERADMIN.'
        )

    errors = password_policy_errors(password, int(config.get('MIN_PASSWORD_LENGTH', 12)))
    if errors:
        conn.close()
        raise RuntimeError('INITIAL_ADMIN_PASSWORD requiere ' + ', '.join(errors) + '.')

    now = now_iso()
    foundation_name = str(config.get('INITIAL_FOUNDATION_NAME', 'Entorno de pruebas')).strip() or 'Entorno de pruebas'
    conn.execute(
        "UPDATE fundaciones SET nombre=?, fecha_actualizacion=? WHERE id=1 AND nombre='Entorno de pruebas'",
        (foundation_name, now),
    )
    existing = conn.execute(
        "SELECT id, username, email, rol FROM usuarios_app WHERE lower(username)=lower(?) OR lower(email)=lower(?)",
        (username, email),
    ).fetchone()

    if existing:
        if str(existing['rol'] or '').upper() != 'SUPERADMIN':
            conn.close()
            raise RuntimeError(
                'La identidad configurada para INITIAL_ADMIN ya pertenece a una cuenta no administradora. '
                'No se promoverá automáticamente por seguridad.'
            )
        conn.commit()
        result = {'created': False, 'id': existing['id'], 'username': existing['username']}
    elif existing_superadmin:
        # Cambiar las variables después del primer despliegue no debe crear un
        # segundo SUPERADMIN silenciosamente ni restablecer credenciales.
        conn.commit()
        result = {
            'created': False,
            'id': existing_superadmin['id'],
            'username': existing_superadmin['username'],
            'configuration_mismatch': True,
        }
    else:
        cur = conn.execute("""
            INSERT INTO usuarios_app
            (username, email, password_hash, rol, fundacion_id, activo, estado, nombre_completo,
             debe_cambiar_password, fecha_creacion, fecha_actualizacion)
            VALUES (?, ?, ?, 'SUPERADMIN', 1, 1, 'ACTIVO', ?, ?, ?, ?)
        """, (
            username,
            email,
            generate_password_hash(password),
            str(config.get('INITIAL_ADMIN_NAME', 'Administrador inicial')),
            1 if bool(config.get('INITIAL_ADMIN_FORCE_PASSWORD_CHANGE', True)) else 0,
            now,
            now,
        ))
        conn.commit()
        result = {'created': True, 'id': cur.lastrowid, 'username': username}
    conn.close()
    return result


def audit(database_path: str, accion: str, tabla: str | None = None, registro_id: int | None = None,
          antes: Any = None, despues: Any = None, usuario: dict | None = None) -> None:
    try:
        usuario = usuario or getattr(g, 'current_user', None) or {}
        remote_addr = request.remote_addr if has_request_context() else None
        user_agent = request.headers.get('User-Agent') if has_request_context() else None
        conn = connect(database_path)
        conn.execute("""
            INSERT INTO auditoria_seguridad
            (usuario_id, username, fundacion_id, accion, tabla_afectada, registro_id,
             datos_anteriores, datos_nuevos, ip, user_agent, fecha)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            usuario.get('id'), usuario.get('username'), usuario.get('fundacion_id'), accion,
            tabla, registro_id,
            json.dumps(antes, ensure_ascii=False, default=str) if antes is not None else None,
            json.dumps(despues, ensure_ascii=False, default=str) if despues is not None else None,
            remote_addr, user_agent, now_iso(),
        ))
        conn.commit()
        conn.close()
    except Exception:
        pass


def user_dict(row: sqlite3.Row | Mapping[str, Any]) -> dict[str, Any]:
    data = dict(row)
    for field in (
        'password_hash', 'reset_token_hash', 'reset_expira', 'token_hash', '_token_hash',
        'session_id', '_session_id', 'sesion_activa', 'fecha_expiracion',
    ):
        data.pop(field, None)
    data['debe_cambiar_password'] = bool(data.get('debe_cambiar_password', 0))
    data['menus'] = ROLE_MENU_PERMISSIONS.get(data.get('rol'), [])
    return data


def extract_token() -> str | None:
    if not has_request_context():
        return None
    auth = request.headers.get('Authorization', '') or ''
    if auth.lower().startswith('bearer '):
        token = auth.split(' ', 1)[1].strip()
        if token:
            return token
    token = (request.headers.get('X-Auth-Token') or '').strip()
    if token:
        return token

    # Compatibilidad temporal solo para desarrollo explícito. Está prohibida en producción.
    if current_app.config.get('ALLOW_LEGACY_QUERY_TOKENS', False):
        token = (request.args.get('token') or '').strip()
        if token:
            return token
        try:
            token = (request.form.get('_auth_token') or '').strip()
            if token:
                return token
        except Exception:
            pass
    return None


def validate_token(database_path: str, token: str | None) -> dict[str, Any] | None:
    if not token:
        return None
    conn = connect(database_path)
    token_digest = hash_token(token)
    row = conn.execute("""
        SELECT s.id AS session_id, s.fecha_expiracion, s.activa AS sesion_activa,
               u.*, f.estado AS fundacion_estado, f.nombre AS fundacion_nombre
        FROM sesiones_usuario s
        JOIN usuarios_app u ON u.id = s.usuario_id
        LEFT JOIN fundaciones f ON f.id = u.fundacion_id
        WHERE s.token_hash = ? AND s.activa = 1
    """, (token_digest,)).fetchone()
    if not row:
        conn.close()
        return None
    try:
        if datetime.fromisoformat(row['fecha_expiracion']) < datetime.now():
            conn.execute("UPDATE sesiones_usuario SET activa=0, fecha_cierre=? WHERE id=?", (now_iso(), row['session_id']))
            conn.commit()
            conn.close()
            return None
    except Exception:
        conn.close()
        return None
    if int(row['activo'] or 0) != 1 or str(row['estado'] or 'ACTIVO').upper() != 'ACTIVO':
        conn.close()
        return None
    if row['rol'] != 'SUPERADMIN' and str(row['fundacion_estado'] or 'ACTIVA').upper() != 'ACTIVA':
        conn.close()
        return None
    data = dict(row)
    data['_session_id'] = row['session_id']
    data['_token_hash'] = token_digest
    conn.close()
    return data


def get_request_user_context() -> dict[str, Any]:
    user = getattr(g, 'current_user', None) or {}
    return {
        'usuario_id': user.get('id'),
        'fundacion_id': user.get('fundacion_id'),
        'rol': user.get('rol') or 'SYSTEM',
        'username': user.get('username') or 'sistema',
    }


def is_superadmin(user: dict | None = None) -> bool:
    user = user or getattr(g, 'current_user', None) or {}
    return user.get('rol') == 'SUPERADMIN'


def role_allowed_for_path(path: str, rol: str) -> bool:
    normalized = (path or '').rstrip('/') or '/'
    for prefix, roles in PATH_ROLE_RULES:
        if normalized == prefix or normalized.startswith(prefix + '/'):
            return rol in roles
    return False


def _rate_key(scope: str, identifier: str) -> str:
    ip = request.remote_addr if has_request_context() else 'unknown'
    normalized = (identifier or '').strip().lower()
    return hash_token(f'{scope}|{ip}|{normalized}')


def rate_limit_status(database_path: str, scope: str, identifier: str) -> int:
    key = _rate_key(scope, identifier)
    conn = connect(database_path)
    row = conn.execute("SELECT * FROM auth_intentos WHERE clave_hash=?", (key,)).fetchone()
    if not row:
        conn.close()
        return 0
    now = datetime.now()
    retry_after = 0
    if row['bloqueado_hasta']:
        try:
            until = datetime.fromisoformat(row['bloqueado_hasta'])
            if until > now:
                retry_after = max(1, int((until - now).total_seconds()))
        except Exception:
            pass
    conn.close()
    return retry_after


def register_rate_limit_failure(database_path: str, scope: str, identifier: str, *, maximum: int,
                                window_seconds: int, lock_seconds: int) -> int:
    key = _rate_key(scope, identifier)
    now = datetime.now()
    conn = connect(database_path)
    row = conn.execute("SELECT * FROM auth_intentos WHERE clave_hash=?", (key,)).fetchone()
    attempts = 1
    window_start = now
    if row:
        try:
            previous_start = datetime.fromisoformat(row['ventana_inicio'])
        except Exception:
            previous_start = now - timedelta(seconds=window_seconds + 1)
        if (now - previous_start).total_seconds() <= window_seconds:
            attempts = int(row['intentos'] or 0) + 1
            window_start = previous_start
    blocked_until = now + timedelta(seconds=lock_seconds) if attempts >= maximum else None
    conn.execute("""
        INSERT INTO auth_intentos
        (clave_hash, alcance, intentos, ventana_inicio, bloqueado_hasta, fecha_actualizacion)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(clave_hash) DO UPDATE SET
            alcance=excluded.alcance,
            intentos=excluded.intentos,
            ventana_inicio=excluded.ventana_inicio,
            bloqueado_hasta=excluded.bloqueado_hasta,
            fecha_actualizacion=excluded.fecha_actualizacion
    """, (
        key, scope, attempts, window_start.isoformat(timespec='seconds'),
        blocked_until.isoformat(timespec='seconds') if blocked_until else None,
        now.isoformat(timespec='seconds'),
    ))
    conn.commit()
    conn.close()
    return lock_seconds if blocked_until else 0


def clear_rate_limit(database_path: str, scope: str, identifier: str) -> None:
    conn = connect(database_path)
    conn.execute("DELETE FROM auth_intentos WHERE clave_hash=?", (_rate_key(scope, identifier),))
    conn.commit()
    conn.close()


def invalidate_user_sessions(database_path: str, user_id: int) -> None:
    conn = connect(database_path)
    conn.execute(
        "UPDATE sesiones_usuario SET activa=0, fecha_cierre=? WHERE usuario_id=? AND activa=1",
        (now_iso(), user_id),
    )
    conn.commit()
    conn.close()


def build_password_reset_url(token: str) -> str:
    base = str(current_app.config.get('PASSWORD_RESET_PUBLIC_URL') or current_app.config.get('PUBLIC_APP_URL') or '').rstrip('/')

    # Un Quick Tunnel se crea después de iniciar Flask. Por eso, en modo túnel
    # el enlace se resuelve en el momento de la solicitud desde el archivo que
    # genera el script de Windows, sin almacenar el token en ese archivo.
    if bool(current_app.config.get('PUBLIC_TUNNEL_MODE', False)):
        try:
            project_dir = Path(str(current_app.config.get('PROJECT_DIR') or '')).resolve()
            link_file = project_dir / 'ENLACE_PUBLICO_TUNEL.txt'
            if link_file.is_file():
                content = link_file.read_text(encoding='utf-8', errors='ignore')
                match = re.search(r'(?im)^Base:\s*(https://[a-z0-9-]+\.trycloudflare\.com)\s*$', content)
                if match:
                    base = match.group(1).rstrip('/')
        except Exception:
            pass

    if not base:
        return ''
    return f"{base}/#restablecer?reset_token={urllib.parse.quote(token)}"


def send_password_reset_email(recipient: str, reset_url: str) -> bool:
    api_key = str(current_app.config.get('RESEND_API_KEY') or '').strip()
    from_email = str(current_app.config.get('PASSWORD_RESET_FROM_EMAIL') or '').strip()
    if not api_key or not from_email or not recipient or not reset_url:
        return False
    body = {
        'from': from_email,
        'to': [recipient],
        'subject': 'Restablecimiento de contraseña - PrimeraInfancia',
        'html': (
            '<p>Se solicitó restablecer tu contraseña.</p>'
            f'<p><a href="{html.escape(reset_url, quote=True)}">Crear una nueva contraseña</a></p>'
            '<p>El enlace es de un solo uso y vence pronto. Si no hiciste la solicitud, ignora este mensaje.</p>'
        ),
    }
    req = urllib.request.Request(
        'https://api.resend.com/emails',
        data=json.dumps(body).encode('utf-8'),
        headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'},
        method='POST',
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            return 200 <= int(response.status) < 300
    except (urllib.error.URLError, TimeoutError, ValueError):
        return False


def activate_security_guard(app, database_path: str) -> None:
    ensure_security_schema(database_path)

    @app.before_request
    def _security_before_request():
        normalized_path = request.path.rstrip('/') or '/'
        forwarded_proto = request.headers.get('X-Forwarded-Proto', '').split(',')[0].strip().lower()
        if (
            current_app.config.get('FORCE_HTTPS', False)
            and normalized_path != '/api/health'
            and not request.is_secure
            and forwarded_proto != 'https'
        ):
            # Railway termina TLS en el proxy. ProxyFix reconstruye el esquema
            # externo; este 308 cubre accesos HTTP directos sin romper el healthcheck.
            secure_url = request.url.replace('http://', 'https://', 1)
            return redirect(secure_url, code=308)

        if not request.path.startswith('/api/') or request.method == 'OPTIONS':
            return None
        if normalized_path in PUBLIC_PATHS:
            return None
        token = extract_token()
        if not token:
            return jsonify({
                'error': 'Debe iniciar sesión para realizar esta acción.',
                'code': 'AUTH_TOKEN_MISSING',
            }), 401
        user = validate_token(database_path, token)
        if not user:
            return jsonify({
                'error': 'Sesión expirada o token inválido. Inicia sesión nuevamente.',
                'code': 'AUTH_TOKEN_INVALID',
            }), 401

        g.current_user = user
        g.current_fundacion_id = user.get('fundacion_id')
        g.current_session_id = user.get('_session_id')

        if bool(user.get('debe_cambiar_password')) and normalized_path not in PASSWORD_CHANGE_ALLOWED_PATHS:
            return jsonify({
                'error': 'Debes cambiar la contraseña inicial antes de continuar.',
                'code': 'PASSWORD_CHANGE_REQUIRED',
            }), 403
        if not role_allowed_for_path(normalized_path, str(user.get('rol') or '')):
            audit(database_path, 'ACCESO_DENEGADO', despues={'path': normalized_path, 'rol': user.get('rol')}, usuario=user)
            return jsonify({'error': 'No tienes permiso para acceder a esta función.', 'code': 'ROLE_FORBIDDEN'}), 403
        return None

    @app.after_request
    def _security_after_request(response):
        response.headers.setdefault('X-Content-Type-Options', 'nosniff')
        response.headers.setdefault('X-Frame-Options', 'DENY')
        response.headers.setdefault('Referrer-Policy', 'no-referrer')
        response.headers.setdefault('Permissions-Policy', 'camera=(), microphone=(), geolocation=()')
        response.headers.setdefault('Cross-Origin-Opener-Policy', 'same-origin')
        connect_src = "'self'"
        if str(current_app.config.get('APP_ENV', '')).lower() != 'production':
            connect_src += ' http://127.0.0.1:5000 http://localhost:5000'
        response.headers.setdefault(
            'Content-Security-Policy',
            "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com https://unpkg.com; "
            "style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self' data:; "
            f"connect-src {connect_src}; object-src 'none'; base-uri 'self'; "
            "frame-ancestors 'none'; form-action 'self'",
        )
        # Las respuestas API pueden contener datos personales o tokens; no deben
        # almacenarse en cachés compartidas ni en el navegador.
        if request.path.startswith('/api/'):
            response.headers.setdefault('Cache-Control', 'no-store')
            response.headers.setdefault('Pragma', 'no-cache')
        forwarded_proto = request.headers.get('X-Forwarded-Proto', '').lower()
        if request.is_secure or forwarded_proto == 'https':
            response.headers.setdefault('Strict-Transport-Security', 'max-age=31536000; includeSubDomains')

        # Compatibilidad desactivada por defecto. Nunca se ejecuta en la entrega Railway.
        if current_app.config.get('ENABLE_LEGACY_TENANT_BACKFILL', False):
            user = getattr(g, 'current_user', None)
            if user and request.path.startswith('/api/'):
                try:
                    conn = connect(database_path)
                    cur = conn.cursor()
                    for row in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall():
                        table = row['name']
                        cols = table_columns(cur, table)
                        if 'fundacion_id' in cols:
                            cur.execute(
                                f"UPDATE {table} SET fundacion_id=COALESCE(fundacion_id, ?) WHERE fundacion_id IS NULL",
                                (user.get('fundacion_id'),),
                            )
                    conn.commit()
                    conn.close()
                except Exception:
                    pass
        return response


def require_roles(*roles: str):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            user = getattr(g, 'current_user', None)
            if not user:
                return jsonify({'error': 'Autenticación requerida.'}), 401
            if user.get('rol') not in roles:
                return jsonify({'error': 'No tienes permiso para esta acción.'}), 403
            return fn(*args, **kwargs)
        return wrapper
    return decorator


def create_session(database_path: str, usuario: sqlite3.Row) -> tuple[str, dict[str, Any]]:
    token = secrets.token_urlsafe(48)
    minutes = max(15, int(current_app.config.get('SESSION_LIFETIME_MINUTES', 720)))
    exp = datetime.now() + timedelta(minutes=minutes)
    conn = connect(database_path)
    conn.execute("DELETE FROM sesiones_usuario WHERE activa=0 OR fecha_expiracion < ?", (now_iso(),))
    conn.execute("""
        INSERT INTO sesiones_usuario
        (usuario_id, fundacion_id, token_hash, ip, user_agent, activa, fecha_creacion, fecha_expiracion)
        VALUES (?, ?, ?, ?, ?, 1, ?, ?)
    """, (
        usuario['id'], usuario['fundacion_id'], hash_token(token),
        request.remote_addr if has_request_context() else None,
        request.headers.get('User-Agent') if has_request_context() else None,
        now_iso(), exp.isoformat(timespec='seconds'),
    ))
    conn.execute(
        "UPDATE usuarios_app SET fecha_ultima_conexion=?, fecha_actualizacion=? WHERE id=?",
        (now_iso(), now_iso(), usuario['id']),
    )
    conn.commit()
    row = conn.execute("""
        SELECT u.*, f.estado AS fundacion_estado, f.nombre AS fundacion_nombre
        FROM usuarios_app u LEFT JOIN fundaciones f ON f.id = u.fundacion_id WHERE u.id=?
    """, (usuario['id'],)).fetchone()
    conn.close()
    payload = user_dict(row)
    payload['expira'] = exp.isoformat(timespec='seconds')
    return token, payload
