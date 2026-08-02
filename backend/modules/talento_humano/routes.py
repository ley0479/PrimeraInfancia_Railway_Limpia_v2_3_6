from __future__ import annotations

from flask import Blueprint, jsonify, request

from .services import TalentoHumanoService, normalizar_registro

bp = Blueprint('talento_humano_core', __name__, url_prefix='/api/talento-core')


@bp.get('/estado')
def estado():
    service = TalentoHumanoService()
    return jsonify({'integracion': service.resumen_integracion()})


@bp.get('/fuente-maestra')
def fuente_maestra():
    return jsonify(TalentoHumanoService().fuente_maestra())


@bp.post('/sincronizar')
def sincronizar():
    service = TalentoHumanoService()
    resultado = service.sincronizar_global(origen='talento_core_endpoint')
    return jsonify({'resultado': resultado, 'integracion': service.resumen_integracion()})


@bp.post('/manual')
def manual():
    data = request.get_json(silent=True) or {}
    registro = normalizar_registro(data, archivo='manual')
    if not registro['documento'] or not registro['nombre']:
        return jsonify({'error': 'Nombre y documento son obligatorios.'}), 400
    service = TalentoHumanoService()
    resultado = service.guardar_registros([registro], origen='talento_core_manual')
    return jsonify({'resultado': resultado, 'integracion': service.resumen_integracion()})
