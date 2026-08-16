from __future__ import annotations

import os
from flask import Blueprint, jsonify, request, send_from_directory
from modules.seguridad.tenant_context import tenant_path

from .repository import BillingRepository, now_iso
from .schema import ALL_MODULES, CREDIT_COSTS, METODOS_PAGO, ESTADOS_SUSCRIPCION
from .services import BillingService, register_billing_middleware


def payload() -> dict:
    if request.is_json:
        return request.get_json(silent=True) or {}
    data = request.form.to_dict()
    if not data:
        data = request.args.to_dict()
    return data


def allowed_payment_file(filename: str) -> bool:
    return os.path.splitext((filename or '').lower())[1] in {'.pdf', '.png', '.jpg', '.jpeg', '.doc', '.docx', '.xlsx', '.xls', '.txt'}


def require_superadmin(repo: BillingRepository):
    if not repo.is_superadmin():
        return jsonify({'error': 'Solo SUPERADMIN puede realizar esta acción.'}), 403
    return None


def register_facturacion(app, database_path: str, upload_folder: str) -> None:
    module_upload = tenant_path(upload_folder, 'facturacion')
    os.makedirs(module_upload, exist_ok=True)
    repo = BillingRepository(database_path)
    service = BillingService(repo, module_upload)
    register_billing_middleware(app, database_path, module_upload)

    bp = Blueprint('facturacion_suscripcion', __name__, url_prefix='/api/facturacion')

    @bp.route('/catalogos', methods=['GET'])
    def catalogos():
        return jsonify({
            'modulos': ALL_MODULES,
            'metodos_pago': METODOS_PAGO,
            'estados_suscripcion': ESTADOS_SUSCRIPCION,
            'costos_credito': CREDIT_COSTS,
            'paquetes': service.list_paquetes(),
            'planes': service.list_planes(),
        }), 200

    @bp.route('/dashboard', methods=['GET'])
    def dashboard():
        return jsonify(service.dashboard()), 200

    @bp.route('/mi-suscripcion', methods=['GET'])
    def mi_suscripcion():
        return jsonify({
            'suscripcion': service.get_subscription(),
            'movimientos': service.list_movimientos(limit=100),
            'pagos': service.list_pagos(limit=100),
        }), 200

    @bp.route('/planes', methods=['GET', 'POST'])
    def planes():
        if request.method == 'GET':
            return jsonify({'planes': service.list_planes()}), 200
        denied = require_superadmin(repo)
        if denied:
            return denied
        try:
            plan = service.create_or_update_plan(payload())
            return jsonify({'message': 'Plan creado correctamente.', 'plan': plan}), 201
        except Exception as exc:
            return jsonify({'error': str(exc)}), 400

    @bp.route('/planes/<int:plan_id>', methods=['PUT', 'PATCH', 'DELETE'])
    def plan_detalle(plan_id: int):
        denied = require_superadmin(repo)
        if denied:
            return denied
        try:
            if request.method == 'DELETE':
                plan = service.delete_or_disable_plan(plan_id)
                return jsonify({'message': 'Plan inactivado correctamente.', 'plan': plan}), 200
            plan = service.create_or_update_plan(payload(), plan_id)
            return jsonify({'message': 'Plan actualizado correctamente.', 'plan': plan}), 200
        except Exception as exc:
            return jsonify({'error': str(exc)}), 400

    @bp.route('/paquetes-creditos', methods=['GET', 'POST'])
    def paquetes_creditos():
        if request.method == 'GET':
            return jsonify({'paquetes': service.list_paquetes()}), 200
        denied = require_superadmin(repo)
        if denied:
            return denied
        try:
            paquete = service.save_paquete(payload())
            return jsonify({'message': 'Paquete de créditos creado.', 'paquete': paquete}), 201
        except Exception as exc:
            return jsonify({'error': str(exc)}), 400

    @bp.route('/paquetes-creditos/<int:paquete_id>', methods=['PUT', 'PATCH'])
    def paquete_detalle(paquete_id: int):
        denied = require_superadmin(repo)
        if denied:
            return denied
        try:
            paquete = service.save_paquete(payload(), paquete_id)
            return jsonify({'message': 'Paquete actualizado.', 'paquete': paquete}), 200
        except Exception as exc:
            return jsonify({'error': str(exc)}), 400

    @bp.route('/suscripciones', methods=['GET', 'POST'])
    def suscripciones():
        if request.method == 'GET':
            fundacion_id = request.args.get('fundacion_id', type=int)
            if fundacion_id:
                if not repo.is_superadmin() and repo.current_fundacion_id() != fundacion_id:
                    return jsonify({'error': 'No tienes permiso para ver esta suscripción.'}), 403
                return jsonify({'suscripcion': service.get_subscription(fundacion_id)}), 200
            return jsonify({'suscripciones': service.list_suscripciones()}), 200
        denied = require_superadmin(repo)
        if denied:
            return denied
        try:
            suscripcion = service.upsert_subscription(payload())
            return jsonify({'message': 'Suscripción guardada correctamente.', 'suscripcion': suscripcion}), 200
        except Exception as exc:
            return jsonify({'error': str(exc)}), 400

    @bp.route('/suscripciones/<int:fundacion_id>', methods=['GET', 'PUT', 'PATCH'])
    def suscripcion_fundacion(fundacion_id: int):
        if request.method == 'GET':
            if not repo.is_superadmin() and repo.current_fundacion_id() != fundacion_id:
                return jsonify({'error': 'No tienes permiso para ver esta suscripción.'}), 403
            return jsonify({'suscripcion': service.get_subscription(fundacion_id)}), 200
        denied = require_superadmin(repo)
        if denied:
            return denied
        try:
            suscripcion = service.upsert_subscription(payload(), fundacion_id)
            return jsonify({'message': 'Suscripción actualizada.', 'suscripcion': suscripcion}), 200
        except Exception as exc:
            return jsonify({'error': str(exc)}), 400

    @bp.route('/pagos', methods=['GET', 'POST'])
    def pagos():
        if request.method == 'GET':
            fundacion_id = request.args.get('fundacion_id', type=int)
            return jsonify({'pagos': service.list_pagos(fundacion_id=fundacion_id)}), 200
        if repo.context().get('rol') not in {'SUPERADMIN', 'GERENTE', 'AUXILIAR_ADMINISTRATIVO'}:
            return jsonify({'error': 'No tienes permiso para registrar pagos.'}), 403
        try:
            data = payload()
            if not repo.is_superadmin():
                data['fundacion_id'] = repo.current_fundacion_id()
            file = request.files.get('comprobante') if request.files else None
            if file and not allowed_payment_file(file.filename):
                return jsonify({'error': 'Comprobante no permitido.'}), 400
            result = service.registrar_pago(data, file)
            return jsonify({'message': 'Pago registrado y suscripción actualizada.', **result}), 201
        except Exception as exc:
            return jsonify({'error': str(exc)}), 400

    @bp.route('/pagos/<int:pago_id>/comprobante', methods=['GET'])
    def descargar_comprobante(pago_id: int):
        pago = repo.fetch_one('SELECT * FROM pagos_suscripcion WHERE id=?', (pago_id,))
        if not pago:
            return jsonify({'error': 'Comprobante no encontrado.'}), 404
        if not repo.is_superadmin() and int(pago.get('fundacion_id') or 0) != repo.current_fundacion_id():
            return jsonify({'error': 'No tienes permiso para este comprobante.'}), 403
        if not pago.get('comprobante_ruta') or not os.path.exists(pago['comprobante_ruta']):
            return jsonify({'error': 'Comprobante no encontrado.'}), 404
        carpeta = os.path.dirname(pago['comprobante_ruta'])
        nombre = os.path.basename(pago['comprobante_ruta'])
        return send_from_directory(carpeta, nombre, as_attachment=True)

    @bp.route('/creditos/asignar', methods=['POST'])
    def asignar_creditos():
        denied = require_superadmin(repo)
        if denied:
            return denied
        try:
            mov = service.asignar_creditos(payload())
            return jsonify({'message': 'Créditos asignados correctamente.', 'movimiento': mov, 'suscripcion': service.get_subscription(int(mov['fundacion_id']))}), 201
        except Exception as exc:
            return jsonify({'error': str(exc)}), 400

    @bp.route('/creditos/consumir', methods=['POST'])
    def consumir_creditos_manual():
        denied = require_superadmin(repo)
        if denied:
            return denied
        data = payload()
        try:
            fid = int(data.get('fundacion_id') or repo.current_fundacion_id())
            accion = data.get('accion') or 'exportacion_masiva'
            mov = service.consumir_creditos(fid, accion, data.get('referencia_tipo'), str(data.get('referencia_id') or ''), data.get('descripcion') or '')
            return jsonify({'message': 'Créditos consumidos correctamente.', 'movimiento': mov, 'suscripcion': service.get_subscription(fid)}), 201
        except PermissionError:
            return jsonify({'error': 'Créditos insuficientes.'}), 402
        except Exception as exc:
            return jsonify({'error': str(exc)}), 400

    @bp.route('/creditos/movimientos', methods=['GET'])
    def movimientos_creditos():
        fundacion_id = request.args.get('fundacion_id', type=int)
        return jsonify({'movimientos': service.list_movimientos(fundacion_id=fundacion_id)}), 200

    @bp.route('/consumo', methods=['GET'])
    def consumo():
        fundacion_id = request.args.get('fundacion_id', type=int)
        return jsonify({'movimientos': service.list_movimientos(fundacion_id=fundacion_id, limit=1000)}), 200

    @bp.route('/alertas', methods=['GET'])
    def alertas():
        data = service.dashboard()
        return jsonify({'alertas': data.get('alertas', [])}), 200

    @bp.route('/auditoria', methods=['GET'])
    def auditoria():
        if not repo.is_superadmin():
            return jsonify({'error': 'Solo SUPERADMIN puede ver auditoría de facturación.'}), 403
        rows = repo.fetch_all("SELECT * FROM auditoria_facturacion ORDER BY fecha DESC LIMIT 500")
        return jsonify({'auditoria': rows}), 200

    app.register_blueprint(bp)
