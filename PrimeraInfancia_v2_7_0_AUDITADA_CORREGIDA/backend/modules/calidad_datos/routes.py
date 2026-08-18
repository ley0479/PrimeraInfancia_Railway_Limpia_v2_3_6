from __future__ import annotations

import json
import os
from datetime import datetime

from flask import Blueprint, g, jsonify, request, send_from_directory
from werkzeug.utils import secure_filename

from modules.seguridad.services import require_roles
from modules.seguridad.tenant_context import tenant_path

from .repository import CalidadDatosRepository
from .services import (
    analizar_archivo,
    analizar_base_actual,
    generar_excel,
    generar_pdf,
)

ALLOWED = {'.xlsx', '.xls', '.xlsm', '.ods', '.csv', '.txt', '.tsv', '.tab', '.dat', '.html', '.htm', '.json'}


def user_ctx() -> dict:
    user = getattr(g, 'current_user', {}) or {}
    return {
        'usuario_id': user.get('id'),
        'usuario': user.get('username') or user.get('email') or 'sistema',
        'fundacion_id': int(user.get('fundacion_id') or 1),
        'rol': user.get('rol') or 'SUPERADMIN',
        'raw': user,
    }


def allowed_file(filename: str) -> bool:
    return os.path.splitext((filename or '').lower())[1] in ALLOWED


def save_upload(file, folder: str) -> dict:
    os.makedirs(folder, exist_ok=True)
    original = file.filename or 'archivo'
    safe = secure_filename(original)
    name = f"CALIDAD_{datetime.now().strftime('%Y%m%d%H%M%S')}_{safe}"
    path = os.path.join(folder, name)
    file.save(path)
    return {'nombre_original': original, 'nombre_guardado': name, 'ruta': path}


def register_calidad_datos(app, database_path: str, upload_folder: str, output_folder: str) -> None:
    repo = CalidadDatosRepository(database_path)
    repo.init_schema()

    bp = Blueprint('calidad_datos', __name__, url_prefix='/api/calidad-datos')
    module_upload = tenant_path(upload_folder, 'calidad_datos')
    module_output = tenant_path(output_folder, 'calidad_datos')
    os.makedirs(module_upload, exist_ok=True)
    os.makedirs(module_output, exist_ok=True)

    @bp.before_request
    def _ensure_schema():
        repo.init_schema()

    @bp.route('/dashboard', methods=['GET'])
    @require_roles('SUPERADMIN', 'GERENTE', 'COORDINADOR', 'AUXILIAR_ADMINISTRATIVO', 'NUTRICIONISTA')
    def dashboard():
        ctx = user_ctx()
        return jsonify(repo.dashboard(ctx['fundacion_id'], superadmin=ctx['rol'] == 'SUPERADMIN'))

    @bp.route('/historial', methods=['GET'])
    @require_roles('SUPERADMIN', 'GERENTE', 'COORDINADOR', 'AUXILIAR_ADMINISTRATIVO', 'NUTRICIONISTA')
    def historial():
        ctx = user_ctx()
        limit = request.args.get('limit', default=100, type=int)
        return jsonify({'historial': repo.historial(ctx['fundacion_id'], superadmin=ctx['rol'] == 'SUPERADMIN', limit=limit)})

    @bp.route('/analizar', methods=['POST'])
    @require_roles('SUPERADMIN', 'GERENTE', 'COORDINADOR', 'AUXILIAR_ADMINISTRATIVO', 'NUTRICIONISTA')
    def analizar():
        ctx = user_ctx()
        mes = request.form.get('mes', type=int) or datetime.now().month
        anio = request.form.get('anio', type=int) or request.form.get('año', type=int) or datetime.now().year
        tipo = request.form.get('tipo') or 'auto'
        fuente = request.form.get('fuente') or 'archivo'
        saved = None

        try:
            if 'file' in request.files and request.files['file'].filename:
                file = request.files['file']
                if not allowed_file(file.filename):
                    return jsonify({'error': 'Formato no permitido para calidad de datos. Usa Excel, CSV, TXT, TSV, HTML, JSON u ODS.'}), 400
                saved = save_upload(file, module_upload)
                resultado = analizar_archivo(saved['ruta'], database_path, ctx['fundacion_id'], tipo=tipo)
                nombre_archivo = saved['nombre_original']
                ruta_archivo = saved['ruta']
                tipo_fuente = 'ARCHIVO'
            else:
                resultado = analizar_base_actual(database_path, ctx['fundacion_id'])
                nombre_archivo = 'BASE_ACTUAL_SISTEMA'
                ruta_archivo = ''
                tipo_fuente = 'BASE_ACTUAL'

            resumen = resultado.get('resumen', {})
            hallazgos = resultado.get('hallazgos', [])
            errores = resultado.get('errores', [])
            metadata = {
                'fundacion_id': ctx['fundacion_id'],
                'usuario_id': ctx['usuario_id'],
                'usuario': ctx['usuario'],
                'tipo_fuente': tipo_fuente,
                'nombre_archivo': nombre_archivo,
                'ruta_archivo': ruta_archivo,
                'mes': mes,
                'anio': anio,
                'ip': request.remote_addr,
            }
            analisis_id = repo.guardar_analisis(metadata, resumen, errores, hallazgos)
            excel_path = generar_excel(analisis_id, resumen, hallazgos, module_output)
            pdf_path = generar_pdf(analisis_id, resumen, hallazgos, module_output)
            repo.actualizar_reportes(analisis_id, os.path.basename(excel_path), os.path.basename(pdf_path))
            return jsonify({
                'message': 'Análisis de calidad de datos generado correctamente.',
                'analisis_id': analisis_id,
                'resumen': resumen,
                'hallazgos': hallazgos[:500],
                'errores': errores,
                'reporte_excel': os.path.basename(excel_path),
                'reporte_pdf': os.path.basename(pdf_path),
            }), 201
        except Exception as exc:
            return jsonify({'error': f'No se pudo analizar calidad de datos: {exc}'}), 400

    @bp.route('/<int:analisis_id>', methods=['GET'])
    @require_roles('SUPERADMIN', 'GERENTE', 'COORDINADOR', 'AUXILIAR_ADMINISTRATIVO', 'NUTRICIONISTA')
    def obtener(analisis_id: int):
        ctx = user_ctx()
        row = repo.obtener_analisis(analisis_id)
        if not row:
            return jsonify({'error': 'Análisis no encontrado.'}), 404
        if ctx['rol'] != 'SUPERADMIN' and int(row.get('fundacion_id') or 0) != ctx['fundacion_id']:
            return jsonify({'error': 'No tienes permiso para ver este análisis.'}), 403
        try:
            row['resumen'] = json.loads(row.get('resumen_json') or '{}')
        except Exception:
            row['resumen'] = {}
        return jsonify({'analisis': row, 'hallazgos': repo.hallazgos(analisis_id, limit=1000)})

    @bp.route('/<int:analisis_id>/hallazgos/<tipo>', methods=['GET'])
    @require_roles('SUPERADMIN', 'GERENTE', 'COORDINADOR', 'AUXILIAR_ADMINISTRATIVO', 'NUTRICIONISTA')
    def hallazgos_tipo(analisis_id: int, tipo: str):
        ctx = user_ctx()
        row = repo.obtener_analisis(analisis_id)
        if not row:
            return jsonify({'error': 'Análisis no encontrado.'}), 404
        if ctx['rol'] != 'SUPERADMIN' and int(row.get('fundacion_id') or 0) != ctx['fundacion_id']:
            return jsonify({'error': 'No tienes permiso para ver este análisis.'}), 403
        return jsonify({'items': repo.hallazgos(analisis_id, tipo=tipo, limit=5000), 'tipo': tipo, 'analisis_id': analisis_id})

    @bp.route('/<int:analisis_id>/descargar/<formato>', methods=['GET'])
    @require_roles('SUPERADMIN', 'GERENTE', 'COORDINADOR', 'AUXILIAR_ADMINISTRATIVO', 'NUTRICIONISTA')
    def descargar(analisis_id: int, formato: str):
        ctx = user_ctx()
        row = repo.obtener_analisis(analisis_id)
        if not row:
            return jsonify({'error': 'Análisis no encontrado.'}), 404
        if ctx['rol'] != 'SUPERADMIN' and int(row.get('fundacion_id') or 0) != ctx['fundacion_id']:
            return jsonify({'error': 'No tienes permiso para descargar este análisis.'}), 403
        filename = row.get('reporte_pdf') if formato.lower() == 'pdf' else row.get('reporte_excel')
        if not filename:
            resumen = json.loads(row.get('resumen_json') or '{}')
            hallazgos = repo.hallazgos(analisis_id)
            if formato.lower() == 'pdf':
                filename = os.path.basename(generar_pdf(analisis_id, resumen, hallazgos, module_output))
            else:
                filename = os.path.basename(generar_excel(analisis_id, resumen, hallazgos, module_output))
            repo.actualizar_reportes(analisis_id, pdf=filename if formato.lower() == 'pdf' else None, excel=filename if formato.lower() != 'pdf' else None)
        path = os.path.join(module_output, filename)
        if not os.path.exists(path):
            return jsonify({'error': 'Archivo de reporte no encontrado.'}), 404
        repo.log(analisis_id, f'DESCARGA_{formato.upper()}', f'Descarga reporte calidad de datos {filename}', ctx['raw'], request.remote_addr)
        return send_from_directory(module_output, filename, as_attachment=True)

    app.register_blueprint(bp)
