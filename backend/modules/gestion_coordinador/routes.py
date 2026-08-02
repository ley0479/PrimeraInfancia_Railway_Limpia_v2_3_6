from __future__ import annotations

import os
from datetime import datetime
from flask import Blueprint, jsonify, request, send_from_directory
from werkzeug.utils import secure_filename

from .repository import GestionCoordinadorRepository, now_iso
from .services import ACTIVITY_STATES, ACTIVITY_TYPES, dashboard, generate_alerts_for_activities, monthly_report, current_period

ALLOWED_DOCS = {'.pdf', '.doc', '.docx', '.xlsx', '.xls', '.xlsm', '.csv', '.txt', '.png', '.jpg', '.jpeg', '.zip', '.rar'}


def json_payload() -> dict:
    return request.get_json(silent=True) or {}


def register_gestion_coordinador(app, database_path: str, upload_folder: str) -> None:
    repo = GestionCoordinadorRepository(database_path)
    repo.init_schema()
    module_upload = os.path.join(upload_folder, 'gestion_coordinador')
    os.makedirs(module_upload, exist_ok=True)

    bp = Blueprint('gestion_coordinador', __name__, url_prefix='/api/gestion-coordinador')

    @bp.route('/dashboard', methods=['GET'])
    def dashboard_view():
        periodo = request.args.get('periodo') or current_period()
        return jsonify(dashboard(repo, periodo)), 200

    @bp.route('/coordinadores', methods=['GET'])
    def coordinadores():
        periodo = request.args.get('periodo') or current_period()
        return jsonify({'coordinadores': repo.list_coordinators_summary(periodo)}), 200

    @bp.route('/coordinadores/<int:coordinador_id>/panel', methods=['GET'])
    def coordinador_panel(coordinador_id: int):
        periodo = request.args.get('periodo') or current_period()
        panel = repo.coordinator_panel(coordinador_id, periodo)
        if not panel:
            return jsonify({'error': 'Coordinador no encontrado o no autorizado.'}), 404
        return jsonify(panel), 200

    @bp.route('/mis-datos', methods=['GET'])
    def mis_datos():
        cid = repo.current_coordinator_id()
        if not cid:
            return jsonify({'coordinador_id': None, 'panel': None}), 200
        return jsonify({'coordinador_id': cid, 'panel': repo.coordinator_panel(cid, request.args.get('periodo') or current_period())}), 200

    @bp.route('/asignaciones', methods=['GET', 'POST'])
    def asignaciones():
        if request.method == 'GET':
            coord_id = request.args.get('coordinador_id', type=int)
            return jsonify({'asignaciones': repo.list_assignments(coord_id)}), 200
        data = json_payload()
        if not data.get('coordinador_id'):
            return jsonify({'error': 'coordinador_id es obligatorio.'}), 400
        if not data.get('nombre'):
            return jsonify({'error': 'Nombre del talento humano requerido.'}), 400
        asignacion = repo.create_assignment(data)
        return jsonify({'message': 'Asignación creada correctamente.', 'asignacion': asignacion}), 201

    @bp.route('/asignaciones/<int:asignacion_id>', methods=['PUT', 'PATCH', 'DELETE'])
    def asignacion_detalle(asignacion_id: int):
        if request.method in {'PUT', 'PATCH'}:
            updated = repo.update_assignment(asignacion_id, json_payload())
            if not updated:
                return jsonify({'error': 'Asignación no encontrada.'}), 404
            return jsonify({'message': 'Asignación actualizada correctamente.', 'asignacion': updated}), 200
        if not repo.deactivate_assignment(asignacion_id):
            return jsonify({'error': 'Asignación no encontrada.'}), 404
        return jsonify({'message': 'Asignación inactivada correctamente.'}), 200

    @bp.route('/calendario', methods=['GET'])
    def calendario():
        periodo = request.args.get('periodo')
        mes = request.args.get('mes')
        anio = request.args.get('anio')
        if not periodo and mes and anio:
            periodo = f"{int(anio):04d}-{int(mes):02d}"
        filters = {
            'periodo': periodo or current_period(),
            'coordinador_id': request.args.get('coordinador_id', type=int),
            'unidad': request.args.get('unidad'),
            'docente_id': request.args.get('docente_id', type=int),
            'tipo': request.args.get('tipo'),
            'estado': request.args.get('estado'),
            'fecha': request.args.get('fecha'),
        }
        actividades = repo.list_activities({k: v for k, v in filters.items() if v})
        return jsonify({
            'periodo': filters['periodo'],
            'vista': request.args.get('vista', 'mes'),
            'actividades': actividades,
            'estados': ACTIVITY_STATES,
            'tipos': ACTIVITY_TYPES,
            'alertas': generate_alerts_for_activities(actividades),
        }), 200

    @bp.route('/calendario/actividades', methods=['POST'])
    def crear_actividad():
        data = json_payload()
        if not data.get('titulo'):
            return jsonify({'error': 'Título requerido.'}), 400
        if not data.get('fecha'):
            return jsonify({'error': 'Fecha requerida.'}), 400
        actividad = repo.create_activity(data)
        return jsonify({'message': 'Actividad creada correctamente.', 'actividad': actividad}), 201

    @bp.route('/calendario/actividades/<int:actividad_id>', methods=['GET', 'PUT', 'PATCH', 'DELETE'])
    def actividad_detalle(actividad_id: int):
        if request.method == 'GET':
            actividad = repo.fetch_one('SELECT * FROM gp_calendario_eventos WHERE id=?', (actividad_id,))
            if not actividad:
                return jsonify({'error': 'Actividad no encontrada.'}), 404
            return jsonify({'actividad': actividad}), 200
        if request.method in {'PUT', 'PATCH'}:
            updated = repo.update_activity(actividad_id, json_payload())
            if not updated:
                return jsonify({'error': 'Actividad no encontrada.'}), 404
            return jsonify({'message': 'Actividad actualizada correctamente.', 'actividad': updated}), 200
        if not repo.delete_activity(actividad_id):
            return jsonify({'error': 'Actividad no encontrada.'}), 404
        return jsonify({'message': 'Actividad anulada correctamente.'}), 200

    @bp.route('/evidencias/upload', methods=['POST'])
    def subir_evidencia():
        if 'file' not in request.files:
            return jsonify({'error': 'Archivo requerido.'}), 400
        file = request.files['file']
        if not file.filename:
            return jsonify({'error': 'Archivo sin nombre.'}), 400
        ext = os.path.splitext(file.filename.lower())[1]
        if ext not in ALLOWED_DOCS:
            return jsonify({'error': 'Extensión no permitida.'}), 400
        name = secure_filename(file.filename)
        saved = f"EVIDENCIA_{datetime.now().strftime('%Y%m%d%H%M%S')}_{name}"
        path = os.path.join(module_upload, saved)
        file.save(path)
        data = request.form.to_dict()
        new_id = repo.execute(
            """
            INSERT INTO gp_evidencias
            (actividad_id, entregable_id, coordinador_id, docente_id, unidad, tipo, titulo, descripcion,
             ruta_archivo, nombre_original, nombre_guardado, estado, observaciones, fecha_creacion, fecha_actualizacion)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'CARGADA', ?, ?, ?)
            """,
            (
                data.get('actividad_id') or None, data.get('entregable_id') or None, data.get('coordinador_id') or None,
                data.get('docente_id') or None, data.get('unidad') or '', data.get('tipo') or 'Evidencia',
                data.get('titulo') or name, data.get('descripcion') or '', path, file.filename, saved,
                data.get('observaciones') or '', now_iso(), now_iso(),
            ),
        )
        evidencia = repo.fetch_one('SELECT * FROM gp_evidencias WHERE id=?', (new_id,))
        repo.log('CARGAR_EVIDENCIA', 'gp_evidencias', new_id, nuevos=evidencia)
        return jsonify({'message': 'Evidencia cargada correctamente.', 'evidencia': evidencia}), 201

    @bp.route('/evidencias/<int:evidencia_id>/download', methods=['GET'])
    def descargar_evidencia(evidencia_id: int):
        evidencia = repo.fetch_one('SELECT * FROM gp_evidencias WHERE id=?', (evidencia_id,))
        if not evidencia:
            return jsonify({'error': 'Evidencia no encontrada.'}), 404
        return send_from_directory(module_upload, evidencia.get('nombre_guardado'), as_attachment=True)

    @bp.route('/alertas', methods=['GET'])
    def alertas():
        periodo = request.args.get('periodo') or current_period()
        actividades = repo.list_activities({'periodo': periodo})
        alertas_calc = generate_alerts_for_activities(actividades)
        # También se devuelven alertas guardadas en gp_alertas.
        where, params = repo.entity_scope_clause('a')
        guardadas = repo.fetch_all(
            f"""
            SELECT a.*, c.nombre AS coordinador_nombre
            FROM gp_alertas a
            LEFT JOIN gp_coordinadores c ON c.id=a.coordinador_id
            WHERE {where}
            ORDER BY a.fecha_alerta DESC, a.fecha_creacion DESC LIMIT 200
            """,
            params,
        )
        return jsonify({'alertas': alertas_calc + guardadas}), 200

    @bp.route('/reportes/mensual', methods=['GET'])
    def reporte_mensual():
        periodo = request.args.get('periodo') or current_period()
        return jsonify(monthly_report(repo, periodo)), 200

    app.register_blueprint(bp)
