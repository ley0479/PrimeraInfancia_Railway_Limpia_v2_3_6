"""API del Motor Inteligente de Gestión del Proyecto."""
from __future__ import annotations

from datetime import date
from typing import Any

from flask import Blueprint, g, jsonify, request, send_file

from modules.seguridad.services import require_roles

from .repository import MotorGestionRepository
from .services import normalize_text, safe_period, task_role_can_edit

ALL_ROLES = {"SUPERADMIN", "GERENTE", "COORDINADOR", "AUXILIAR_ADMINISTRATIVO", "DOCENTE", "NUTRICIONISTA", "PSICOSOCIAL"}
COORDINATION_ROLES = {"SUPERADMIN", "GERENTE", "COORDINADOR", "AUXILIAR_ADMINISTRATIVO"}
APPROVAL_ROLES = {"SUPERADMIN", "GERENTE", "COORDINADOR"}


def _user() -> dict[str, Any]:
    current = getattr(g, "current_user", None) or {}
    return {
        **current,
        "id": current.get("id"),
        "username": current.get("username") or current.get("email") or "sistema",
        "rol": normalize_text(current.get("rol")),
        "fundacion_id": int(current.get("fundacion_id") or 1),
    }


def _payload() -> dict[str, Any]:
    return request.get_json(silent=True) or {}


def register_routes(app, database_path: str, data_dir: str, output_folder: str) -> None:
    repo = MotorGestionRepository(database_path, data_dir, output_folder)
    repo.init_schema()
    bp = Blueprint("motor_gestion_proyecto", __name__, url_prefix="/api/motor-gestion-proyecto")

    @bp.route("/salud", methods=["GET"])
    def health():
        return jsonify({"status": "ok", "module": "motor_gestion_proyecto", "schema_version": 1, "version": "2.5.3"}), 200

    @bp.route("/dashboard", methods=["GET"])
    def dashboard():
        user = _user()
        period = request.args.get("periodo") or date.today().strftime("%Y-%m")
        expediente_id = request.args.get("expediente_id", type=int)
        return jsonify(repo.dashboard(user["fundacion_id"], period, expediente_id, user=user)), 200

    @bp.route("/sincronizar", methods=["POST"])
    @require_roles(*COORDINATION_ROLES)
    def synchronize():
        user = _user()
        try:
            result = repo.synchronize(user["fundacion_id"], user)
            return jsonify({"message": "Motor sincronizado con los módulos existentes.", "resultado": result}), 200
        except Exception as exc:
            return jsonify({"error": str(exc)}), 400

    @bp.route("/tareas", methods=["GET", "POST"])
    def tasks():
        user = _user()
        if request.method == "POST":
            if user["rol"] not in COORDINATION_ROLES:
                return jsonify({"error": "Solo coordinación puede crear tareas manuales."}), 403
            try:
                task = repo.create_manual_task(user["fundacion_id"], _payload(), user)
                return jsonify({"message": "Tarea creada.", "tarea": task}), 201
            except Exception as exc:
                return jsonify({"error": str(exc)}), 400
        filters = {
            "periodo": request.args.get("periodo"),
            "expediente_id": request.args.get("expediente_id", type=int),
            "estado": request.args.get("estado"),
            "prioridad": request.args.get("prioridad"),
            "fuente_modulo": request.args.get("fuente_modulo"),
            "componente": request.args.get("componente"),
            "tipo_tarea": request.args.get("tipo_tarea"),
            "unidad": request.args.get("unidad"),
            "buscar": request.args.get("buscar"),
            "solo_abiertas": str(request.args.get("solo_abiertas") or "").lower() in {"1", "true", "si", "sí"},
        }
        if user["rol"] not in COORDINATION_ROLES:
            filters["responsable_id"] = user.get("id")
        return jsonify({"tareas": repo.list_tasks(user["fundacion_id"], filters)}), 200

    @bp.route("/tareas/<int:task_id>", methods=["GET", "PATCH"])
    def task_detail(task_id: int):
        user = _user()
        task = repo.task(user["fundacion_id"], task_id)
        if not task:
            return jsonify({"error": "Tarea no encontrada."}), 404
        if user["rol"] not in COORDINATION_ROLES and not task_role_can_edit(task, user):
            return jsonify({"error": "No tienes permiso sobre esta tarea."}), 403
        if request.method == "GET":
            task["dependencias"] = repo.list_dependencies(user["fundacion_id"], task_id)
            return jsonify({"tarea": task}), 200
        try:
            updated = repo.update_task(user["fundacion_id"], task_id, _payload(), user, allow_review=user["rol"] in COORDINATION_ROLES)
            return jsonify({"message": "Tarea actualizada.", "tarea": updated}), 200
        except PermissionError as exc:
            return jsonify({"error": str(exc)}), 403
        except LookupError as exc:
            return jsonify({"error": str(exc)}), 404
        except Exception as exc:
            return jsonify({"error": str(exc)}), 400

    @bp.route("/tareas/<int:task_id>/dependencias", methods=["GET", "POST"])
    def dependencies(task_id: int):
        user = _user()
        if request.method == "GET":
            return jsonify({"dependencias": repo.list_dependencies(user["fundacion_id"], task_id)}), 200
        if user["rol"] not in COORDINATION_ROLES:
            return jsonify({"error": "Solo coordinación puede definir dependencias."}), 403
        data = _payload()
        try:
            result = repo.add_dependency(user["fundacion_id"], task_id, int(data.get("depende_de_tarea_id") or 0), user, bool(data.get("obligatoria", True)))
            return jsonify({"message": "Dependencia registrada.", "dependencias": result}), 201
        except LookupError as exc:
            return jsonify({"error": str(exc)}), 404
        except Exception as exc:
            return jsonify({"error": str(exc)}), 400

    @bp.route("/recordatorios", methods=["GET"])
    def reminders():
        user = _user()
        unread = str(request.args.get("no_leidos") or "").lower() in {"1", "true", "si", "sí"}
        return jsonify({"recordatorios": repo.reminders(user["fundacion_id"], user=user, unread_only=unread)}), 200

    @bp.route("/recordatorios/<int:reminder_id>/leer", methods=["POST"])
    def reminder_read(reminder_id: int):
        user = _user()
        if not repo.mark_reminder_read(user["fundacion_id"], reminder_id, user):
            return jsonify({"error": "Recordatorio no encontrado."}), 404
        return jsonify({"message": "Recordatorio marcado como leído."}), 200

    @bp.route("/productos/preparar", methods=["POST"])
    @require_roles(*COORDINATION_ROLES)
    def prepare_products():
        user = _user()
        data = _payload()
        try:
            result = repo.prepare_monthly_products(
                user["fundacion_id"], safe_period(data.get("periodo")), int(data.get("expediente_id") or 0) or None, user,
            )
            return jsonify({"message": "Borradores operativos preparados para revisión.", "resultado": result}), 201
        except Exception as exc:
            return jsonify({"error": str(exc)}), 400

    @bp.route("/productos", methods=["GET"])
    def products():
        user = _user()
        return jsonify({"productos": repo.list_products(user["fundacion_id"], request.args.get("periodo"), request.args.get("expediente_id", type=int))}), 200

    @bp.route("/productos/<int:product_id>/descargar", methods=["GET"])
    def product_download(product_id: int):
        user = _user()
        found = repo.product_path(user["fundacion_id"], product_id)
        if not found:
            return jsonify({"error": "Producto no encontrado o integridad inválida."}), 404
        path, name, mime = found
        repo.audit(user["fundacion_id"], user, "DESCARGAR_PRODUCTO", "mgp_productos", product_id, {"archivo": name})
        return send_file(path, as_attachment=True, download_name=name, mimetype=mime)

    @bp.route("/productos/<int:product_id>/<string:action>", methods=["POST"])
    @require_roles(*APPROVAL_ROLES)
    def product_review(product_id: int, action: str):
        user = _user()
        try:
            product = repo.review_product(user["fundacion_id"], product_id, action, user)
            return jsonify({"message": "Producto actualizado.", "producto": product}), 200
        except LookupError as exc:
            return jsonify({"error": str(exc)}), 404
        except Exception as exc:
            return jsonify({"error": str(exc)}), 400

    @bp.route("/cierres", methods=["GET", "POST"])
    def closures():
        user = _user()
        if request.method == "GET":
            return jsonify({"cierres": repo.list_closures(user["fundacion_id"], request.args.get("periodo"))}), 200
        if user["rol"] not in COORDINATION_ROLES:
            return jsonify({"error": "Solo coordinación puede preparar cierres."}), 403
        data = _payload()
        closure = repo.prepare_closure(user["fundacion_id"], safe_period(data.get("periodo")), int(data.get("expediente_id") or 0) or None, user)
        return jsonify({"message": "Cierre mensual preparado como borrador.", "cierre": closure}), 201

    @bp.route("/cierres/<int:closure_id>/<string:action>", methods=["POST"])
    @require_roles(*APPROVAL_ROLES)
    def closure_review(closure_id: int, action: str):
        user = _user()
        try:
            result = repo.review_closure(user["fundacion_id"], closure_id, action, user, _payload().get("observaciones"))
            return jsonify({"message": "Cierre mensual actualizado.", "cierre": result}), 200
        except LookupError as exc:
            return jsonify({"error": str(exc)}), 404
        except Exception as exc:
            return jsonify({"error": str(exc)}), 400

    @bp.route("/reglas", methods=["GET"])
    def rules():
        user = _user()
        return jsonify({"reglas": repo.rules(user["fundacion_id"])}), 200

    app.register_blueprint(bp)
