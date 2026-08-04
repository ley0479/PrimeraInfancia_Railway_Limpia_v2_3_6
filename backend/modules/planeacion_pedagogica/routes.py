from __future__ import annotations

import os
from datetime import datetime
from flask import Blueprint, jsonify, request, send_from_directory
from modules.seguridad.tenant_context import tenant_path
from werkzeug.utils import secure_filename

from .repository import PlaneacionRepository, now_iso
from .schema import ESTADOS_PLANEACION, TIPOS_DOCUMENTO_GENERABLES, TIPOS_ACTIVIDAD_DEFAULT
from .services import (
    create_planeacion_from_file,
    create_activities_and_calendar,
    generate_documents,
    cambiar_estado_planeacion,
    monthly_report,
    periodo_actual,
    extract_text_from_file,
)

ALLOWED_UPLOADS = {'.xlsx', '.xls', '.xlsm', '.csv', '.txt', '.doc', '.docx', '.pdf'}
ALLOWED_TEMPLATES = {'.docx', '.xlsx', '.xlsm', '.pdf'}
ALLOWED_EVIDENCIAS = {'.pdf', '.doc', '.docx', '.xlsx', '.xls', '.xlsm', '.csv', '.txt', '.png', '.jpg', '.jpeg', '.zip', '.rar'}


def payload() -> dict:
    return request.get_json(silent=True) or {}


def safe_filename(prefix: str, filename: str) -> str:
    name = secure_filename(filename) or 'archivo'
    return f"{prefix}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{name}"


def register_planeacion_pedagogica(app, database_path: str, upload_folder: str, output_folder: str) -> None:
    repo = PlaneacionRepository(database_path)
    repo.init_schema()
    module_upload = tenant_path(upload_folder, 'planeacion_pedagogica')
    module_output = tenant_path(output_folder, 'planeacion_pedagogica')
    os.makedirs(module_upload, exist_ok=True)
    os.makedirs(module_output, exist_ok=True)

    bp = Blueprint('planeacion_pedagogica', __name__, url_prefix='/api/planeacion-pedagogica')

    @bp.before_request
    def _ensure_schema():
        repo.init_schema()

    @bp.route('/dashboard', methods=['GET'])
    def dashboard():
        periodo = request.args.get('periodo') or periodo_actual()
        return jsonify(repo.dashboard(periodo)), 200

    @bp.route('/catalogos', methods=['GET'])
    def catalogos():
        return jsonify({
            'estados': ESTADOS_PLANEACION,
            'tipos_actividad': [{'codigo': c, 'nombre': n} for c, n in TIPOS_ACTIVIDAD_DEFAULT],
            'tipos_documento': TIPOS_DOCUMENTO_GENERABLES,
            'coordinadores': repo.list_coordinadores(),
            'docentes': repo.list_docentes(),
        }), 200

    @bp.route('/planeaciones', methods=['GET', 'POST'])
    def planeaciones():
        if request.method == 'GET':
            return jsonify({
                'planeaciones': repo.list_planeaciones(
                    periodo=request.args.get('periodo'),
                    estado=request.args.get('estado'),
                )
            }), 200

        if 'file' not in request.files:
            return jsonify({'error': 'Archivo de planeación requerido.'}), 400
        file = request.files['file']
        if not file.filename:
            return jsonify({'error': 'Archivo sin nombre.'}), 400
        ext = os.path.splitext(file.filename.lower())[1]
        if ext not in ALLOWED_UPLOADS:
            return jsonify({'error': 'Extensión no permitida para planeación.'}), 400
        saved = safe_filename('PLANEACION', file.filename)
        path = os.path.join(module_upload, saved)
        file.save(path)
        form = request.form.to_dict()
        try:
            planeacion = create_planeacion_from_file(repo, path, file.filename, form)
            return jsonify({'message': 'Planeación cargada y calendario generado correctamente.', 'planeacion': planeacion}), 201
        except Exception as exc:
            return jsonify({'error': f'No se pudo procesar la planeación: {exc}'}), 500

    @bp.route('/planeaciones/manual', methods=['POST'])
    def crear_planeacion_manual():
        data = payload()
        periodo = data.get('periodo') or periodo_actual()
        anio, mes = [int(x) for x in periodo.split('-', 1)] if '-' in periodo else (datetime.now().year, datetime.now().month)
        now = now_iso()
        if not data.get('tema'):
            return jsonify({'error': 'Tema requerido.'}), 400
        new_id = repo.execute(
            """
            INSERT INTO pp_planeaciones
            (coordinador_id, docente_id, unidad, periodo, mes, anio, tema, objetivo, actividad,
             fecha_programada, poblacion_objetivo, evidencia_requerida, tipo_encuentro, observaciones,
             estado, activo, fecha_carga, fecha_creacion, fecha_actualizacion)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'BORRADOR', 1, ?, ?, ?)
            """,
            (
                data.get('coordinador_id'), data.get('docente_id'), data.get('unidad') or '', periodo, mes, anio,
                data.get('tema'), data.get('objetivo') or '', data.get('actividad') or '', data.get('fecha_programada') or f'{periodo}-01',
                data.get('poblacion_objetivo') or '', data.get('evidencia_requerida') or '', data.get('tipo_encuentro') or 'Actividad pedagógica',
                data.get('observaciones') or '', now, now, now,
            ),
        )
        planeacion = repo.get_planeacion(new_id) or {}
        create_activities_and_calendar(repo, planeacion)
        repo.log('CREAR_PLANEACION_MANUAL', 'pp_planeaciones', new_id, nuevos=planeacion, planeacion_id=new_id)
        return jsonify({'message': 'Planeación creada correctamente.', 'planeacion': repo.get_planeacion(new_id)}), 201

    @bp.route('/planeaciones/<int:planeacion_id>', methods=['GET', 'PUT', 'PATCH', 'DELETE'])
    def planeacion_detalle(planeacion_id: int):
        planeacion = repo.get_planeacion(planeacion_id)
        if not planeacion:
            return jsonify({'error': 'Planeación no encontrada.'}), 404
        if request.method == 'GET':
            return jsonify({'planeacion': planeacion}), 200
        if request.method in {'PUT', 'PATCH'}:
            data = payload()
            anterior = planeacion
            fields = ['coordinador_id','docente_id','unidad','tema','objetivo','actividad','fecha_programada','poblacion_objetivo','evidencia_requerida','tipo_encuentro','observaciones','estado']
            values = {f: data.get(f, planeacion.get(f)) for f in fields}
            repo.execute_update(
                """
                UPDATE pp_planeaciones
                SET coordinador_id=?, docente_id=?, unidad=?, tema=?, objetivo=?, actividad=?, fecha_programada=?,
                    poblacion_objetivo=?, evidencia_requerida=?, tipo_encuentro=?, observaciones=?, estado=?, fecha_actualizacion=?
                WHERE id=?
                """,
                tuple(values[f] for f in fields) + (now_iso(), planeacion_id),
            )
            updated = repo.get_planeacion(planeacion_id)
            repo.log('EDITAR_PLANEACION', 'pp_planeaciones', planeacion_id, anteriores=anterior, nuevos=updated, planeacion_id=planeacion_id)
            return jsonify({'message': 'Planeación actualizada.', 'planeacion': updated}), 200
        # DELETE lógico = anular.
        updated = cambiar_estado_planeacion(repo, planeacion_id, 'ANULAR_PLANEACION', 'ANULADA', request.args.get('observacion') or '')
        return jsonify({'message': 'Planeación anulada.', 'planeacion': updated}), 200

    @bp.route('/planeaciones/<int:planeacion_id>/aprobar', methods=['POST'])
    def aprobar_planeacion(planeacion_id: int):
        return jsonify({'message': 'Planeación aprobada.', 'planeacion': cambiar_estado_planeacion(repo, planeacion_id, 'APROBAR_PLANEACION', 'APROBADA', payload().get('observacion',''))}), 200

    @bp.route('/planeaciones/<int:planeacion_id>/rechazar', methods=['POST'])
    def rechazar_planeacion(planeacion_id: int):
        return jsonify({'message': 'Planeación rechazada.', 'planeacion': cambiar_estado_planeacion(repo, planeacion_id, 'RECHAZAR_PLANEACION', 'RECHAZADA', payload().get('observacion',''))}), 200

    @bp.route('/planeaciones/<int:planeacion_id>/corregir', methods=['POST'])
    def corregir_planeacion(planeacion_id: int):
        return jsonify({'message': 'Corrección solicitada.', 'planeacion': cambiar_estado_planeacion(repo, planeacion_id, 'SOLICITAR_CORRECCION', 'VALIDADA', payload().get('observacion','Solicitar corrección'))}), 200

    @bp.route('/planeaciones/<int:planeacion_id>/generar-documentos', methods=['POST'])
    def generar_docs(planeacion_id: int):
        data = payload()
        tipos = data.get('tipos') or TIPOS_DOCUMENTO_GENERABLES
        try:
            docs = generate_documents(repo, module_output, planeacion_id, tipos)
            return jsonify({'message': 'Documentos generados correctamente.', 'documentos': docs}), 201
        except Exception as exc:
            return jsonify({'error': f'No se pudieron generar documentos: {exc}'}), 500

    @bp.route('/actividades', methods=['GET'])
    def actividades():
        planeacion_id = request.args.get('planeacion_id', type=int)
        periodo = request.args.get('periodo')
        where, params = repo.coordinator_filter_clause('a')
        if planeacion_id:
            where += ' AND a.planeacion_id=?'
            params.append(planeacion_id)
        if periodo:
            where += " AND substr(COALESCE(a.fecha_programada,''),1,7)=?"
            params.append(periodo)
        fid = int(repo.context().get('fundacion_id') or 1)
        rows = repo.fetch_all(
            f"SELECT a.*, p.tema AS planeacion_tema "
            f"FROM pp_actividades a "
            f"LEFT JOIN pp_planeaciones p ON p.id=a.planeacion_id AND COALESCE(p.fundacion_id, 1)={fid} "
            f"WHERE {where} AND a.activo=1 ORDER BY a.fecha_programada, a.id",
            params,
        )
        return jsonify({'actividades': rows}), 200

    @bp.route('/actividades/<int:actividad_id>', methods=['PUT', 'PATCH'])
    def actualizar_actividad(actividad_id: int):
        data = payload()
        actual = repo.fetch_one('SELECT * FROM pp_actividades WHERE id=?', (actividad_id,))
        if not actual:
            return jsonify({'error': 'Actividad no encontrada.'}), 404
        repo.execute_update(
            """
            UPDATE pp_actividades
            SET tipo_actividad=?, titulo=?, tema=?, objetivo=?, actividad=?, fecha_programada=?, poblacion_objetivo=?, evidencia_requerida=?, estado=?, fecha_actualizacion=?
            WHERE id=?
            """,
            (
                data.get('tipo_actividad', actual.get('tipo_actividad')), data.get('titulo', actual.get('titulo')),
                data.get('tema', actual.get('tema')), data.get('objetivo', actual.get('objetivo')), data.get('actividad', actual.get('actividad')),
                data.get('fecha_programada', actual.get('fecha_programada')), data.get('poblacion_objetivo', actual.get('poblacion_objetivo')),
                data.get('evidencia_requerida', actual.get('evidencia_requerida')), data.get('estado', actual.get('estado')), now_iso(), actividad_id,
            ),
        )
        updated = repo.fetch_one('SELECT * FROM pp_actividades WHERE id=?', (actividad_id,))
        repo.log('EDITAR_ACTIVIDAD', 'pp_actividades', actividad_id, anteriores=actual, nuevos=updated, planeacion_id=actual.get('planeacion_id'))
        return jsonify({'message': 'Actividad actualizada.', 'actividad': updated}), 200

    @bp.route('/plantillas', methods=['GET', 'POST'])
    def plantillas():
        if request.method == 'GET':
            return jsonify({'plantillas': repo.list_plantillas(request.args.get('tipo_documento'))}), 200
        if 'file' not in request.files:
            return jsonify({'error': 'Archivo de plantilla requerido.'}), 400
        file = request.files['file']
        if not file.filename:
            return jsonify({'error': 'Archivo sin nombre.'}), 400
        ext = os.path.splitext(file.filename.lower())[1]
        if ext not in ALLOWED_TEMPLATES:
            return jsonify({'error': 'Extensión de plantilla no permitida.'}), 400
        saved = safe_filename('PLANTILLA_PP', file.filename)
        path = os.path.join(module_upload, saved)
        file.save(path)
        data = request.form.to_dict()
        now = now_iso()
        fields = data.get('campos_dinamicos') or '{{nombreFundacion}},{{nombreCoordinador}},{{nombreDocente}},{{unidad}},{{mes}},{{anio}},{{tema}},{{objetivo}},{{actividad}},{{fecha}},{{poblacion}},{{evidencia}},{{observaciones}}'
        new_id = repo.execute(
            """
            INSERT INTO pp_plantillas_documento
            (nombre, tipo_documento, campos_dinamicos, formato_base, nombre_original, nombre_guardado, ruta_archivo, version, estado, activo, fecha_creacion, fecha_actualizacion)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'ACTIVA', 1, ?, ?)
            """,
            (data.get('nombre') or file.filename, data.get('tipo_documento') or 'Informe pedagógico mensual', fields, ext.replace('.', ''), file.filename, saved, path, data.get('version') or '1.0', now, now),
        )
        plantilla = repo.fetch_one('SELECT * FROM pp_plantillas_documento WHERE id=?', (new_id,))
        repo.log('CARGAR_PLANTILLA', 'pp_plantillas_documento', new_id, nuevos=plantilla)
        return jsonify({'message': 'Plantilla registrada correctamente.', 'plantilla': plantilla}), 201

    @bp.route('/plantillas/<int:plantilla_id>', methods=['PUT', 'PATCH', 'DELETE'])
    def plantilla_detalle(plantilla_id: int):
        actual = repo.fetch_one('SELECT * FROM pp_plantillas_documento WHERE id=?', (plantilla_id,))
        if not actual:
            return jsonify({'error': 'Plantilla no encontrada.'}), 404
        if request.method in {'PUT', 'PATCH'}:
            data = payload()
            repo.execute_update(
                """
                UPDATE pp_plantillas_documento SET nombre=?, tipo_documento=?, campos_dinamicos=?, version=?, estado=?, activo=?, fecha_actualizacion=? WHERE id=?
                """,
                (data.get('nombre', actual.get('nombre')), data.get('tipo_documento', actual.get('tipo_documento')), data.get('campos_dinamicos', actual.get('campos_dinamicos')), data.get('version', actual.get('version')), data.get('estado', actual.get('estado')), int(data.get('activo', actual.get('activo', 1))), now_iso(), plantilla_id),
            )
            updated = repo.fetch_one('SELECT * FROM pp_plantillas_documento WHERE id=?', (plantilla_id,))
            repo.log('EDITAR_PLANTILLA', 'pp_plantillas_documento', plantilla_id, anteriores=actual, nuevos=updated)
            return jsonify({'message': 'Plantilla actualizada.', 'plantilla': updated}), 200
        repo.execute_update('UPDATE pp_plantillas_documento SET activo=0, estado="INACTIVA", fecha_actualizacion=? WHERE id=?', (now_iso(), plantilla_id))
        repo.log('INACTIVAR_PLANTILLA', 'pp_plantillas_documento', plantilla_id, anteriores=actual)
        return jsonify({'message': 'Plantilla inactivada.'}), 200

    @bp.route('/documentos-generados', methods=['GET'])
    def documentos_generados():
        planeacion_id = request.args.get('planeacion_id', type=int)
        where, params = repo.scope_clause('d')
        if planeacion_id:
            where += ' AND d.planeacion_id=?'
            params.append(planeacion_id)
        fid = int(repo.context().get('fundacion_id') or 1)
        rows = repo.fetch_all(
            f"SELECT d.*, p.tema AS planeacion_tema "
            f"FROM pp_documentos_generados d "
            f"LEFT JOIN pp_planeaciones p ON p.id=d.planeacion_id AND COALESCE(p.fundacion_id, 1)={fid} "
            f"WHERE {where} ORDER BY d.fecha_generacion DESC",
            params,
        )
        return jsonify({'documentos': rows}), 200

    @bp.route('/documentos-generados/<int:documento_id>/download', methods=['GET'])
    def descargar_documento(documento_id: int):
        doc = repo.fetch_one('SELECT * FROM pp_documentos_generados WHERE id=?', (documento_id,))
        if not doc or not os.path.exists(doc.get('ruta_archivo') or ''):
            return jsonify({'error': 'Documento no encontrado.'}), 404
        return send_from_directory(os.path.dirname(doc['ruta_archivo']), os.path.basename(doc['ruta_archivo']), as_attachment=True)

    @bp.route('/evidencias', methods=['GET'])
    def evidencias():
        planeacion_id = request.args.get('planeacion_id', type=int)
        where, params = repo.scope_clause('e')
        if planeacion_id:
            where += ' AND e.planeacion_id=?'
            params.append(planeacion_id)
        rows = repo.fetch_all(f"SELECT * FROM pp_evidencias_planeacion e WHERE {where} AND e.activo=1 ORDER BY e.fecha_creacion DESC", params)
        return jsonify({'evidencias': rows}), 200

    @bp.route('/evidencias/upload', methods=['POST'])
    def subir_evidencia():
        if 'file' not in request.files:
            return jsonify({'error': 'Archivo requerido.'}), 400
        file = request.files['file']
        if not file.filename:
            return jsonify({'error': 'Archivo sin nombre.'}), 400
        ext = os.path.splitext(file.filename.lower())[1]
        if ext not in ALLOWED_EVIDENCIAS:
            return jsonify({'error': 'Extensión de evidencia no permitida.'}), 400
        saved = safe_filename('EVIDENCIA_PP', file.filename)
        path = os.path.join(module_upload, saved)
        file.save(path)
        data = request.form.to_dict()
        now = now_iso()
        new_id = repo.execute(
            """
            INSERT INTO pp_evidencias_planeacion
            (planeacion_id, actividad_id, tipo, titulo, descripcion, ruta_archivo, nombre_original, nombre_guardado, estado, observaciones, activo, fecha_creacion, fecha_actualizacion)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'CARGADA', ?, 1, ?, ?)
            """,
            (data.get('planeacion_id') or None, data.get('actividad_id') or None, data.get('tipo') or 'EVIDENCIA', data.get('titulo') or file.filename, data.get('descripcion') or '', path, file.filename, saved, data.get('observaciones') or '', now, now),
        )
        evidencia = repo.fetch_one('SELECT * FROM pp_evidencias_planeacion WHERE id=?', (new_id,))
        repo.log('CARGAR_EVIDENCIA', 'pp_evidencias_planeacion', new_id, nuevos=evidencia, planeacion_id=int(data.get('planeacion_id') or 0) or None)
        return jsonify({'message': 'Evidencia cargada.', 'evidencia': evidencia}), 201

    @bp.route('/evidencias/<int:evidencia_id>/download', methods=['GET'])
    def descargar_evidencia(evidencia_id: int):
        ev = repo.fetch_one('SELECT * FROM pp_evidencias_planeacion WHERE id=?', (evidencia_id,))
        if not ev or not os.path.exists(ev.get('ruta_archivo') or ''):
            return jsonify({'error': 'Evidencia no encontrada.'}), 404
        return send_from_directory(os.path.dirname(ev['ruta_archivo']), os.path.basename(ev['ruta_archivo']), as_attachment=True)

    @bp.route('/reportes/mensual', methods=['GET'])
    def reporte_mensual():
        periodo = request.args.get('periodo') or periodo_actual()
        return jsonify(monthly_report(repo, periodo)), 200

    @bp.route('/analizar-documento', methods=['POST'])
    def analizar_documento():
        if 'file' not in request.files:
            return jsonify({'error': 'Archivo requerido.'}), 400
        file = request.files['file']
        if not file.filename:
            return jsonify({'error': 'Archivo sin nombre.'}), 400
        saved = safe_filename('ANALISIS_PP', file.filename)
        path = os.path.join(module_upload, saved)
        file.save(path)
        text = extract_text_from_file(path, file.filename)
        return jsonify({'nombre': file.filename, 'texto_detectado': text[:5000], 'caracteres': len(text)}), 200

    app.register_blueprint(bp)
