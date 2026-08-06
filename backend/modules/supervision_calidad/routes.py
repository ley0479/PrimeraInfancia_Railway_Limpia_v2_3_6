"""API del Centro Inteligente de Supervisión, Auditoría y Calidad."""
from __future__ import annotations

from datetime import date
from typing import Any

from flask import Blueprint, g, jsonify, request, send_file

from modules.seguridad.services import require_roles

from .repository import CentroSupervisionRepository
from .services import normalize, parse_json, unit_key

ALL_ROLES = {"SUPERADMIN", "GERENTE", "COORDINADOR", "AUXILIAR_ADMINISTRATIVO", "DOCENTE", "NUTRICIONISTA", "PSICOSOCIAL"}
COORDINATION_ROLES = {"SUPERADMIN", "GERENTE", "COORDINADOR", "AUXILIAR_ADMINISTRATIVO"}
APPROVAL_ROLES = {"SUPERADMIN", "GERENTE", "COORDINADOR"}


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
    values = parse_json(user.get("unidades"), None)
    if isinstance(values, str):
        values = [part.strip() for part in values.split(",") if part.strip()]
    if isinstance(values, list):
        return [str(value).strip() for value in values if str(value).strip()]
    return []


def _can_access_unit(unit_name: str, user: dict[str, Any]) -> bool:
    allowed = _allowed_units(user)
    if allowed is None:
        return True
    return unit_key(unit_name) in {unit_key(value) for value in allowed}


def register_routes(app, database_path: str, data_dir: str, output_folder: str) -> None:
    repo = CentroSupervisionRepository(database_path, data_dir, output_folder)
    repo.init_schema()
    bp = Blueprint("supervision_calidad", __name__, url_prefix="/api/supervision-calidad")

    def _require_supervision(supervision_id: int, user: dict[str, Any]) -> dict[str, Any]:
        item = repo.supervision(user["fundacion_id"], supervision_id)
        if not item:
            raise LookupError("Supervisión no encontrada.")
        if not _can_access_unit(item.get("unidad_nombre") or "", user):
            raise PermissionError("No tienes permiso sobre esta UCA.")
        return item

    def _require_finding(finding_id: int, user: dict[str, Any]) -> dict[str, Any]:
        item = repo.finding(user["fundacion_id"], finding_id)
        if not item:
            raise LookupError("Hallazgo no encontrado.")
        if item.get("unidad_nombre") and not _can_access_unit(item["unidad_nombre"], user):
            raise PermissionError("No tienes permiso sobre esta UCA.")
        return item

    @bp.route("/salud", methods=["GET"])
    def health():
        return jsonify({"status": "ok", "module": "supervision_calidad", "schema_version": 1, "version": "2.5.4"}), 200

    @bp.route("/expedientes", methods=["GET"])
    def expedientes():
        user = _user()
        rows = [row for row in repo.expedientes(user["fundacion_id"]) if _can_access_unit(row.get("unidad_nombre") or "", user)]
        return jsonify({"expedientes": rows}), 200

    @bp.route("/dashboard", methods=["GET"])
    def dashboard():
        user = _user()
        data = repo.dashboard(user["fundacion_id"], {"vigencia": request.args.get("vigencia"), "unidad": request.args.get("unidad")})
        if _allowed_units(user) is not None:
            data["supervisiones"] = [row for row in data.get("supervisiones", []) if _can_access_unit(row.get("unidad_nombre") or "", user)]
            data["hallazgos"] = [row for row in data.get("hallazgos", []) if _can_access_unit(row.get("unidad_nombre") or "", user)]
            data["planes"] = [row for row in data.get("planes", []) if _can_access_unit(row.get("unidad_nombre") or "", user)]
        return jsonify(data), 200

    @bp.route("/supervisiones", methods=["GET", "POST"])
    def supervisions():
        user = _user()
        if request.method == "POST":
            if user["rol"] not in COORDINATION_ROLES:
                return jsonify({"error": "Solo coordinación puede programar supervisiones."}), 403
            try:
                item = repo.create_supervision(user["fundacion_id"], _payload(), user)
                return jsonify({"message": "Supervisión preparada con lista de verificación.", "supervision": item}), 201
            except Exception as exc:
                return jsonify({"error": str(exc)}), 400
        rows = repo.list_supervisions(user["fundacion_id"], {"estado": request.args.get("estado"), "vigencia": request.args.get("vigencia"), "unidad": request.args.get("unidad"), "tipo": request.args.get("tipo")})
        rows = [row for row in rows if _can_access_unit(row.get("unidad_nombre") or "", user)]
        return jsonify({"supervisiones": rows}), 200

    @bp.route("/supervisiones/<int:supervision_id>", methods=["GET", "PATCH"])
    def supervision_detail(supervision_id: int):
        user = _user()
        try:
            item = _require_supervision(supervision_id, user)
            if request.method == "GET":
                return jsonify({"supervision": item}), 200
            if user["rol"] not in COORDINATION_ROLES:
                return jsonify({"error": "No tienes permiso para modificar la supervisión."}), 403
            updated = repo.update_supervision(user["fundacion_id"], supervision_id, _payload(), user, allow_close=user["rol"] in APPROVAL_ROLES)
            return jsonify({"message": "Supervisión actualizada.", "supervision": updated}), 200
        except LookupError as exc:
            return jsonify({"error": str(exc)}), 404
        except PermissionError as exc:
            return jsonify({"error": str(exc)}), 403
        except Exception as exc:
            return jsonify({"error": str(exc)}), 400

    @bp.route("/verificaciones/<int:verification_id>", methods=["PATCH"])
    def verification_update(verification_id: int):
        user = _user()
        if user["rol"] not in COORDINATION_ROLES:
            return jsonify({"error": "Solo el equipo de coordinación o supervisión puede evaluar criterios."}), 403
        try:
            item = repo.update_verification(user["fundacion_id"], verification_id, _payload(), user)
            return jsonify({"message": "Criterio evaluado. Los hallazgos requieren creación y validación explícita.", "verificacion": item}), 200
        except LookupError as exc:
            return jsonify({"error": str(exc)}), 404
        except Exception as exc:
            return jsonify({"error": str(exc)}), 400

    @bp.route("/hallazgos", methods=["GET", "POST"])
    def findings():
        user = _user()
        if request.method == "POST":
            if user["rol"] not in COORDINATION_ROLES:
                return jsonify({"error": "No tienes permiso para registrar hallazgos."}), 403
            try:
                item = repo.create_finding(user["fundacion_id"], _payload(), user)
                return jsonify({"message": "Hallazgo registrado sin alterar los registros fuente.", "hallazgo": item}), 201
            except Exception as exc:
                return jsonify({"error": str(exc)}), 400
        rows = repo.list_findings(user["fundacion_id"], {"estado": request.args.get("estado"), "nivel_riesgo": request.args.get("nivel_riesgo"), "componente": request.args.get("componente"), "supervision_id": request.args.get("supervision_id", type=int), "unidad": request.args.get("unidad")})
        rows = [row for row in rows if not row.get("unidad_nombre") or _can_access_unit(row["unidad_nombre"], user)]
        return jsonify({"hallazgos": rows}), 200

    @bp.route("/hallazgos/<int:finding_id>", methods=["GET", "PATCH"])
    def finding_detail(finding_id: int):
        user = _user()
        try:
            item = _require_finding(finding_id, user)
            if request.method == "GET":
                return jsonify({"hallazgo": item}), 200
            if user["rol"] not in COORDINATION_ROLES:
                return jsonify({"error": "No tienes permiso para actualizar hallazgos."}), 403
            updated = repo.update_finding(user["fundacion_id"], finding_id, _payload(), user, allow_close=user["rol"] in APPROVAL_ROLES)
            return jsonify({"message": "Hallazgo actualizado con trazabilidad.", "hallazgo": updated}), 200
        except LookupError as exc:
            return jsonify({"error": str(exc)}), 404
        except PermissionError as exc:
            return jsonify({"error": str(exc)}), 403
        except Exception as exc:
            return jsonify({"error": str(exc)}), 400

    @bp.route("/planes", methods=["GET", "POST"])
    def plans():
        user = _user()
        if request.method == "POST":
            if user["rol"] not in COORDINATION_ROLES:
                return jsonify({"error": "Solo coordinación puede crear planes de mejora."}), 403
            try:
                item = repo.create_plan(user["fundacion_id"], _payload(), user)
                return jsonify({"message": "Plan de mejora creado como borrador.", "plan": item}), 201
            except Exception as exc:
                return jsonify({"error": str(exc)}), 400
        rows = repo.list_plans(user["fundacion_id"], {"estado": request.args.get("estado"), "unidad": request.args.get("unidad")})
        rows = [row for row in rows if not row.get("unidad_nombre") or _can_access_unit(row["unidad_nombre"], user)]
        return jsonify({"planes": rows}), 200

    @bp.route("/planes/<int:plan_id>", methods=["GET", "PATCH"])
    def plan_detail(plan_id: int):
        user = _user()
        item = repo.plan(user["fundacion_id"], plan_id)
        if not item:
            return jsonify({"error": "Plan no encontrado."}), 404
        if item.get("unidad_nombre") and not _can_access_unit(item["unidad_nombre"], user):
            return jsonify({"error": "No tienes permiso sobre esta UCA."}), 403
        if request.method == "GET":
            return jsonify({"plan": item}), 200
        if user["rol"] not in COORDINATION_ROLES:
            return jsonify({"error": "No tienes permiso para modificar planes."}), 403
        try:
            updated = repo.update_plan(user["fundacion_id"], plan_id, _payload(), user, allow_review=user["rol"] in APPROVAL_ROLES)
            return jsonify({"message": "Plan actualizado.", "plan": updated}), 200
        except PermissionError as exc:
            return jsonify({"error": str(exc)}), 403
        except Exception as exc:
            return jsonify({"error": str(exc)}), 400

    @bp.route("/planes/<int:plan_id>/acciones", methods=["POST"])
    @require_roles(*COORDINATION_ROLES)
    def create_action(plan_id: int):
        user = _user()
        try:
            item = repo.create_action(user["fundacion_id"], plan_id, _payload(), user)
            return jsonify({"message": "Acción de mejora creada y enlazada al Motor de Gestión.", "accion": item}), 201
        except LookupError as exc:
            return jsonify({"error": str(exc)}), 404
        except Exception as exc:
            return jsonify({"error": str(exc)}), 400

    @bp.route("/acciones/<int:action_id>", methods=["GET", "PATCH"])
    def action_detail(action_id: int):
        user = _user()
        item = repo.action(user["fundacion_id"], action_id)
        if not item:
            return jsonify({"error": "Acción no encontrada."}), 404
        if request.method == "GET":
            return jsonify({"accion": item}), 200
        if user["rol"] not in COORDINATION_ROLES:
            return jsonify({"error": "No tienes permiso para modificar acciones."}), 403
        try:
            updated = repo.update_action(user["fundacion_id"], action_id, _payload(), user, allow_validate=user["rol"] in APPROVAL_ROLES)
            return jsonify({"message": "Acción actualizada.", "accion": updated}), 200
        except Exception as exc:
            return jsonify({"error": str(exc)}), 400

    @bp.route("/seguimientos/<string:entity_type>/<int:entity_id>", methods=["GET", "POST"])
    def followups(entity_type: str, entity_id: int):
        user = _user()
        if request.method == "GET":
            return jsonify({"seguimientos": repo.list_followups(user["fundacion_id"], entity_type, entity_id)}), 200
        if user["rol"] not in COORDINATION_ROLES:
            return jsonify({"error": "No tienes permiso para registrar seguimientos."}), 403
        try:
            item = repo.add_followup(user["fundacion_id"], entity_type, entity_id, _payload(), user)
            return jsonify({"message": "Seguimiento registrado.", "seguimiento": item}), 201
        except Exception as exc:
            return jsonify({"error": str(exc)}), 400

    @bp.route("/evidencias/<string:entity_type>/<int:entity_id>", methods=["GET", "POST"])
    def evidence(entity_type: str, entity_id: int):
        user = _user()
        if request.method == "GET":
            return jsonify({"evidencias": repo.list_evidence(user["fundacion_id"], entity_type, entity_id)}), 200
        if user["rol"] not in COORDINATION_ROLES:
            return jsonify({"error": "No tienes permiso para cargar evidencias de supervisión."}), 403
        try:
            item = repo.add_evidence(user["fundacion_id"], entity_type, entity_id, request.files.get("file"), request.form.get("descripcion", ""), user)
            return jsonify({"message": "Evidencia cargada con huella de integridad.", "evidencia": item}), 201
        except Exception as exc:
            return jsonify({"error": str(exc)}), 400

    @bp.route("/evidencias/<int:evidence_id>/descargar", methods=["GET"])
    def evidence_download(evidence_id: int):
        user = _user()
        found = repo.evidence_path(user["fundacion_id"], evidence_id)
        if not found:
            return jsonify({"error": "Evidencia no encontrada o integridad inválida."}), 404
        path, name, mime = found
        repo.audit(user["fundacion_id"], user, "DESCARGAR_EVIDENCIA", "csc_evidencias", evidence_id, {"archivo": name})
        return send_file(path, as_attachment=True, download_name=name, mimetype=mime)

    @bp.route("/supervisiones/<int:supervision_id>/productos", methods=["POST"])
    @require_roles(*COORDINATION_ROLES)
    def build_products(supervision_id: int):
        user = _user()
        try:
            _require_supervision(supervision_id, user)
            items = repo.build_products(user["fundacion_id"], supervision_id, user)
            return jsonify({"message": "Productos preparados como borradores para revisión.", "productos": items}), 201
        except LookupError as exc:
            return jsonify({"error": str(exc)}), 404
        except Exception as exc:
            return jsonify({"error": str(exc)}), 400

    @bp.route("/productos", methods=["GET"])
    def products():
        user = _user()
        supervision_id = request.args.get("supervision_id", type=int)
        return jsonify({"productos": repo.list_products(user["fundacion_id"], supervision_id)}), 200

    @bp.route("/productos/<int:product_id>/descargar", methods=["GET"])
    def product_download(product_id: int):
        user = _user()
        found = repo.product_path(user["fundacion_id"], product_id)
        if not found:
            return jsonify({"error": "Producto no encontrado o integridad inválida."}), 404
        path, name, mime = found
        repo.audit(user["fundacion_id"], user, "DESCARGAR_PRODUCTO", "csc_productos", product_id, {"archivo": name})
        return send_file(path, as_attachment=True, download_name=name, mimetype=mime)

    app.register_blueprint(bp)
