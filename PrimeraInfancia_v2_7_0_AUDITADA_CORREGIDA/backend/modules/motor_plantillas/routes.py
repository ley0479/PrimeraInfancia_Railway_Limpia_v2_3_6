
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
from datetime import datetime
from pathlib import Path

from flask import Blueprint, g, jsonify, request, send_file
from werkzeug.utils import secure_filename

from modules.seguridad.services import require_roles
from modules.seguridad.tenant_context import tenant_path
from modules.print_master import print_master_config_public

from .repository import MotorPlantillasRepository
from .schema import CAMPOS_CANONICOS
from .services import (
    apply_mapping_to_copy,
    detect_template,
    init_schema,
    validate_mapping,
)
from services.ram_v3_service import find_instruction, load_instruction_catalog, sha256_file
from services.rpp_minutas_service import (
    guardar_minuta_desde_archivo,
    listar_minutas,
    marcar_minuta_vigente,
    obtener_minuta_vigente,
    init_schema as init_minutas_schema,
)

ALLOWED_TEMPLATE_EXTENSIONS = {'.xlsx', '.xls', '.xlsm'}
ALLOWED_ROLES = ('SUPERADMIN', 'GERENTE', 'AUXILIAR_ADMINISTRATIVO')


def current_user() -> dict:
    user = getattr(g, 'current_user', {}) or {}
    return {
        'usuario_id': user.get('id'),
        'username': user.get('username') or user.get('email') or 'sistema',
        'fundacion_id': int(user.get('fundacion_id') or 1),
        'rol': user.get('rol') or 'SUPERADMIN',
        'raw': user,
    }


def allowed_file(filename: str) -> bool:
    return os.path.splitext((filename or '').lower())[1] in ALLOWED_TEMPLATE_EXTENSIONS


def sanitize_name(filename: str) -> str:
    filename = secure_filename(filename or 'plantilla.xlsx')
    if not filename:
        filename = 'plantilla.xlsx'
    return filename


def register_motor_plantillas(app, database_path: str, templates_folder: str, output_folder: str) -> None:
    init_schema(database_path)
    init_minutas_schema(database_path)
    repo = MotorPlantillasRepository(database_path)
    custom_templates = tenant_path(
        Path(app.config['DATA_DIR']) / 'custom_templates',
        'motor_plantillas',
    )

    def motor_folder_path() -> Path:
        path = Path(os.fspath(custom_templates))
        path.mkdir(parents=True, exist_ok=True)
        return path

    def output_folder_path() -> Path:
        path = Path(os.fspath(output_folder))
        path.mkdir(parents=True, exist_ok=True)
        return path

    ram_rules_path = Path(__file__).resolve().parents[2] / 'config' / 'ram_v3_instrucciones.json'
    ram_template_path = Path(templates_folder) / 'oficiales' / 'plantilla_ram_oficial_v3.xlsx'

    bp = Blueprint('motor_plantillas', __name__, url_prefix='/api/motor-plantillas')

    @bp.before_request
    def _ensure_schema():
        init_schema(database_path)
        init_minutas_schema(database_path)

    @bp.route('/dashboard', methods=['GET'])
    @require_roles(*ALLOWED_ROLES)
    def dashboard():
        user = current_user()
        include_all = user['rol'] == 'SUPERADMIN'
        return jsonify(repo.dashboard(None if include_all else user['fundacion_id']))

    @bp.route('/campos', methods=['GET'])
    @require_roles(*ALLOWED_ROLES)
    def campos():
        return jsonify({'campos': CAMPOS_CANONICOS})

    @bp.route('/print-config', methods=['GET'])
    @require_roles(*ALLOWED_ROLES)
    def print_config():
        return jsonify({'formatos': print_master_config_public()})

    @bp.route('/ram-v3/instrucciones', methods=['GET'])
    @require_roles(*ALLOWED_ROLES)
    def instrucciones_ram_v3():
        if not ram_rules_path.exists():
            return jsonify({'error': 'No se encontró el catálogo de instrucciones RAM V3.'}), 404
        catalog = load_instruction_catalog(ram_rules_path)
        field = (request.args.get('campo') or request.args.get('field') or '').strip()
        if field:
            instruction = find_instruction(catalog, field)
            if not instruction:
                return jsonify({'error': 'El manual RAM V3 no contiene una instrucción específica para ese campo.'}), 404
            return jsonify({'formato': catalog.get('formato'), 'codigo': catalog.get('codigo'), 'version': catalog.get('version'), 'instruccion': instruction})
        return jsonify(catalog)

    @bp.route('/ram-v3/estado', methods=['GET'])
    @require_roles(*ALLOWED_ROLES)
    def estado_ram_v3():
        mes = request.args.get('mes', type=int) or datetime.now().month
        anio = request.args.get('anio', type=int) or request.args.get('año', type=int) or datetime.now().year
        version = repo.get_applicable('RAM', mes, anio)
        actual_hash = sha256_file(ram_template_path) if ram_template_path.exists() else None
        return jsonify({
            'periodo': f'{anio:04d}-{mes:02d}',
            'version_aplicable': version,
            'plantilla_existe': ram_template_path.exists(),
            'hash_actual': actual_hash,
            'integridad_ok': bool(version and actual_hash and (version.get('hash_sha256') or '').lower() == actual_hash.lower()),
            'instrucciones_existen': ram_rules_path.exists(),
        })

    @bp.route('/ram-v3/validar', methods=['POST'])
    @require_roles(*ALLOWED_ROLES)
    def validar_datos_ram_v3():
        data = request.get_json(silent=True) or {}
        errors = []
        warnings = []
        doc_type = str(data.get('tipo_documento') or '').strip().upper()
        if doc_type and doc_type not in {'RC', 'TI', 'CC', 'CE', 'PA', 'SD'}:
            errors.append({'campo': 'tipo_documento', 'mensaje': 'Solo se permiten RC, TI, CC, CE, PA o SD.'})
        if doc_type == 'SD' and not str(data.get('numero_documento') or '').strip():
            errors.append({'campo': 'numero_documento', 'mensaje': 'SD requiere el número asignado por CUÉNTAME.'})
        withdrawal = str(data.get('causa_retiro') or '').strip().upper()
        if withdrawal and withdrawal not in {'D', 'V', 'T', 'S', 'I', 'M', 'O'}:
            errors.append({'campo': 'causa_retiro', 'mensaje': 'Código de retiro no permitido.'})
        nit = str(data.get('nit') or '').strip()
        normalized_nit = re.sub(r'[.\-\s]', '', nit)
        if nit and nit != normalized_nit:
            warnings.append({'campo': 'nit', 'mensaje': 'El NIT se normalizará sin puntos ni guiones.', 'valor_normalizado': normalized_nit})
        return jsonify({'valido': not errors, 'errores': errors, 'advertencias': warnings})

    @bp.route('/plantillas', methods=['GET'])
    @require_roles(*ALLOWED_ROLES)
    def listar_plantillas():
        user = current_user()
        include_all = user['rol'] == 'SUPERADMIN'
        return jsonify({'plantillas': repo.list_templates(None if include_all else user['fundacion_id'], include_all=include_all)})

    @bp.route('/plantillas', methods=['POST'])
    @require_roles(*ALLOWED_ROLES)
    def subir_plantilla():
        if 'file' not in request.files:
            return jsonify({'error': 'Falta el archivo de plantilla oficial.'}), 400
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'Archivo no seleccionado.'}), 400
        if not allowed_file(file.filename):
            return jsonify({'error': 'Solo se permiten plantillas Excel .xlsx, .xls o .xlsm.'}), 400

        user = current_user()
        tipo = (request.form.get('tipo') or 'OTROS').strip().upper()[:80]
        version = (request.form.get('version') or '1.0').strip()[:30]
        nombre_original = sanitize_name(file.filename)
        nombre_guardado = f"MP_{tipo}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{nombre_original}"
        ruta = motor_folder_path() / nombre_guardado
        file.save(ruta)
        archivo_hash = sha256_file(ruta)

        try:
            deteccion = detect_template(str(ruta))
        except Exception as exc:
            try:
                ruta.unlink(missing_ok=True)
            except Exception:
                pass
            return jsonify({'error': f'No se pudo leer la plantilla Excel: {exc}'}), 400

        plantilla_id = repo.create_template({
            'nombre': request.form.get('nombre') or nombre_original,
            'tipo': tipo,
            'nombre_original': nombre_original,
            'nombre_guardado': nombre_guardado,
            'ruta_archivo': str(ruta),
            'version': version,
            'estado': request.form.get('estado') or 'BORRADOR',
            'codigo': request.form.get('codigo') or '',
            'fecha_vigencia': request.form.get('fecha_vigencia') or '',
            'observaciones': request.form.get('observaciones') or '',
            'hoja_principal': deteccion['hojas'][0]['nombre'] if deteccion.get('hojas') else '',
            'total_hojas': len(deteccion.get('hojas') or []),
            'metadata': {
                'deteccion': {
                    'total_columnas_detectadas': deteccion.get('total_columnas_detectadas', 0),
                    'hojas': deteccion.get('hojas', []),
                    'riesgos': deteccion.get('riesgos', []),
                }
            },
            'fundacion_id': user['fundacion_id'],
            'usuario_creador_id': user['usuario_id'],
        })
        version_id = repo.create_template_version_record(plantilla_id, {
            'tipo_formato': tipo,
            'codigo': request.form.get('codigo') or '',
            'nombre': request.form.get('nombre') or nombre_original,
            'version': version,
            'fecha_vigencia': request.form.get('fecha_vigencia') or '',
            'observaciones': request.form.get('observaciones') or '',
            'hash_sha256': archivo_hash,
            'manual_path': str(ram_rules_path) if tipo == 'RAM' and ram_rules_path.exists() else '',
            'reglas_json': ram_rules_path.read_text(encoding='utf-8') if tipo == 'RAM' and ram_rules_path.exists() else '[]',
            'estado': 'borrador',
            'estado_publicacion': 'borrador',
        }, user)

        return jsonify({
            'message': 'Plantilla oficial cargada como borrador y analizada correctamente.',
            'plantilla_id': plantilla_id,
            'version_id': version_id,
            'estado': 'borrador',
            'deteccion': deteccion,
        })

    @bp.route('/plantillas/<int:plantilla_id>/detectar', methods=['GET'])
    @require_roles(*ALLOWED_ROLES)
    def detectar(plantilla_id: int):
        plantilla = repo.get_template(plantilla_id)
        if not plantilla:
            return jsonify({'error': 'Plantilla no encontrada.'}), 404
        if not os.path.exists(plantilla['ruta_archivo']):
            return jsonify({'error': 'El archivo físico de la plantilla no existe.'}), 404
        deteccion = detect_template(plantilla['ruta_archivo'])
        return jsonify({'plantilla': plantilla, 'deteccion': deteccion, 'campos': CAMPOS_CANONICOS})

    @bp.route('/plantillas/<int:plantilla_id>/mapeo', methods=['GET'])
    @require_roles(*ALLOWED_ROLES)
    def obtener_mapeo(plantilla_id: int):
        plantilla = repo.get_template(plantilla_id)
        if not plantilla:
            return jsonify({'error': 'Plantilla no encontrada.'}), 404
        return jsonify({'plantilla': plantilla, 'mapeo': repo.get_active_mapping(plantilla_id)})

    @bp.route('/plantillas/<int:plantilla_id>/mapeo', methods=['POST'])
    @require_roles(*ALLOWED_ROLES)
    def guardar_mapeo(plantilla_id: int):
        plantilla = repo.get_template(plantilla_id)
        if not plantilla:
            return jsonify({'error': 'Plantilla no encontrada.'}), 404
        data = request.get_json(silent=True) or {}
        mapping = data.get('mapping') or data.get('mapeo') or []
        validation = validate_mapping(mapping, strict=True)
        if not validation['valido']:
            return jsonify({'error': 'El mapeo tiene errores críticos. Corrige antes de guardar.', 'validacion': validation}), 400
        user = current_user()
        mapeo_id = repo.save_mapping(
            plantilla_id,
            mapping,
            validation,
            user,
            nombre=data.get('nombre') or 'Mapeo principal',
            version=data.get('version') or '1.0'
        )
        return jsonify({'message': 'Mapeo guardado correctamente.', 'mapeo_id': mapeo_id, 'validacion': validation})

    @bp.route('/plantillas/<int:plantilla_id>/validar', methods=['POST'])
    @require_roles(*ALLOWED_ROLES)
    def validar(plantilla_id: int):
        plantilla = repo.get_template(plantilla_id)
        if not plantilla:
            return jsonify({'error': 'Plantilla no encontrada.'}), 404
        data = request.get_json(silent=True) or {}
        mapping = data.get('mapping') or data.get('mapeo') or []
        validation = validate_mapping(mapping, strict=bool(data.get('strict', True)))
        return jsonify({'validacion': validation})

    @bp.route('/plantillas/<int:plantilla_id>/probar-unidad', methods=['POST'])
    @require_roles(*ALLOWED_ROLES)
    def probar_unidad(plantilla_id: int):
        plantilla = repo.get_template(plantilla_id)
        if not plantilla:
            return jsonify({'error': 'Plantilla no encontrada.'}), 404
        if not os.path.exists(plantilla['ruta_archivo']):
            return jsonify({'error': 'Archivo de plantilla no encontrado.'}), 404
        data = request.get_json(silent=True) or {}
        unidad = (data.get('unidad') or '').strip()
        if not unidad:
            return jsonify({'error': 'Debes indicar una unidad para la prueba.'}), 400
        mapping = data.get('mapping') or data.get('mapeo')
        active = repo.get_active_mapping(plantilla_id)
        if not mapping and active:
            mapping = active.get('mapeo') or []
        if not mapping:
            return jsonify({'error': 'No hay mapeo para probar.'}), 400
        limit = int(data.get('limite') or data.get('limit') or 20)
        limit = max(1, min(50, limit))
        version = repo.get_version_by_template(plantilla_id)
        productos = repo.get_products(version['id']) if version else []
        result = apply_mapping_to_copy(database_path, plantilla['ruta_archivo'], mapping, unidad, os.fspath(output_folder_path()), limit=limit, tipo_formato=plantilla.get('tipo'), productos=productos)
        prueba_id = repo.save_test(plantilla_id, active.get('id') if active else None, unidad, result, current_user())
        return jsonify({
            'message': 'Prueba generada correctamente.' if result.get('ok') else 'La prueba no se pudo generar por errores de mapeo.',
            'prueba_id': prueba_id,
            'resultado': result,
            'download_url': f'/api/motor-plantillas/pruebas/{prueba_id}/descargar' if result.get('ok') else None,
        })

    @bp.route('/pruebas/<int:prueba_id>/descargar', methods=['GET'])
    @require_roles(*ALLOWED_ROLES)
    def descargar_prueba(prueba_id: int):
        prueba = repo.get_test(prueba_id)
        if not prueba:
            return jsonify({'error': 'Prueba no encontrada.'}), 404
        archivo = prueba.get('archivo_generado')
        if not archivo or not os.path.exists(archivo):
            return jsonify({'error': 'Archivo de prueba no encontrado.'}), 404
        return send_file(archivo, as_attachment=True)


    @bp.route('/cargar-version', methods=['POST'])
    @require_roles(*ALLOWED_ROLES)
    def cargar_version_alias():
        """Alias ALPHA52 para cargar nueva versión desde el Motor de Plantillas."""
        return subir_plantilla()

    @bp.route('/versiones', methods=['GET'])
    @require_roles(*ALLOWED_ROLES)
    def listar_versiones():
        tipo = request.args.get('tipo_formato') or request.args.get('tipo')
        return jsonify({'versiones': repo.list_versions(tipo)})

    @bp.route('/<tipo_formato>/vigente', methods=['GET'])
    @require_roles(*ALLOWED_ROLES)
    def obtener_vigente(tipo_formato: str):
        vigente = repo.get_vigente(tipo_formato)
        if not vigente:
            return jsonify({'error': f'No existe plantilla vigente para {tipo_formato}.'}), 404
        return jsonify({'vigente': vigente})

    @bp.route('/plantillas/<int:plantilla_id>/versiones', methods=['GET'])
    @require_roles(*ALLOWED_ROLES)
    def versiones_por_plantilla(plantilla_id: int):
        plantilla = repo.get_template(plantilla_id)
        if not plantilla:
            return jsonify({'error': 'Plantilla no encontrada.'}), 404
        tipo = plantilla.get('tipo') or ''
        return jsonify({'plantilla': plantilla, 'versiones': [v for v in repo.list_versions(tipo) if int(v.get('mp_plantilla_id') or 0) == plantilla_id or (v.get('tipo_formato') or '') == tipo]})

    @bp.route('/version/<int:version_id>/estructura', methods=['GET'])
    @require_roles(*ALLOWED_ROLES)
    def estructura_version(version_id: int):
        versiones = [v for v in repo.list_versions() if int(v.get('id') or 0) == version_id]
        if not versiones:
            return jsonify({'error': 'Versión no encontrada.'}), 404
        version = versiones[0]
        archivo = version.get('archivo_path')
        if not archivo or not os.path.exists(archivo):
            return jsonify({'error': 'El archivo físico de la versión no existe.'}), 404
        return jsonify({'version': version, 'estructura': detect_template(archivo), 'campos': CAMPOS_CANONICOS})

    @bp.route('/version/<int:version_id>/mapeo', methods=['POST'])
    @require_roles(*ALLOWED_ROLES)
    def guardar_mapeo_version(version_id: int):
        versiones = [v for v in repo.list_versions() if int(v.get('id') or 0) == version_id]
        if not versiones:
            return jsonify({'error': 'Versión no encontrada.'}), 404
        version = versiones[0]
        data = request.get_json(silent=True) or {}
        mapping = data.get('mapping') or data.get('mapeo') or []
        validation = validate_mapping(mapping, strict=True)
        if not validation['valido']:
            return jsonify({'error': 'El mapeo tiene errores críticos. Corrige antes de guardar.', 'validacion': validation}), 400
        mapeo_id = repo.save_mapping(int(version.get('mp_plantilla_id')), mapping, validation, current_user(), nombre=data.get('nombre') or 'Mapeo versionado', version=version.get('version') or '1.0')
        return jsonify({'message': 'Mapeo versionado guardado correctamente.', 'mapeo_id': mapeo_id, 'validacion': validation})

    @bp.route('/version/<int:version_id>/productos', methods=['GET', 'POST'])
    @require_roles(*ALLOWED_ROLES)
    def productos_version(version_id: int):
        if request.method == 'GET':
            return jsonify({'productos': repo.get_products(version_id)})
        data = request.get_json(silent=True) or {}
        productos = data.get('productos') or data.get('products') or []
        productos_guardados = repo.save_products(version_id, productos, current_user())
        return jsonify({'message': 'Catálogo de productos guardado correctamente.', 'productos': productos_guardados})

    @bp.route('/version/<int:version_id>/probar', methods=['POST'])
    @require_roles(*ALLOWED_ROLES)
    def probar_version(version_id: int):
        versiones = [v for v in repo.list_versions() if int(v.get('id') or 0) == version_id]
        if not versiones:
            return jsonify({'error': 'Versión no encontrada.'}), 404
        version = versiones[0]
        plantilla = repo.get_template(int(version.get('mp_plantilla_id') or 0))
        if not plantilla:
            return jsonify({'error': 'Plantilla base no encontrada.'}), 404
        data = request.get_json(silent=True) or {}
        unidad = (data.get('unidad') or '').strip()
        if not unidad:
            return jsonify({'error': 'Debes indicar una unidad para la prueba.'}), 400
        mapping = data.get('mapping') or data.get('mapeo')
        active = repo.get_active_mapping(int(plantilla['id']))
        if not mapping and active:
            mapping = active.get('mapeo') or []
        if not mapping:
            return jsonify({'error': 'No hay mapeo para probar.'}), 400
        productos = data.get('productos') or repo.get_products(version_id)
        limit = max(1, min(50, int(data.get('limite') or data.get('limit') or 20)))
        result = apply_mapping_to_copy(database_path, plantilla['ruta_archivo'], mapping, unidad, os.fspath(output_folder_path()), limit=limit, tipo_formato=plantilla.get('tipo'), productos=productos)
        prueba_id = repo.save_test(int(plantilla['id']), active.get('id') if active else None, unidad, result, current_user())
        return jsonify({'message': 'Prueba versionada generada correctamente.' if result.get('ok') else 'La prueba versionada falló.', 'prueba_id': prueba_id, 'resultado': result, 'download_url': f'/api/motor-plantillas/pruebas/{prueba_id}/descargar' if result.get('ok') else None})

    @bp.route('/version/<int:version_id>/vigente', methods=['POST'])
    @require_roles(*ALLOWED_ROLES)
    def marcar_vigente(version_id: int):
        try:
            result = repo.mark_version_vigente(version_id, current_user())
        except Exception as exc:
            return jsonify({'error': str(exc)}), 400
        return jsonify({'message': 'Plantilla marcada como vigente correctamente.', 'resultado': result})

    @bp.route('/<tipo_formato>/rollback', methods=['POST'])
    @require_roles(*ALLOWED_ROLES)
    def rollback_tipo(tipo_formato: str):
        try:
            result = repo.rollback(tipo_formato, current_user())
        except Exception as exc:
            return jsonify({'error': str(exc)}), 400
        return jsonify({'message': 'Rollback realizado correctamente.', 'resultado': result})



    # ===== ALPHA53 — Motor de Minutas RPP Versionadas =====
    @bp.route('/minutas-rpp', methods=['GET'])
    @require_roles(*ALLOWED_ROLES)
    def listar_minutas_rpp():
        mes = request.args.get('mes', type=int)
        anio = request.args.get('anio', type=int) or request.args.get('año', type=int)
        return jsonify({'minutas': listar_minutas(database_path, mes=mes, anio=anio)})

    @bp.route('/minutas-rpp/vigente', methods=['GET'])
    @require_roles(*ALLOWED_ROLES)
    def minuta_rpp_vigente():
        user = current_user()
        mes = request.args.get('mes', type=int)
        anio = request.args.get('anio', type=int) or request.args.get('año', type=int)
        minuta = obtener_minuta_vigente(database_path, mes=mes, anio=anio, fundacion_id=user['fundacion_id'], corporacion_id=1)
        if not minuta:
            return jsonify({'error': 'No existe minuta RPP vigente para el periodo seleccionado.'}), 404
        return jsonify({'minuta': minuta})

    @bp.route('/minutas-rpp/cargar', methods=['POST'])
    @require_roles(*ALLOWED_ROLES)
    def cargar_minuta_rpp():
        if 'file' not in request.files:
            return jsonify({'error': 'Falta el archivo de minuta RPP.'}), 400
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'Archivo no seleccionado.'}), 400
        ext = os.path.splitext((file.filename or '').lower())[1]
        if ext not in {'.pdf', '.xlsx', '.xls', '.xlsm'}:
            return jsonify({'error': 'Solo se permiten minutas PDF o Excel.'}), 400
        user = current_user()
        safe = sanitize_name(file.filename)
        folder = motor_folder_path() / 'minutas_rpp'
        folder.mkdir(parents=True, exist_ok=True)
        temp_path = folder / f"UPLOAD_MINUTA_{datetime.now().strftime('%Y%m%d%H%M%S')}_{safe}"
        file.save(temp_path)
        try:
            result = guardar_minuta_desde_archivo(database_path, str(temp_path), {
                'codigo': request.form.get('codigo') or 'F2.G36.PP',
                'nombre': request.form.get('nombre') or 'Ración Para Preparar Mensual',
                'version': request.form.get('version') or '1.0',
                'mes': request.form.get('mes') or datetime.now().month,
                'anio': request.form.get('anio') or request.form.get('año') or datetime.now().year,
                'fecha_elaboracion': request.form.get('fecha_elaboracion') or '',
                'estado': request.form.get('estado') or 'borrador',
                'fundacion_id': user['fundacion_id'],
                'corporacion_id': 1,
                'usuario_id': user['usuario_id'],
                'observaciones': request.form.get('observaciones') or '',
            }, destino_folder=str(folder))
            grupos = result.get('extraccion', {}).get('grupos') or []
            productos = sum(len(grupo.get('productos') or []) for grupo in grupos)
            if not grupos or not productos:
                raise ValueError('La minuta no contiene grupos y productos suficientes para generar RPP.')
            vigencia = marcar_minuta_vigente(
                database_path, int(result['version_id']), user.get('usuario_id')
            )
        except Exception as exc:
            return jsonify({'error': f'No se pudo procesar la minuta RPP: {exc}'}), 400
        return jsonify({
            'message': 'Minuta RPP cargada, validada y marcada como vigente.',
            'vigencia': vigencia,
            **result,
        })

    @bp.route('/minutas-rpp/<int:version_id>/vigente', methods=['POST'])
    @require_roles(*ALLOWED_ROLES)
    def marcar_minuta_rpp_vigente(version_id: int):
        try:
            result = marcar_minuta_vigente(database_path, version_id, current_user().get('usuario_id'))
        except Exception as exc:
            return jsonify({'error': str(exc)}), 400
        return jsonify({'message': 'Minuta RPP marcada como vigente.', 'resultado': result})

    app.register_blueprint(bp)
