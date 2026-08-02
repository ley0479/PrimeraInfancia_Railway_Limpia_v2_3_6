from __future__ import annotations

import secrets
import sqlite3
from datetime import datetime, timedelta

from flask import jsonify, request, g
from werkzeug.security import generate_password_hash, check_password_hash

from .schema import ROLES_SISTEMA
from .services import (
    audit,
    clear_rate_limit,
    connect,
    create_session,
    ensure_security_schema,
    extract_token,
    get_request_user_context,
    hash_token,
    invalidate_user_sessions,
    is_superadmin,
    now_iso,
    password_policy_errors,
    rate_limit_status,
    register_rate_limit_failure,
    require_roles,
    send_password_reset_email,
    build_password_reset_url,
    user_dict,
)


def payload() -> dict:
    return request.get_json(silent=True) or {}


def _rate_limited_response(seconds: int):
    response = jsonify({
        'error': 'Demasiados intentos. Intenta nuevamente más tarde.',
        'code': 'RATE_LIMITED',
        'retry_after': seconds,
    })
    response.status_code = 429
    response.headers['Retry-After'] = str(max(1, seconds))
    return response


def _password_error(password: str):
    errors = password_policy_errors(password)
    if not errors:
        return None
    return jsonify({
        'error': 'La contraseña requiere ' + ', '.join(errors) + '.',
        'code': 'WEAK_PASSWORD',
    }), 400


def register_seguridad(app, database_path: str) -> None:
    ensure_security_schema(database_path)

    def single_tenant_mode() -> bool:
        return bool(app.config.get('SINGLE_TENANT_MODE', True))

    @app.route('/api/auth/login', methods=['POST'])
    def auth_login_seguro():
        data = payload()
        username = (data.get('username') or data.get('email') or '').strip()
        password = data.get('password') or ''
        if not username or not password:
            return jsonify({'error': 'Usuario/correo y contraseña requeridos.'}), 400

        retry_after = rate_limit_status(database_path, 'login', username)
        if retry_after:
            return _rate_limited_response(retry_after)

        conn = connect(database_path)
        usuario = conn.execute("""
            SELECT u.*, f.estado AS fundacion_estado, f.nombre AS fundacion_nombre
            FROM usuarios_app u LEFT JOIN fundaciones f ON f.id = u.fundacion_id
            WHERE lower(u.username)=lower(?) OR lower(u.email)=lower(?)
        """, (username, username)).fetchone()
        conn.close()

        if not usuario or not check_password_hash(usuario['password_hash'], password):
            blocked = register_rate_limit_failure(
                database_path,
                'login',
                username,
                maximum=max(1, int(app.config.get('LOGIN_MAX_ATTEMPTS', 5))),
                window_seconds=max(60, int(app.config.get('LOGIN_WINDOW_SECONDS', 900))),
                lock_seconds=max(60, int(app.config.get('LOGIN_LOCK_SECONDS', 900))),
            )
            audit(database_path, 'LOGIN_FALLIDO', despues={'identificador_hash': hash_token(username.lower())})
            if blocked:
                return _rate_limited_response(blocked)
            return jsonify({'error': 'Credenciales inválidas.'}), 401

        if int(usuario['activo'] or 0) != 1 or str(usuario['estado'] or 'ACTIVO').upper() != 'ACTIVO':
            audit(database_path, 'LOGIN_USUARIO_INACTIVO', despues={'usuario_id': usuario['id']})
            return jsonify({'error': 'Usuario inactivo o suspendido.'}), 403
        if usuario['rol'] != 'SUPERADMIN' and str(usuario['fundacion_estado'] or 'ACTIVA').upper() != 'ACTIVA':
            audit(database_path, 'LOGIN_FUNDACION_SUSPENDIDA', despues={'usuario_id': usuario['id'], 'fundacion_id': usuario['fundacion_id']})
            return jsonify({'error': 'La fundación está suspendida o vencida.'}), 403

        clear_rate_limit(database_path, 'login', username)
        token, user_payload = create_session(database_path, usuario)
        try:
            from modules.facturacion_suscripcion.repository import BillingRepository
            from modules.facturacion_suscripcion.services import BillingService
            billing_service = BillingService(BillingRepository(database_path))
            billing_service.init()
            if user_payload.get('fundacion_id'):
                user_payload['suscripcion'] = billing_service.get_subscription(int(user_payload['fundacion_id']))
        except Exception:
            pass
        audit(database_path, 'LOGIN_EXITOSO', usuario=user_payload)
        return jsonify({'token': token, 'usuario': user_payload})

    @app.route('/api/auth/me', methods=['GET'])
    def auth_me():
        usuario = user_dict(getattr(g, 'current_user', None) or {})
        if usuario.get('fundacion_id'):
            try:
                from modules.facturacion_suscripcion.repository import BillingRepository
                from modules.facturacion_suscripcion.services import BillingService
                billing_service = BillingService(BillingRepository(database_path))
                billing_service.init()
                usuario['suscripcion'] = billing_service.get_subscription(int(usuario['fundacion_id']))
            except Exception:
                pass
        return jsonify({'usuario': usuario})

    @app.route('/api/auth/logout', methods=['POST'])
    def auth_logout():
        session_id = getattr(g, 'current_session_id', None)
        conn = connect(database_path)
        if session_id:
            conn.execute(
                "UPDATE sesiones_usuario SET activa=0, fecha_cierre=? WHERE id=?",
                (now_iso(), session_id),
            )
        else:
            token = extract_token()
            if token:
                conn.execute(
                    "UPDATE sesiones_usuario SET activa=0, fecha_cierre=? WHERE token_hash=?",
                    (now_iso(), hash_token(token)),
                )
        conn.commit()
        conn.close()
        audit(database_path, 'LOGOUT')
        return jsonify({'message': 'Sesión cerrada correctamente.'})

    @app.route('/api/auth/recuperar', methods=['POST'])
    def auth_recuperar():
        generic_message = 'Si la cuenta existe y tiene recuperación configurada, recibirás un enlace de un solo uso.'
        data = payload()
        identifier = (data.get('email') or data.get('username') or '').strip()
        if not identifier:
            return jsonify({'message': generic_message})

        retry_after = rate_limit_status(database_path, 'recovery', identifier)
        if retry_after:
            return _rate_limited_response(retry_after)
        blocked = register_rate_limit_failure(
            database_path,
            'recovery',
            identifier,
            maximum=max(1, int(app.config.get('RECOVERY_MAX_ATTEMPTS', 5))),
            window_seconds=max(60, int(app.config.get('RECOVERY_WINDOW_SECONDS', 3600))),
            lock_seconds=max(60, int(app.config.get('RECOVERY_LOCK_SECONDS', 3600))),
        )

        conn = connect(database_path)
        usuario = conn.execute(
            "SELECT * FROM usuarios_app WHERE lower(email)=lower(?) OR lower(username)=lower(?)",
            (identifier, identifier),
        ).fetchone()
        if not usuario:
            conn.close()
            return jsonify({'message': generic_message})

        token = secrets.token_urlsafe(40)
        exp = datetime.now() + timedelta(minutes=max(10, int(app.config.get('PASSWORD_RESET_EXPIRES_MINUTES', 30))))
        conn.execute("UPDATE recuperacion_password SET usado=1 WHERE usuario_id=? AND usado=0", (usuario['id'],))
        cur = conn.execute("""
            INSERT INTO recuperacion_password (usuario_id, token_hash, usado, fecha_creacion, fecha_expiracion)
            VALUES (?, ?, 0, ?, ?)
        """, (usuario['id'], hash_token(token), now_iso(), exp.isoformat(timespec='seconds')))
        reset_request_id = cur.lastrowid
        conn.commit()
        conn.close()

        reset_url = build_password_reset_url(token)
        delivered = send_password_reset_email(usuario['email'], reset_url)
        debug_token_allowed = bool(app.config.get('ALLOW_PASSWORD_RESET_TOKEN_RESPONSE', False)) and app.config.get('APP_ENV') != 'production'
        if not delivered and not debug_token_allowed:
            conn = connect(database_path)
            conn.execute("UPDATE recuperacion_password SET usado=1 WHERE id=?", (reset_request_id,))
            conn.commit()
            conn.close()
            audit(database_path, 'RECUPERACION_NO_ENVIADA', despues={'usuario_id': usuario['id']})
        else:
            audit(database_path, 'RECUPERAR_PASSWORD', despues={'usuario_id': usuario['id'], 'correo_enviado': delivered})

        response = {'message': generic_message}
        if debug_token_allowed:
            response['development_reset_token'] = token
            response['expira'] = exp.isoformat(timespec='seconds')
        if blocked:
            response['proximo_intento_en'] = blocked
        return jsonify(response)

    @app.route('/api/auth/restablecer', methods=['POST'])
    def auth_restablecer():
        data = payload()
        token = str(data.get('token') or '').strip()
        password = data.get('password') or ''
        if not token:
            return jsonify({'error': 'Token requerido.'}), 400
        weak = _password_error(password)
        if weak:
            return weak

        conn = connect(database_path)
        rec = conn.execute(
            "SELECT * FROM recuperacion_password WHERE token_hash=? AND usado=0",
            (hash_token(token),),
        ).fetchone()
        if not rec:
            conn.close()
            return jsonify({'error': 'Token inválido, usado o vencido.'}), 400
        try:
            if datetime.fromisoformat(rec['fecha_expiracion']) < datetime.now():
                conn.execute("UPDATE recuperacion_password SET usado=1 WHERE id=?", (rec['id'],))
                conn.commit()
                conn.close()
                return jsonify({'error': 'Token inválido, usado o vencido.'}), 400
        except Exception:
            conn.close()
            return jsonify({'error': 'Token inválido, usado o vencido.'}), 400

        conn.execute(
            "UPDATE usuarios_app SET password_hash=?, debe_cambiar_password=0, fecha_actualizacion=? WHERE id=?",
            (generate_password_hash(password), now_iso(), rec['usuario_id']),
        )
        conn.execute("UPDATE recuperacion_password SET usado=1 WHERE usuario_id=?", (rec['usuario_id'],))
        conn.execute(
            "UPDATE sesiones_usuario SET activa=0, fecha_cierre=? WHERE usuario_id=? AND activa=1",
            (now_iso(), rec['usuario_id']),
        )
        conn.commit()
        conn.close()
        audit(database_path, 'PASSWORD_RESTABLECIDO', despues={'usuario_id': rec['usuario_id']})
        return jsonify({'message': 'Contraseña actualizada. Inicia sesión nuevamente.'})

    @app.route('/api/auth/cambiar-password', methods=['POST'])
    def auth_cambiar_password():
        user = getattr(g, 'current_user', {})
        data = payload()
        current_password = data.get('password_actual') or ''
        new_password = data.get('password_nueva') or ''
        weak = _password_error(new_password)
        if weak:
            return weak
        conn = connect(database_path)
        row = conn.execute("SELECT * FROM usuarios_app WHERE id=?", (user.get('id'),)).fetchone()
        if not row or not check_password_hash(row['password_hash'], current_password):
            conn.close()
            return jsonify({'error': 'La contraseña actual no es correcta.'}), 400
        if check_password_hash(row['password_hash'], new_password):
            conn.close()
            return jsonify({'error': 'La nueva contraseña debe ser diferente.'}), 400
        conn.execute(
            "UPDATE usuarios_app SET password_hash=?, debe_cambiar_password=0, fecha_actualizacion=? WHERE id=?",
            (generate_password_hash(new_password), now_iso(), row['id']),
        )
        conn.execute(
            "UPDATE sesiones_usuario SET activa=0, fecha_cierre=? WHERE usuario_id=? AND activa=1",
            (now_iso(), row['id']),
        )
        conn.commit()
        conn.close()
        audit(database_path, 'PASSWORD_CAMBIADO', despues={'usuario_id': row['id']})
        return jsonify({'message': 'Contraseña cambiada. Inicia sesión nuevamente.', 'reauthenticate': True})

    @app.route('/api/fundaciones', methods=['GET', 'POST'])
    def fundaciones():
        user = getattr(g, 'current_user', {})
        conn = connect(database_path)
        if request.method == 'GET':
            if single_tenant_mode():
                filas = conn.execute("SELECT * FROM fundaciones WHERE id=1").fetchall()
            elif user.get('rol') == 'SUPERADMIN':
                filas = conn.execute("SELECT * FROM fundaciones ORDER BY nombre").fetchall()
            else:
                filas = conn.execute("SELECT * FROM fundaciones WHERE id=?", (user.get('fundacion_id'),)).fetchall()
            conn.close()
            return jsonify({'fundaciones': [dict(f) for f in filas], 'single_tenant_mode': single_tenant_mode()})
        if single_tenant_mode():
            conn.close()
            return jsonify({
                'error': 'Esta entrega segura funciona con una sola fundación. La creación multi-fundación está desactivada.',
                'code': 'SINGLE_TENANT_MODE',
            }), 403
        if user.get('rol') != 'SUPERADMIN':
            conn.close()
            return jsonify({'error': 'Solo SUPERADMIN puede crear fundaciones.'}), 403
        data = payload()
        nombre = (data.get('nombre') or '').strip()
        if not nombre:
            conn.close()
            return jsonify({'error': 'Nombre de fundación requerido.'}), 400
        now = now_iso()
        try:
            cur = conn.execute("""
                INSERT INTO fundaciones
                (nombre, nit, representante, email, telefono, direccion, municipio, departamento, estado, plan, fecha_inicio, fecha_vencimiento, observaciones, fecha_creacion, fecha_actualizacion)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                nombre, data.get('nit'), data.get('representante'), data.get('email'), data.get('telefono'),
                data.get('direccion'), data.get('municipio'), data.get('departamento'), data.get('estado', 'ACTIVA'),
                data.get('plan', 'PRUEBA'), data.get('fecha_inicio') or now[:10], data.get('fecha_vencimiento'),
                data.get('observaciones'), now, now
            ))
            conn.commit()
            fid = cur.lastrowid
            fundacion = conn.execute("SELECT * FROM fundaciones WHERE id=?", (fid,)).fetchone()
            conn.close()
            audit(database_path, 'CREAR_FUNDACION', 'fundaciones', fid, despues=dict(fundacion))
            return jsonify({'message': 'Fundación creada correctamente.', 'fundacion': dict(fundacion)}), 201
        except sqlite3.IntegrityError:
            conn.close()
            return jsonify({'error': 'Ya existe una fundación con ese nombre.'}), 409

    @app.route('/api/fundaciones/<int:fundacion_id>', methods=['PUT', 'DELETE'])
    @require_roles('SUPERADMIN')
    def fundacion_detalle(fundacion_id: int):
        if single_tenant_mode() and fundacion_id != 1:
            return jsonify({'error': 'Fundación no disponible en modo de una sola fundación.', 'code': 'SINGLE_TENANT_MODE'}), 404
        if single_tenant_mode() and request.method == 'DELETE':
            return jsonify({'error': 'No se puede suspender la única fundación del entorno.', 'code': 'SINGLE_TENANT_MODE'}), 403
        conn = connect(database_path)
        actual = conn.execute("SELECT * FROM fundaciones WHERE id=?", (fundacion_id,)).fetchone()
        if not actual:
            conn.close()
            return jsonify({'error': 'Fundación no encontrada.'}), 404
        if request.method == 'DELETE':
            nuevo_estado = request.args.get('estado', 'SUSPENDIDA').upper()
            conn.execute("UPDATE fundaciones SET estado=?, fecha_actualizacion=? WHERE id=?", (nuevo_estado, now_iso(), fundacion_id))
            conn.commit()
            conn.close()
            audit(database_path, 'CAMBIAR_ESTADO_FUNDACION', 'fundaciones', fundacion_id, antes=dict(actual), despues={'estado': nuevo_estado})
            return jsonify({'message': f'Fundación actualizada a estado {nuevo_estado}.'})
        data = payload()
        campos = ['nombre','nit','representante','email','telefono','direccion','municipio','departamento','estado','plan','fecha_inicio','fecha_vencimiento','observaciones']
        valores = {c: data.get(c, actual[c]) for c in campos}
        conn.execute("""
            UPDATE fundaciones
            SET nombre=?, nit=?, representante=?, email=?, telefono=?, direccion=?, municipio=?, departamento=?,
                estado=?, plan=?, fecha_inicio=?, fecha_vencimiento=?, observaciones=?, fecha_actualizacion=?
            WHERE id=?
        """, tuple(valores[c] for c in campos) + (now_iso(), fundacion_id))
        conn.commit()
        actualizado = conn.execute("SELECT * FROM fundaciones WHERE id=?", (fundacion_id,)).fetchone()
        conn.close()
        audit(database_path, 'EDITAR_FUNDACION', 'fundaciones', fundacion_id, antes=dict(actual), despues=dict(actualizado))
        return jsonify({'message': 'Fundación actualizada.', 'fundacion': dict(actualizado)})

    @app.route('/api/usuarios', methods=['GET', 'POST'])
    def usuarios():
        user = getattr(g, 'current_user', {})
        conn = connect(database_path)
        if request.method == 'GET':
            if user.get('rol') == 'SUPERADMIN' and not single_tenant_mode():
                filas = conn.execute("""
                    SELECT u.id, u.username, u.email, u.rol, u.fundacion_id, u.activo, u.estado, u.nombre_completo,
                           u.telefono, u.fecha_creacion, u.fecha_ultima_conexion, f.nombre AS fundacion_nombre
                    FROM usuarios_app u LEFT JOIN fundaciones f ON f.id = u.fundacion_id
                    ORDER BY f.nombre, u.username
                """).fetchall()
            else:
                filas = conn.execute("""
                    SELECT u.id, u.username, u.email, u.rol, u.fundacion_id, u.activo, u.estado, u.nombre_completo,
                           u.telefono, u.fecha_creacion, u.fecha_ultima_conexion, f.nombre AS fundacion_nombre
                    FROM usuarios_app u LEFT JOIN fundaciones f ON f.id = u.fundacion_id
                    WHERE u.fundacion_id=? ORDER BY u.username
                """, (user.get('fundacion_id'),)).fetchall()
            conn.close()
            return jsonify({'usuarios': [dict(f) for f in filas], 'roles': ROLES_SISTEMA})
        data = payload()
        for campo in ['username', 'email', 'password', 'rol']:
            if not data.get(campo):
                conn.close()
                return jsonify({'error': f'{campo} requerido.'}), 400
        weak = _password_error(str(data.get('password') or ''))
        if weak:
            conn.close()
            return weak
        rol = data.get('rol')
        if rol not in ROLES_SISTEMA:
            conn.close()
            return jsonify({'error': 'Rol inválido.'}), 400
        fundacion_id = 1 if single_tenant_mode() else (data.get('fundacion_id') or user.get('fundacion_id'))
        if user.get('rol') != 'SUPERADMIN':
            fundacion_id = user.get('fundacion_id')
            if rol == 'SUPERADMIN':
                conn.close()
                return jsonify({'error': 'No puedes crear usuarios SUPERADMIN.'}), 403
        now = now_iso()
        try:
            cur = conn.execute("""
                INSERT INTO usuarios_app
                (username, email, password_hash, rol, fundacion_id, activo, estado, nombre_completo, telefono, fecha_creacion, fecha_actualizacion)
                VALUES (?, ?, ?, ?, ?, 1, 'ACTIVO', ?, ?, ?, ?)
            """, (
                data['username'].strip(), data['email'].strip(), generate_password_hash(data['password']), rol,
                fundacion_id, data.get('nombre_completo') or data.get('username'), data.get('telefono'), now, now
            ))
            conn.commit()
            uid = cur.lastrowid
            nuevo = conn.execute("SELECT id, username, email, rol, fundacion_id, activo, estado, nombre_completo, telefono FROM usuarios_app WHERE id=?", (uid,)).fetchone()
            conn.close()
            audit(database_path, 'CREAR_USUARIO', 'usuarios_app', uid, despues=dict(nuevo))
            return jsonify({'message': 'Usuario creado correctamente.', 'usuario': dict(nuevo)}), 201
        except sqlite3.IntegrityError:
            conn.close()
            return jsonify({'error': 'Usuario o correo ya existe.'}), 409

    @app.route('/api/usuarios/<int:usuario_id>', methods=['PUT', 'DELETE'])
    def usuario_detalle(usuario_id: int):
        user = getattr(g, 'current_user', {})
        conn = connect(database_path)
        actual = conn.execute("SELECT * FROM usuarios_app WHERE id=?", (usuario_id,)).fetchone()
        if not actual:
            conn.close()
            return jsonify({'error': 'Usuario no encontrado.'}), 404
        if user.get('rol') != 'SUPERADMIN' and actual['fundacion_id'] != user.get('fundacion_id'):
            conn.close()
            return jsonify({'error': 'No puedes modificar usuarios de otra fundación.'}), 403
        if request.method == 'DELETE':
            if int(user.get('id') or 0) == usuario_id:
                conn.close()
                return jsonify({'error': 'No puedes desactivar tu propia cuenta.'}), 400
            estado = request.args.get('estado', 'INACTIVO').upper()
            conn.execute("UPDATE usuarios_app SET activo=0, estado=?, fecha_actualizacion=? WHERE id=?", (estado, now_iso(), usuario_id))
            conn.execute("UPDATE sesiones_usuario SET activa=0, fecha_cierre=? WHERE usuario_id=? AND activa=1", (now_iso(), usuario_id))
            conn.commit()
            conn.close()
            audit(database_path, 'DESACTIVAR_USUARIO', 'usuarios_app', usuario_id, antes=dict(actual), despues={'estado': estado})
            return jsonify({'message': 'Usuario desactivado correctamente.'})
        data = payload()
        rol = data.get('rol', actual['rol'])
        if rol not in ROLES_SISTEMA:
            conn.close()
            return jsonify({'error': 'Rol inválido.'}), 400
        fundacion_id = (
            1 if single_tenant_mode()
            else (data.get('fundacion_id', actual['fundacion_id']) if user.get('rol') == 'SUPERADMIN' else actual['fundacion_id'])
        )
        password_sql = ''
        params_extra = []
        if data.get('password'):
            weak = _password_error(str(data.get('password') or ''))
            if weak:
                conn.close()
                return weak
            password_sql = ', password_hash=?, debe_cambiar_password=0'
            params_extra.append(generate_password_hash(data['password']))
        params = [
            data.get('username', actual['username']), data.get('email', actual['email']), rol, fundacion_id,
            int(data.get('activo', actual['activo'])), data.get('estado', actual['estado'] or 'ACTIVO'),
            data.get('nombre_completo', actual['nombre_completo']), data.get('telefono', actual['telefono'])
        ] + params_extra + [now_iso(), usuario_id]
        conn.execute(f"""
            UPDATE usuarios_app
            SET username=?, email=?, rol=?, fundacion_id=?, activo=?, estado=?, nombre_completo=?, telefono=?{password_sql}, fecha_actualizacion=?
            WHERE id=?
        """, tuple(params))
        conn.commit()
        nuevo = conn.execute("SELECT id, username, email, rol, fundacion_id, activo, estado, nombre_completo, telefono FROM usuarios_app WHERE id=?", (usuario_id,)).fetchone()
        conn.close()
        audit(database_path, 'EDITAR_USUARIO', 'usuarios_app', usuario_id, antes=dict(actual), despues=dict(nuevo))
        return jsonify({'message': 'Usuario actualizado.', 'usuario': dict(nuevo)})

    @app.route('/api/roles', methods=['GET'])
    def roles():
        return jsonify({'roles': ROLES_SISTEMA})

    @app.route('/api/seguridad/auditoria', methods=['GET'])
    @require_roles('SUPERADMIN', 'GERENTE')
    def auditoria_seguridad():
        user = getattr(g, 'current_user', {})
        conn = connect(database_path)
        if user.get('rol') == 'SUPERADMIN':
            filas = conn.execute("SELECT * FROM auditoria_seguridad ORDER BY fecha DESC LIMIT 300").fetchall()
        else:
            filas = conn.execute("SELECT * FROM auditoria_seguridad WHERE fundacion_id=? ORDER BY fecha DESC LIMIT 300", (user.get('fundacion_id'),)).fetchall()
        conn.close()
        return jsonify({'auditoria': [dict(f) for f in filas]})
