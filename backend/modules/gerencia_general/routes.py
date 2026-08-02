from __future__ import annotations

from flask import Blueprint, Response, jsonify, request

from .services import GerenciaGeneralService


def register_gerencia_general(app, database_path: str, output_folder: str | None = None) -> None:
    service = GerenciaGeneralService(database_path, output_folder)
    service.init_schema()

    bp = Blueprint('gerencia_general', __name__, url_prefix='/api/gerencia-general')

    @bp.before_request
    def _ensure_schema():
        service.init_schema()

    @bp.route('/dashboard', methods=['GET'])
    def dashboard():
        anio = request.args.get('anio', type=int)
        mes = request.args.get('mes', type=int)
        return jsonify(service.dashboard(anio, mes)), 200

    @bp.route('/licencias', methods=['GET'])
    def licencias():
        anio = request.args.get('anio', type=int)
        mes = request.args.get('mes', type=int)
        data = service.dashboard(anio, mes)
        return jsonify({'licencias': data.get('licencias', [])}), 200

    @bp.route('/alertas', methods=['GET'])
    def alertas():
        anio = request.args.get('anio', type=int)
        mes = request.args.get('mes', type=int)
        data = service.dashboard(anio, mes)
        return jsonify({
            'alertas_pago': data.get('alertas_pago', []),
            'alertas_criticas': data.get('alertas_criticas', []),
            'nutricion_riesgo': data.get('nutricion_riesgo', []),
            'unidades_cobertura_incompleta': data.get('unidades_cobertura_incompleta', []),
            'coordinadores_bajo_cumplimiento': data.get('coordinadores_bajo_cumplimiento', []),
        }), 200

    @bp.route('/exportar/excel', methods=['GET'])
    def exportar_excel():
        anio = request.args.get('anio', type=int)
        mes = request.args.get('mes', type=int)
        data = service.export_excel(anio, mes)
        filename = f"GERENCIA_GENERAL_{anio or 'ACTUAL'}_{mes or ''}.xlsx".replace('__', '_')
        return Response(
            data,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            headers={'Content-Disposition': f'attachment; filename={filename}'}
        )

    @bp.route('/exportar/pdf', methods=['GET'])
    def exportar_pdf():
        anio = request.args.get('anio', type=int)
        mes = request.args.get('mes', type=int)
        data = service.export_pdf(anio, mes)
        filename = f"GERENCIA_GENERAL_{anio or 'ACTUAL'}_{mes or ''}.pdf".replace('__', '_')
        return Response(
            data,
            mimetype='application/pdf',
            headers={'Content-Disposition': f'attachment; filename={filename}'}
        )

    app.register_blueprint(bp)
