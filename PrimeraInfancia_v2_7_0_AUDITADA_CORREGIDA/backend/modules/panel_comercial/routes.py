from __future__ import annotations

from flask import Blueprint, jsonify, request, send_file

from .services import PanelComercialService
from modules.runtime_schema import migration_mode


def payload() -> dict:
    if request.is_json:
        return request.get_json(silent=True) or {}
    data = request.form.to_dict()
    if not data:
        data = request.args.to_dict()
    return data


def register_panel_comercial(app, database_path: str) -> None:
    service = PanelComercialService(database_path)
    service.init_schema(force=migration_mode())
    bp = Blueprint('panel_comercial', __name__, url_prefix='/api/panel-comercial')

    @bp.route('/dashboard', methods=['GET'])
    def dashboard():
        return jsonify(service.dashboard()), 200

    @bp.route('/fundaciones', methods=['GET'])
    def fundaciones():
        return jsonify({'fundaciones': service.fundaciones_resumen(limit=500)}), 200

    @bp.route('/suscripciones', methods=['GET'])
    def suscripciones():
        return jsonify({'suscripciones': service.estado_suscripciones(limit=500)}), 200

    @bp.route('/ingresos', methods=['GET'])
    def ingresos():
        return jsonify({'ingresos': service.ingresos_recientes(limit=500)}), 200

    @bp.route('/consumo-creditos', methods=['GET'])
    def consumo_creditos():
        return jsonify({'movimientos': service.consumo_creditos(limit=500)}), 200

    @bp.route('/alertas-pago', methods=['GET'])
    def alertas_pago():
        return jsonify({'alertas': service.alertas_pago()}), 200

    @bp.route('/tickets', methods=['GET', 'POST'])
    def tickets():
        if request.method == 'GET':
            estado = request.args.get('estado') or None
            return jsonify({'tickets': service.list_tickets(estado=estado), 'catalogos': service.catalogos()}), 200
        try:
            ticket = service.save_ticket(payload())
            return jsonify({'message': 'Ticket creado correctamente.', 'ticket': ticket}), 201
        except PermissionError as exc:
            return jsonify({'error': str(exc)}), 403
        except Exception as exc:
            return jsonify({'error': str(exc)}), 400

    @bp.route('/tickets/<int:ticket_id>', methods=['GET', 'PUT', 'PATCH'])
    def ticket_detalle(ticket_id: int):
        try:
            if request.method == 'GET':
                return jsonify({'ticket': service.get_ticket(ticket_id), 'catalogos': service.catalogos()}), 200
            ticket = service.save_ticket(payload(), ticket_id=ticket_id)
            return jsonify({'message': 'Ticket actualizado correctamente.', 'ticket': ticket}), 200
        except PermissionError as exc:
            return jsonify({'error': str(exc)}), 403
        except Exception as exc:
            return jsonify({'error': str(exc)}), 400

    @bp.route('/tickets/<int:ticket_id>/comentarios', methods=['POST'])
    def ticket_comentarios(ticket_id: int):
        try:
            data = payload()
            comentario = service.add_comment(ticket_id, data.get('comentario') or data.get('observacion') or '')
            return jsonify({'message': 'Comentario agregado.', 'comentario': comentario}), 201
        except PermissionError as exc:
            return jsonify({'error': str(exc)}), 403
        except Exception as exc:
            return jsonify({'error': str(exc)}), 400

    @bp.route('/exportar/excel', methods=['GET'])
    def exportar_excel():
        contenido = service.export_excel()
        from io import BytesIO
        return send_file(
            BytesIO(contenido),
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name='PANEL_COMERCIAL_PRIMERA_INFANCIA.xlsx',
        )

    app.register_blueprint(bp)
