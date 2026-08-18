"""API del Centro Inteligente de Planeación y Calendario Operativo."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from flask import Blueprint, g, jsonify, request, send_file

from modules.seguridad.services import require_roles
from .repository import CentroPlaneacionRepository
from .services import COORDINATION_ROLES, normalize, parse_json, unit_key

ALL_ROLES = {"SUPERADMIN", "GERENTE", "COORDINADOR", "AUXILIAR_ADMINISTRATIVO", "DOCENTE", "NUTRICIONISTA", "PSICOSOCIAL"}
EDIT_ROLES = {"SUPERADMIN", "GERENTE", "COORDINADOR", "AUXILIAR_ADMINISTRATIVO", "DOCENTE", "NUTRICIONISTA", "PSICOSOCIAL"}


def _user() -> dict[str, Any]:
    current = getattr(g, "current_user", None) or {}
    return {
        **current,
        "id": current.get("id"),
        "username": current.get("username") or current.get("email") or "sistema",
        "rol": normalize(current.get("rol")),
        "fundacion_id": int(current.get("fundacion_id") or 1),
    }


def _payload() -> dict[str, Any]:
    return request.get_json(silent=True) or {}


def _allowed_units(user: dict[str, Any]) -> list[str] | None:
    if user.get("rol") in COORDINATION_ROLES:
        return None
    values = parse_json(user.get("unidades"), [])
    if isinstance(values, str):
        values = [part.strip() for part in values.split(",") if part.strip()]
    if not isinstance(values, list):
        return []
    return [str(value).strip() for value in values if str(value).strip()]


def _can_access_unit(unit: str | None, user: dict[str, Any]) -> bool:
    allowed = _allowed_units(user)
    if allowed is None:
        return True
    if not unit:
        return False
    return unit_key(unit) in {unit_key(value) for value in allowed}


def register_centro_planeacion(app, database_path: str, data_dir: str, output_folder: str) -> None:
    repo = CentroPlaneacionRepository(database_path, data_dir, output_folder)
    repo.init_schema()
    bp = Blueprint("centro_planeacion", __name__, url_prefix="/api/centro-planeacion")

    def _require_activity(activity_id: int, user: dict[str, Any]) -> dict[str, Any]:
        item = repo.activity(user["fundacion_id"], activity_id)
        if not _can_access_unit(item.get("unidad_nombre"), user):
            raise PermissionError("No tienes permiso sobre esta UCA.")
        if user.get("rol") not in COORDINATION_ROLES:
            assigned = item.get("responsable_id")
            role = normalize(item.get("rol_responsable"))
            if assigned not in (None, user.get("id")) and role not in ("", user.get("rol")):
                raise PermissionError("La actividad está asignada a otro profesional.")
        return item

    @bp.route("/salud", methods=["GET"])
    def health():
        return jsonify({"status": "ok", "module": "centro_planeacion", "schema_version": 1, "version": "2.7.0"}), 200

    @bp.route("/sincronizar", methods=["POST"])
    @require_roles(*ALL_ROLES)
    def synchronize():
        user = _user()
        try:
            return jsonify({"message": "Fuentes sincronizadas sin duplicar actividades.", "resultado": repo.synchronize(user["fundacion_id"], user)}), 200
        except Exception as exc:
            return jsonify({"error": str(exc)}), 400

    @bp.route("/dashboard", methods=["GET"])
    @require_roles(*ALL_ROLES)
    def dashboard():
        user = _user()
        unit = request.args.get("unidad")
        if unit and not _can_access_unit(unit, user):
            return jsonify({"error": "No tienes permiso sobre esta UCA."}), 403
        allowed = _allowed_units(user)
        if not unit and allowed is not None and len(allowed) == 1:
            unit = allowed[0]
        filters = {
            "periodo": request.args.get("periodo"),
            "unidad": unit,
            "componente": request.args.get("componente"),
            "estado": request.args.get("estado"),
            "vista": request.args.get("vista"),
        }
        data = repo.dashboard(user["fundacion_id"], user, filters)
        if allowed is not None and not unit:
            data["actividades"] = [row for row in data.get("actividades", []) if _can_access_unit(row.get("unidad_nombre"), user)]
            allowed_keys = {unit_key(value) for value in allowed}
            data["por_uca"] = [row for row in data.get("por_uca", []) if unit_key(row.get("unidad")) in allowed_keys]
        return jsonify(data), 200

    @bp.route("/actividades", methods=["GET"])
    @require_roles(*ALL_ROLES)
    def activities():
        user = _user()
        unit = request.args.get("unidad")
        if unit and not _can_access_unit(unit, user):
            return jsonify({"error": "No tienes permiso sobre esta UCA."}), 403
        filters = {key: request.args.get(key) for key in ("periodo", "unidad", "componente", "estado", "rol") if request.args.get(key)}
        if user.get("rol") not in COORDINATION_ROLES:
            filters["responsable_id"] = user.get("id")
        rows = repo.list_activities(user["fundacion_id"], filters)
        rows = [row for row in rows if _can_access_unit(row.get("unidad_nombre"), user)]
        return jsonify({"actividades": rows}), 200

    @bp.route("/actividades/<int:activity_id>", methods=["GET", "PATCH"])
    @require_roles(*ALL_ROLES)
    def activity_detail(activity_id: int):
        user = _user()
        try:
            current = _require_activity(activity_id, user)
            if request.method == "GET":
                return jsonify({"actividad": current}), 200
            updated = repo.update_activity(user["fundacion_id"], activity_id, _payload(), user, allow_approve=user.get("rol") in COORDINATION_ROLES)
            return jsonify({"message": "Actividad actualizada con trazabilidad.", "actividad": updated}), 200
        except LookupError as exc:
            return jsonify({"error": str(exc)}), 404
        except PermissionError as exc:
            return jsonify({"error": str(exc)}), 403
        except Exception as exc:
            return jsonify({"error": str(exc)}), 400

    @bp.route("/actividades/<int:activity_id>/dependencias", methods=["POST"])
    @require_roles(*COORDINATION_ROLES)
    def add_dependency(activity_id: int):
        user = _user()
        try:
            _require_activity(activity_id, user)
            parent = int(_payload().get("depende_de_actividad_id") or 0)
            if not parent:
                return jsonify({"error": "depende_de_actividad_id es obligatorio."}), 400
            _require_activity(parent, user)
            return jsonify({"message": "Dependencia registrada.", "actividad": repo.add_dependency(user["fundacion_id"], activity_id, parent, user)}), 201
        except LookupError as exc:
            return jsonify({"error": str(exc)}), 404
        except PermissionError as exc:
            return jsonify({"error": str(exc)}), 403
        except Exception as exc:
            return jsonify({"error": str(exc)}), 400

    @bp.route("/actividades/<int:activity_id>/documentos", methods=["POST"])
    @require_roles(*EDIT_ROLES)
    def prepare_documents(activity_id: int):
        user = _user()
        try:
            _require_activity(activity_id, user)
            types = _payload().get("tipos") or []
            return jsonify({"message": "Documentos preparados como borradores.", "documentos": repo.prepare_documents(user["fundacion_id"], activity_id, types, user)}), 201
        except LookupError as exc:
            return jsonify({"error": str(exc)}), 404
        except PermissionError as exc:
            return jsonify({"error": str(exc)}), 403
        except Exception as exc:
            return jsonify({"error": str(exc)}), 400

    @bp.route("/documentos/<int:document_id>/descargar", methods=["GET"])
    @require_roles(*ALL_ROLES)
    def download_document(document_id: int):
        user = _user()
        try:
            meta = repo.document(user["fundacion_id"], document_id)
            if not _can_access_unit(meta.get("unidad_nombre"), user):
                return jsonify({"error": "No tienes permiso sobre esta UCA."}), 403
            found = repo.document_path(user["fundacion_id"], document_id)
            if not found:
                return jsonify({"error": "Documento no encontrado o integridad inválida."}), 404
            path, name, mime = found
            repo.audit(user["fundacion_id"], user, "DESCARGAR_DOCUMENTO", "cpo_documentos_preparados", document_id, {"archivo": name})
            return send_file(path, as_attachment=True, download_name=name, mimetype=mime)
        except LookupError as exc:
            return jsonify({"error": str(exc)}), 404

    @bp.route("/documentos/<int:document_id>/<string:action>", methods=["POST"])
    @require_roles(*COORDINATION_ROLES)
    def review_document(document_id: int, action: str):
        user = _user()
        try:
            meta = repo.document(user["fundacion_id"], document_id)
            if not _can_access_unit(meta.get("unidad_nombre"), user):
                return jsonify({"error": "No tienes permiso sobre esta UCA."}), 403
            return jsonify({"message": "Documento actualizado.", "documento": repo.review_document(user["fundacion_id"], document_id, action, user)}), 200
        except LookupError as exc:
            return jsonify({"error": str(exc)}), 404
        except Exception as exc:
            return jsonify({"error": str(exc)}), 400

    @bp.route("/reglas", methods=["GET", "POST"])
    @require_roles(*ALL_ROLES)
    def rules():
        user = _user()
        repo.ensure_rules(user["fundacion_id"], user.get("id"))
        if request.method == "POST":
            if user.get("rol") not in COORDINATION_ROLES:
                return jsonify({"error": "Solo coordinación puede configurar reglas."}), 403
            try:
                return jsonify({"message": "Regla registrada.", "regla": repo.create_rule(user["fundacion_id"], _payload(), user)}), 201
            except Exception as exc:
                return jsonify({"error": str(exc)}), 400
        return jsonify({"reglas": repo.list_rules(user["fundacion_id"])}), 200

    @bp.route("/notificaciones/<int:notification_id>/leer", methods=["POST"])
    @require_roles(*ALL_ROLES)
    def read_notification(notification_id: int):
        user = _user()
        try:
            return jsonify({"notificacion": repo.mark_notification_read(user["fundacion_id"], notification_id, user)}), 200
        except LookupError as exc:
            return jsonify({"error": str(exc)}), 404

    @bp.route("/paquetes/mensual", methods=["POST"])
    @require_roles(*ALL_ROLES)
    def monthly_package():
        user = _user(); data = _payload(); period = str(data.get("periodo") or "")[:7]
        if len(period) != 7:
            return jsonify({"error": "periodo debe tener formato AAAA-MM."}), 400
        unit = data.get("unidad")
        if unit and not _can_access_unit(unit, user):
            return jsonify({"error": "No tienes permiso sobre esta UCA."}), 403
        try:
            product = repo.export_monthly_package(user["fundacion_id"], user, period, {"unidad": unit, "vista": data.get("vista")})
            return jsonify({"message": "Paquete preparado como borrador.", "producto": product}), 201
        except Exception as exc:
            return jsonify({"error": str(exc)}), 400

    @bp.route("/paquetes/descargar", methods=["GET"])
    @require_roles(*ALL_ROLES)
    def package_download():
        user = _user(); value = request.args.get("ruta") or ""
        path = repo.package_path(user["fundacion_id"], value)
        if not path:
            return jsonify({"error": "Paquete no encontrado o ruta inválida."}), 404
        return send_file(path, as_attachment=True, download_name=path.name)

    app.register_blueprint(bp)
