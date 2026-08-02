from __future__ import annotations

from flask import Blueprint, g, jsonify, request

from modules.seguridad.services import require_roles

from .schema import DEFAULT_UI_SETTINGS, PRESETS
from .services import audit_ux, get_settings, init_schema, reset_settings, save_settings


ALL_ROLES = (
    'SUPERADMIN', 'GERENTE', 'COORDINADOR', 'DOCENTE', 'NUTRICIONISTA',
    'PSICOSOCIAL', 'AUXILIAR_ADMINISTRATIVO'
)


def user_ctx() -> dict:
    user = getattr(g, 'current_user', {}) or {}
    return {
        'usuario_id': user.get('id'),
        'fundacion_id': int(user.get('fundacion_id') or 1),
        'rol': user.get('rol') or 'DOCENTE',
        'username': user.get('username') or 'sistema',
        'raw': user,
    }


def register_ajustes_ui(app, database_path: str, project_root: str) -> None:
    init_schema(database_path)
    bp = Blueprint('ajustes_ui', __name__, url_prefix='/api/ajustes-ui')

    @bp.before_request
    def _ensure_schema():
        init_schema(database_path)

    @bp.route('', methods=['GET'])
    @require_roles(*ALL_ROLES)
    def obtener_ajustes():
        ctx = user_ctx()
        return jsonify({
            'settings': get_settings(database_path, ctx['fundacion_id']),
            'defaults': DEFAULT_UI_SETTINGS,
            'presets': PRESETS,
            'fundacion_id': ctx['fundacion_id'],
        })

    @bp.route('', methods=['POST'])
    @require_roles('SUPERADMIN', 'GERENTE')
    def guardar_ajustes():
        ctx = user_ctx()
        data = request.get_json(silent=True) or {}
        settings = save_settings(database_path, ctx['fundacion_id'], ctx['usuario_id'], data, request.remote_addr)
        return jsonify({'message': 'Ajustes visuales guardados correctamente.', 'settings': settings})

    @bp.route('/restablecer', methods=['POST'])
    @require_roles('SUPERADMIN', 'GERENTE')
    def restablecer_ajustes():
        ctx = user_ctx()
        settings = reset_settings(database_path, ctx['fundacion_id'], ctx['usuario_id'], request.remote_addr)
        return jsonify({'message': 'Ajustes visuales restablecidos.', 'settings': settings})

    @bp.route('/auditoria-ux', methods=['GET'])
    @require_roles('SUPERADMIN', 'GERENTE')
    def auditoria_ux():
        return jsonify(audit_ux(project_root))

    app.register_blueprint(bp)
