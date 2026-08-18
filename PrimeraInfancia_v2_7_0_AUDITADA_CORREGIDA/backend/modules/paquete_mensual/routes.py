from __future__ import annotations

import os

from flask import Blueprint, g, jsonify, request, send_file

from modules.seguridad.services import require_roles

from .services import PaqueteMensualService


ALLOWED_ROLES = ('SUPERADMIN', 'GERENTE', 'COORDINADOR', 'AUXILIAR_ADMINISTRATIVO')


def current_user() -> dict:
    user = getattr(g, 'current_user', {}) or {}
    return {
        'id': user.get('id') or user.get('usuario_id'),
        'username': user.get('username') or user.get('email') or 'sistema',
        'email': user.get('email'),
        'rol': user.get('rol') or 'SUPERADMIN',
        'fundacion_id': int(user.get('fundacion_id') or 1),
        'raw': user,
    }


def consumir_creditos_paquete(database_path: str, user: dict, referencia_id: str = '') -> dict:
    """Descuenta créditos del paquete mensual si el módulo de facturación está disponible."""
    try:
        from modules.facturacion_suscripcion.repository import BillingRepository
        from modules.facturacion_suscripcion.services import BillingService
        repo = BillingRepository(database_path)
        service = BillingService(repo)
        service.init()
        return service.consumir_creditos(
            int(user.get('fundacion_id') or 1),
            'paquete_mensual_completo',
            referencia_tipo='paquete_mensual',
            referencia_id=referencia_id,
            descripcion='Generación de paquete mensual completo'
        )
    except PermissionError:
        raise
    except Exception as exc:
        # No se bloquea si el módulo de facturación no está inicializado en una instalación local.
        print(f'No se pudo descontar créditos del paquete mensual: {exc}')
        return {}


def register_paquete_mensual(app, database_path: str, output_folder: str, base_dir: str | None = None) -> None:
    service = PaqueteMensualService(database_path, output_folder, base_dir)
    service.init_schema()

    bp = Blueprint('paquete_mensual', __name__, url_prefix='/api/paquete-mensual')

    @bp.before_request
    def _ensure_schema():
        service.init_schema()

    @bp.route('/dashboard', methods=['GET'])
    @require_roles(*ALLOWED_ROLES)
    def dashboard():
        user = current_user()
        paquetes = service.list_packages(20, user.get('fundacion_id'), user.get('rol') == 'SUPERADMIN')
        total = len(paquetes)
        ultimo = paquetes[0] if paquetes else None
        return jsonify({
            'total_paquetes': total,
            'ultimo': ultimo,
            'historial': paquetes[:10],
            'costo_creditos': 10,
            'componentes': [
                'Bienestarina',
                'RPP',
                'RAM',
                'Relación del mes',
                'Cuentas de cobro',
                'Informe nutricional',
                'Informe de novedades',
                'Informe de talento humano',
                'Reporte gerencial',
                'Auditoría mensual',
            ]
        })

    @bp.route('/historial', methods=['GET'])
    @require_roles(*ALLOWED_ROLES)
    def historial():
        user = current_user()
        limit = int(request.args.get('limit') or 100)
        return jsonify({'paquetes': service.list_packages(limit, user.get('fundacion_id'), user.get('rol') == 'SUPERADMIN')})

    @bp.route('/generar', methods=['POST'])
    @require_roles(*ALLOWED_ROLES)
    def generar():
        data = request.get_json(silent=True) or request.form.to_dict() or {}
        try:
            mes = int(data.get('mes') or data.get('month') or 0)
            anio = int(data.get('anio') or data.get('año') or data.get('year') or 0)
            if not mes or not anio:
                from datetime import datetime
                hoy = datetime.now()
                mes = mes or hoy.month
                anio = anio or hoy.year
            user = current_user()
            paquete = service.generate_package(mes, anio, user, data)
            return jsonify({
                'message': 'Paquete mensual completo generado correctamente.',
                'paquete': paquete,
                'consumo_creditos': {'accion': 'paquete_mensual_completo', 'creditos': 10, 'control': 'middleware_facturacion'},
            })
        except Exception as exc:
            return jsonify({'error': f'No se pudo generar el paquete mensual: {exc}'}), 500

    @bp.route('/<int:paquete_id>/archivos', methods=['GET'])
    @require_roles(*ALLOWED_ROLES)
    def archivos(paquete_id: int):
        return jsonify({'archivos': service.list_package_files(paquete_id)})

    @bp.route('/<int:paquete_id>/descargar', methods=['GET'])
    @require_roles(*ALLOWED_ROLES)
    def descargar(paquete_id: int):
        paquete = service.get_package(paquete_id)
        if not paquete:
            return jsonify({'error': 'Paquete no encontrado.'}), 404
        ruta = paquete.get('ruta_zip') or ''
        if not ruta or not os.path.exists(ruta):
            reconstruido = service.reconstruir_zip_paquete(paquete_id)
            if reconstruido and os.path.exists(reconstruido):
                ruta = str(reconstruido)
                paquete = service.get_package(paquete_id) or paquete
            else:
                return jsonify({
                    'error': 'Archivo ZIP del paquete no encontrado. Genere nuevamente el paquete mensual o revise que la carpeta backend/archivos_actualizados/paquete_mensual exista.'
                }), 404
        return send_file(ruta, as_attachment=True, download_name=paquete.get('nombre_archivo') or os.path.basename(ruta))

    app.register_blueprint(bp)
