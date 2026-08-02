from __future__ import annotations

import os
from datetime import datetime

from flask import Blueprint, g, jsonify, request, send_file

from modules.seguridad.services import require_roles
from .services import ReportesGerencialesService

ALLOWED_ROLES = ('SUPERADMIN', 'GERENTE', 'COORDINADOR', 'AUXILIAR_ADMINISTRATIVO')


def current_user() -> dict:
    user = getattr(g, 'current_user', {}) or {}
    return {
        'id': user.get('id') or user.get('usuario_id'),
        'username': user.get('username') or user.get('email') or 'sistema',
        'rol': user.get('rol') or 'SUPERADMIN',
        'fundacion_id': int(user.get('fundacion_id') or 1),
        'raw': user,
    }


def register_reportes_gerenciales(app, database_path: str, output_folder: str) -> None:
    service = ReportesGerencialesService(database_path, output_folder)
    service.init_schema()

    bp = Blueprint('reportes_gerenciales', __name__, url_prefix='/api/reportes-gerenciales')

    @bp.before_request
    def _ensure_schema():
        service.init_schema()

    @bp.route('/dashboard', methods=['GET'])
    @require_roles(*ALLOWED_ROLES)
    def dashboard():
        user = current_user()
        return jsonify(service.dashboard(user.get('fundacion_id')))

    @bp.route('/generar', methods=['POST'])
    @require_roles(*ALLOWED_ROLES)
    def generar():
        payload = request.get_json(silent=True) or request.form.to_dict() or {}
        hoy = datetime.now()
        mes = int(payload.get('mes') or payload.get('month') or hoy.month)
        anio = int(payload.get('anio') or payload.get('año') or payload.get('year') or hoy.year)
        try:
            resultado = service.generar_reporte_ejecutivo(mes, anio, current_user(), registrar=True)
            data = resultado.get('data') or {}
            return jsonify({
                'message': 'Reporte gerencial ejecutivo generado correctamente.',
                'reporte': {
                    'id': resultado.get('id'),
                    'periodo': resultado.get('periodo'),
                    'nombre_excel': resultado.get('nombre_excel'),
                    'nombre_pdf': resultado.get('nombre_pdf'),
                },
                'resumen_ejecutivo': data.get('resumen_ejecutivo'),
                'indicadores': data.get('indicadores'),
                'hallazgos': data.get('hallazgos'),
                'alertas': data.get('alertas'),
                'recomendaciones': data.get('recomendaciones'),
                'pendientes': data.get('pendientes'),
                'responsables': data.get('responsables'),
                'conclusion': data.get('conclusion'),
            })
        except Exception as exc:
            return jsonify({'error': f'No se pudo generar el reporte gerencial: {exc}'}), 500

    @bp.route('/historial', methods=['GET'])
    @require_roles(*ALLOWED_ROLES)
    def historial():
        user = current_user()
        limit = int(request.args.get('limit') or 50)
        return jsonify({'reportes': service.historial(user.get('fundacion_id'), limit)})

    @bp.route('/<int:reporte_id>', methods=['GET'])
    @require_roles(*ALLOWED_ROLES)
    def detalle(reporte_id: int):
        row = service.obtener_reporte(reporte_id)
        if not row:
            return jsonify({'error': 'Reporte no encontrado.'}), 404
        return jsonify({'reporte': row})

    @bp.route('/<int:reporte_id>/descargar/<tipo>', methods=['GET'])
    @require_roles(*ALLOWED_ROLES)
    def descargar(reporte_id: int, tipo: str):
        row = service.obtener_reporte(reporte_id)
        if not row:
            return jsonify({'error': 'Reporte no encontrado.'}), 404
        tipo = (tipo or '').lower()
        ruta = row.get('ruta_pdf') if tipo == 'pdf' else row.get('ruta_excel')
        nombre = row.get('nombre_pdf') if tipo == 'pdf' else row.get('nombre_excel')
        if not ruta or not os.path.exists(ruta):
            return jsonify({'error': 'Archivo del reporte no encontrado.'}), 404
        return send_file(ruta, as_attachment=True, download_name=nombre or os.path.basename(ruta))

    app.register_blueprint(bp)
