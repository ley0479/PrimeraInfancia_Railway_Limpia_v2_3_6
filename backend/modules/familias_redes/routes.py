"""API de Gestión Integral de Familias, Comunidad y Redes de Apoyo."""
from __future__ import annotations

from typing import Any

from flask import Blueprint, g, jsonify, request, send_file

from modules.seguridad.services import require_roles
from .repository import FamiliasRedesRepository
from .services import normalize_text, parse_json, unit_key

READ_ROLES = {"SUPERADMIN", "GERENTE", "COORDINADOR", "PSICOSOCIAL"}
EDIT_ROLES = {"SUPERADMIN", "GERENTE", "COORDINADOR", "PSICOSOCIAL"}
COORDINATION_ROLES = {"SUPERADMIN", "GERENTE", "COORDINADOR"}


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


def _can_edit(user: dict[str, Any]) -> bool:
    return user.get("rol") in EDIT_ROLES


def _allowed_units(user: dict[str, Any]) -> list[str] | None:
    """Retorna las UCA autorizadas o ``None`` para roles de coordinación.

    Los roles operativos trabajan en modo *fail-closed*: si su sesión no trae
    una asignación explícita de UCA, no se interpreta como acceso global.
    """

    if user.get("rol") in COORDINATION_ROLES:
        return None
    values = parse_json(user.get("unidades"), [])
    if isinstance(values, str):
        values = [part.strip() for part in values.split(",") if part.strip()]
    if not isinstance(values, list):
        return []
    return [str(value).strip() for value in values if str(value).strip()]


def _can_access_unit(unit_name: str | None, user: dict[str, Any]) -> bool:
    allowed = _allowed_units(user)
    if allowed is None:
        return True
    if not unit_name:
        return False
    allowed_keys = {unit_key(value) for value in allowed}
    return unit_key(unit_name) in allowed_keys


def _filter_units(rows: list[dict[str, Any]], user: dict[str, Any]) -> list[dict[str, Any]]:
    return [row for row in rows if _can_access_unit(row.get("unidad_nombre") or row.get("unidad"), user)]


def _scoped_payload(data: dict[str, Any], user: dict[str, Any]) -> dict[str, Any]:
    """Valida o completa la UCA de una operación de escritura."""

    scoped = dict(data)
    allowed = _allowed_units(user)
    if allowed is None:
        return scoped
    unit_name = str(scoped.get("unidad_nombre") or scoped.get("unidad") or "").strip()
    if not unit_name and len(allowed) == 1:
        unit_name = allowed[0]
        scoped["unidad_nombre"] = unit_name
    if not unit_name:
        raise PermissionError("Selecciona una UCA asignada a tu usuario.")
    if not _can_access_unit(unit_name, user):
        raise PermissionError("No tienes permiso sobre esta UCA.")
    return scoped


def register_routes(app, database_path: str, data_dir: str, output_folder: str) -> None:
    repo = FamiliasRedesRepository(database_path, data_dir, output_folder)
    repo.init_schema()
    bp = Blueprint("familias_redes", __name__, url_prefix="/api/familias-redes")

    def _require_family(record_id: int, user: dict[str, Any]) -> dict[str, Any]:
        item = repo.family_record(user["fundacion_id"], record_id)
        if not _can_access_unit(item.get("unidad_nombre"), user):
            raise PermissionError("No tienes permiso sobre esta UCA.")
        return item

    def _require_activity(activity_id: int, user: dict[str, Any]) -> dict[str, Any]:
        item = repo.activity_detail(user["fundacion_id"], activity_id)
        if not _can_access_unit(item.get("unidad_nombre"), user):
            raise PermissionError("No tienes permiso sobre esta UCA.")
        if user.get("rol") == "PSICOSOCIAL" and item.get("profesional_id") not in {None, user.get("id")}:
            raise PermissionError("Esta actividad está asignada a otro profesional.")
        return item

    def _require_commitment(commitment_id: int, user: dict[str, Any]) -> dict[str, Any]:
        item = repo.commitment_detail(user["fundacion_id"], commitment_id)
        if not _can_access_unit(item.get("unidad_nombre"), user):
            raise PermissionError("No tienes permiso sobre esta UCA.")
        return item

    def _require_alert(alert_id: int, user: dict[str, Any]) -> dict[str, Any]:
        item = repo.alert(user["fundacion_id"], alert_id)
        if not _can_access_unit(item.get("unidad_nombre"), user):
            raise PermissionError("No tienes permiso sobre esta UCA.")
        return item

    def _resolve_linked_unit(data: dict[str, Any], user: dict[str, Any]) -> dict[str, Any]:
        """Completa la UCA desde una actividad o expediente referenciado."""

        scoped = dict(data)
        linked_unit = None
        if scoped.get("actividad_id"):
            parent = _require_activity(int(scoped["actividad_id"]), user)
            linked_unit = parent.get("unidad_nombre")
            scoped.setdefault("expediente_uca_id", parent.get("expediente_uca_id"))
        if scoped.get("expediente_familiar_id"):
            parent = _require_family(int(scoped["expediente_familiar_id"]), user)
            family_unit = parent.get("unidad_nombre")
            if linked_unit and unit_key(linked_unit) != unit_key(family_unit):
                raise PermissionError("La actividad y el expediente familiar pertenecen a UCA diferentes.")
            linked_unit = family_unit
            scoped.setdefault("expediente_uca_id", parent.get("expediente_uca_id"))
        direct_unit = str(scoped.get("unidad_nombre") or scoped.get("unidad") or "").strip()
        if linked_unit and direct_unit and unit_key(linked_unit) != unit_key(direct_unit):
            raise PermissionError("La UCA indicada no coincide con la entidad relacionada.")
        if linked_unit:
            scoped["unidad_nombre"] = linked_unit
        return _scoped_payload(scoped, user)

    @bp.route("/salud", methods=["GET"])
    def health():
        return jsonify({"status": "ok", "module": "familias_redes", "schema_version": 1, "version": "2.5.4"}), 200

    @bp.route("/dashboard", methods=["GET"])
    @require_roles(*READ_ROLES)
    def dashboard():
        user = _user()
        requested_unit = request.args.get("unidad")
        allowed = _allowed_units(user)
        if allowed == []:
            return jsonify({"vista": "PROFESIONAL", "resumen": {}, "por_uca": [], "actividades": [], "compromisos": [], "alertas": [], "redes": []}), 200
        if requested_unit and not _can_access_unit(requested_unit, user):
            return jsonify({"error": "No tienes permiso sobre esta UCA."}), 403
        if not requested_unit and allowed is not None and len(allowed) == 1:
            requested_unit = allowed[0]
        filters = {"unidad": requested_unit, "vista_coordinacion": request.args.get("vista") == "coordinacion"}
        data = repo.dashboard(user["fundacion_id"], user, filters)
        if allowed is not None and not requested_unit:
            data["actividades"] = _filter_units(data.get("actividades", []), user)
            data["compromisos"] = _filter_units(data.get("compromisos", []), user)
            data["alertas"] = _filter_units(data.get("alertas", []), user)
            data["por_uca"] = [row for row in data.get("por_uca", []) if _can_access_unit(row.get("unidad"), user)]
            families = _filter_units(repo.list_family_records(user["fundacion_id"], limit=5000), user)
            docs = _filter_units(repo.list_documents(user["fundacion_id"]), user)
            open_commitments = [row for row in data["compromisos"] if normalize_text(row.get("estado")) not in {"CERRADO", "CERRADA", "APROBADO", "APROBADA", "COMPLETADO", "COMPLETADA"}]
            open_alerts = [row for row in data["alertas"] if normalize_text(row.get("estado")) not in {"CERRADO", "CERRADA"}]
            data["resumen"].update({
                "expedientes_familiares": len(families),
                "actividades": len(data["actividades"]),
                "compromisos_abiertos": len(open_commitments),
                "alertas_abiertas": len(open_alerts),
                "documentos_borrador": sum(1 for row in docs if normalize_text(row.get("estado")) == "BORRADOR"),
            })
        return jsonify(data), 200

    @bp.route("/expedientes/sincronizar", methods=["POST"])
    @require_roles(*EDIT_ROLES)
    def sync_records():
        user = _user(); data = _payload()
        try:
            data = _scoped_payload(data, user)
            result = repo.sync_family_records(user["fundacion_id"], int(data.get("expediente_uca_id") or 0) or None, data.get("unidad_nombre") or data.get("unidad"), int(data.get("unidad_id") or 0) or None, user)
            return jsonify({"message": "Expedientes familiares referenciados sin duplicar participantes.", "resultado": result}), 200
        except PermissionError as exc:
            return jsonify({"error": str(exc)}), 403
        except Exception as exc:
            return jsonify({"error": str(exc)}), 400

    @bp.route("/expedientes", methods=["GET"])
    @require_roles(*READ_ROLES)
    def family_records():
        user = _user()
        rows = _filter_units(repo.list_family_records(user["fundacion_id"], dict(request.args)), user)
        return jsonify({"expedientes": rows}), 200

    @bp.route("/expedientes/<int:record_id>", methods=["GET", "PATCH"])
    @require_roles(*READ_ROLES)
    def family_record(record_id: int):
        user = _user()
        try:
            current = _require_family(record_id, user)
            if request.method == "PATCH":
                if not _can_edit(user): return jsonify({"error": "Tu rol solo puede consultar el expediente."}), 403
                return jsonify({"message": "Expediente familiar actualizado.", "expediente": repo.update_family_record(user["fundacion_id"], record_id, _payload(), user)}), 200
            return jsonify({"expediente": current}), 200
        except LookupError as exc:
            return jsonify({"error": str(exc)}), 404
        except PermissionError as exc:
            return jsonify({"error": str(exc)}), 403
        except Exception as exc:
            return jsonify({"error": str(exc)}), 400

    @bp.route("/actividades", methods=["GET", "POST"])
    @require_roles(*READ_ROLES)
    def activities():
        user = _user()
        if request.method == "POST":
            if not _can_edit(user): return jsonify({"error": "Tu rol no puede crear actividades."}), 403
            try:
                data = _scoped_payload(_payload(), user)
                target_key = unit_key(data.get("unidad_nombre") or data.get("unidad"))
                for record_id in data.get("expedientes_familiares") or []:
                    family = _require_family(int(record_id), user)
                    if unit_key(family.get("unidad_nombre")) != target_key:
                        raise PermissionError("Todos los expedientes vinculados deben pertenecer a la misma UCA de la actividad.")
                return jsonify({"message": "Actividad creada y borradores de acta/listado preparados.", "actividad": repo.create_activity(user["fundacion_id"], data, user)}), 201
            except PermissionError as exc:
                return jsonify({"error": str(exc)}), 403
            except Exception as exc:
                return jsonify({"error": str(exc)}), 400
        filters = dict(request.args)
        if user["rol"] == "PSICOSOCIAL": filters.setdefault("profesional_id", user.get("id"))
        return jsonify({"actividades": _filter_units(repo.list_activities(user["fundacion_id"], filters), user)}), 200

    @bp.route("/actividades/<int:activity_id>", methods=["GET", "PATCH"])
    @require_roles(*READ_ROLES)
    def activity_detail(activity_id: int):
        user = _user()
        try:
            current = _require_activity(activity_id, user)
            if request.method == "PATCH":
                if not _can_edit(user): return jsonify({"error": "Tu rol solo puede consultar actividades."}), 403
                return jsonify({"message": "Actividad actualizada.", "actividad": repo.update_activity(user["fundacion_id"], activity_id, _payload(), user)}), 200
            return jsonify({"actividad": current}), 200
        except LookupError as exc:
            return jsonify({"error": str(exc)}), 404
        except PermissionError as exc:
            return jsonify({"error": str(exc)}), 403
        except Exception as exc:
            return jsonify({"error": str(exc)}), 400

    @bp.route("/actividades/<int:activity_id>/asistencias", methods=["POST", "PATCH"])
    @require_roles(*EDIT_ROLES)
    def attendance(activity_id: int):
        user = _user()
        try:
            _require_activity(activity_id, user)
            return jsonify({"message": "Asistencia actualizada.", "actividad": repo.update_attendance(user["fundacion_id"], activity_id, _payload(), user)}), 200
        except LookupError as exc:
            return jsonify({"error": str(exc)}), 404
        except PermissionError as exc:
            return jsonify({"error": str(exc)}), 403
        except Exception as exc:
            return jsonify({"error": str(exc)}), 400

    @bp.route("/actividades/<int:activity_id>/documentos/preparar", methods=["POST"])
    @require_roles(*EDIT_ROLES)
    def prepare_documents(activity_id: int):
        user = _user(); data = _payload(); types = tuple(data.get("tipos") or ["ACTA", "LISTADO_ASISTENCIA", "INFORME"])
        try:
            _require_activity(activity_id, user)
            return jsonify({"message": "Documentos preparados como borradores para revisión.", "resultado": repo.prepare_activity_documents(user["fundacion_id"], activity_id, user, types=types)}), 201
        except LookupError as exc:
            return jsonify({"error": str(exc)}), 404
        except PermissionError as exc:
            return jsonify({"error": str(exc)}), 403
        except Exception as exc:
            return jsonify({"error": str(exc)}), 400

    @bp.route("/compromisos", methods=["GET", "POST"])
    @require_roles(*READ_ROLES)
    def commitments():
        user = _user()
        if request.method == "POST":
            if not _can_edit(user): return jsonify({"error": "Tu rol no puede crear compromisos."}), 403
            try:
                data = _resolve_linked_unit(_payload(), user)
                return jsonify({"message": "Compromiso registrado y enviado al Motor de Gestión.", "compromiso": repo.create_commitment(user["fundacion_id"], data, user)}), 201
            except PermissionError as exc: return jsonify({"error": str(exc)}), 403
            except Exception as exc: return jsonify({"error": str(exc)}), 400
        return jsonify({"compromisos": _filter_units(repo.list_commitments(user["fundacion_id"], dict(request.args)), user)}), 200

    @bp.route("/compromisos/<int:commitment_id>", methods=["GET"])
    @require_roles(*READ_ROLES)
    def commitment_detail(commitment_id: int):
        user = _user()
        try: return jsonify({"compromiso": _require_commitment(commitment_id, user)}), 200
        except LookupError as exc: return jsonify({"error": str(exc)}), 404
        except PermissionError as exc: return jsonify({"error": str(exc)}), 403

    @bp.route("/compromisos/<int:commitment_id>/seguimientos", methods=["POST"])
    @require_roles(*EDIT_ROLES)
    def commitment_followup(commitment_id: int):
        user = _user()
        try:
            _require_commitment(commitment_id, user)
            return jsonify({"message": "Seguimiento registrado.", "compromiso": repo.add_followup(user["fundacion_id"], commitment_id, _payload(), user)}), 201
        except LookupError as exc: return jsonify({"error": str(exc)}), 404
        except PermissionError as exc: return jsonify({"error": str(exc)}), 403
        except Exception as exc: return jsonify({"error": str(exc)}), 400

    @bp.route("/compromisos/<int:commitment_id>/cerrar", methods=["POST"])
    @require_roles(*COORDINATION_ROLES)
    def close_commitment(commitment_id: int):
        user = _user()
        try:
            _require_commitment(commitment_id, user)
            return jsonify({"message": "Compromiso cerrado con validación humana.", "compromiso": repo.close_commitment(user["fundacion_id"], commitment_id, _payload(), user)}), 200
        except LookupError as exc: return jsonify({"error": str(exc)}), 404
        except PermissionError as exc: return jsonify({"error": str(exc)}), 403
        except Exception as exc: return jsonify({"error": str(exc)}), 400

    @bp.route("/redes", methods=["GET", "POST"])
    @require_roles(*READ_ROLES)
    def networks():
        user = _user()
        if request.method == "POST":
            if not _can_edit(user): return jsonify({"error": "Tu rol no puede registrar redes."}), 403
            try: return jsonify({"message": "Red de apoyo registrada.", "red": repo.create_network(user["fundacion_id"], _payload(), user)}), 201
            except Exception as exc: return jsonify({"error": str(exc)}), 400
        return jsonify({"redes": repo.list_networks(user["fundacion_id"])}), 200

    @bp.route("/redes/<int:network_id>/verificar", methods=["POST"])
    @require_roles(*COORDINATION_ROLES)
    def verify_network(network_id: int):
        user = _user()
        try: return jsonify({"message": "Red verificada.", "red": repo.verify_network(user["fundacion_id"], network_id, user)}), 200
        except LookupError as exc: return jsonify({"error": str(exc)}), 404

    @bp.route("/alertas", methods=["GET", "POST"])
    @require_roles(*READ_ROLES)
    def alerts():
        user = _user()
        if request.method == "POST":
            if not _can_edit(user): return jsonify({"error": "Tu rol no puede registrar alertas."}), 403
            try:
                data = _resolve_linked_unit(_payload(), user)
                return jsonify({"message": "Alerta registrada; no se cerrará automáticamente.", "alerta": repo.create_alert(user["fundacion_id"], data, user)}), 201
            except PermissionError as exc: return jsonify({"error": str(exc)}), 403
            except Exception as exc: return jsonify({"error": str(exc)}), 400
        return jsonify({"alertas": _filter_units(repo.list_alerts(user["fundacion_id"], dict(request.args)), user)}), 200

    @bp.route("/alertas/<int:alert_id>", methods=["GET", "PATCH"])
    @require_roles(*READ_ROLES)
    def alert_detail(alert_id: int):
        user = _user()
        try:
            current = _require_alert(alert_id, user)
            if request.method == "PATCH":
                if not _can_edit(user): return jsonify({"error": "Tu rol solo puede consultar alertas."}), 403
                return jsonify({"message": "Alerta actualizada.", "alerta": repo.update_alert(user["fundacion_id"], alert_id, _payload(), user)}), 200
            return jsonify({"alerta": current}), 200
        except PermissionError as exc: return jsonify({"error": str(exc)}), 403
        except LookupError as exc: return jsonify({"error": str(exc)}), 404
        except Exception as exc: return jsonify({"error": str(exc)}), 400

    @bp.route("/alertas/<int:alert_id>/cerrar", methods=["POST"])
    @require_roles(*COORDINATION_ROLES)
    def close_alert(alert_id: int):
        user = _user()
        try:
            _require_alert(alert_id, user)
            return jsonify({"message": "Alerta cerrada con resultado y evidencia.", "alerta": repo.close_alert(user["fundacion_id"], alert_id, _payload(), user)}), 200
        except LookupError as exc: return jsonify({"error": str(exc)}), 404
        except PermissionError as exc: return jsonify({"error": str(exc)}), 403
        except Exception as exc: return jsonify({"error": str(exc)}), 400

    @bp.route("/evidencias", methods=["POST"])
    @require_roles(*EDIT_ROLES)
    def evidence_upload():
        user = _user(); file_obj = request.files.get("archivo")
        try:
            data = _resolve_linked_unit(request.form.to_dict(), user)
            return jsonify({"message": "Evidencia almacenada con huella SHA-256.", "evidencia": repo.add_evidence(user["fundacion_id"], file_obj, data, user)}), 201
        except PermissionError as exc: return jsonify({"error": str(exc)}), 403
        except Exception as exc: return jsonify({"error": str(exc)}), 400

    @bp.route("/evidencias/<int:evidence_id>/descargar", methods=["GET"])
    @require_roles(*READ_ROLES)
    def evidence_download(evidence_id: int):
        user = _user()
        try:
            meta = repo.evidence(user["fundacion_id"], evidence_id)
            if not _can_access_unit(meta.get("unidad_nombre"), user):
                return jsonify({"error": "No tienes permiso sobre esta UCA."}), 403
        except LookupError as exc:
            return jsonify({"error": str(exc)}), 404
        found = repo.evidence_path(user["fundacion_id"], evidence_id)
        if not found: return jsonify({"error": "Evidencia no encontrada o integridad inválida."}), 404
        path, name, mime = found; repo.audit(user["fundacion_id"], user, "DESCARGAR_EVIDENCIA", "fcr_evidencias", evidence_id, {"archivo": name})
        return send_file(path, as_attachment=True, download_name=name, mimetype=mime)

    @bp.route("/documentos", methods=["GET"])
    @require_roles(*READ_ROLES)
    def documents():
        user = _user()
        activity_id = request.args.get("actividad_id", type=int)
        if activity_id:
            try: _require_activity(activity_id, user)
            except LookupError as exc: return jsonify({"error": str(exc)}), 404
            except PermissionError as exc: return jsonify({"error": str(exc)}), 403
        rows = _filter_units(repo.list_documents(user["fundacion_id"], activity_id), user)
        return jsonify({"documentos": rows}), 200

    @bp.route("/documentos/<int:document_id>/descargar", methods=["GET"])
    @require_roles(*READ_ROLES)
    def document_download(document_id: int):
        user = _user()
        try:
            meta = repo.document(user["fundacion_id"], document_id)
            if not _can_access_unit(meta.get("unidad_nombre"), user):
                return jsonify({"error": "No tienes permiso sobre esta UCA."}), 403
        except LookupError as exc:
            return jsonify({"error": str(exc)}), 404
        found = repo.document_path(user["fundacion_id"], document_id)
        if not found: return jsonify({"error": "Documento no encontrado o integridad inválida."}), 404
        path, name, mime = found; repo.audit(user["fundacion_id"], user, "DESCARGAR_DOCUMENTO", "fcr_documentos_generados", document_id, {"archivo": name})
        return send_file(path, as_attachment=True, download_name=name, mimetype=mime)

    @bp.route("/documentos/<int:document_id>/<string:action>", methods=["POST"])
    @require_roles(*COORDINATION_ROLES)
    def document_review(document_id: int, action: str):
        user = _user()
        try:
            meta = repo.document(user["fundacion_id"], document_id)
            if not _can_access_unit(meta.get("unidad_nombre"), user):
                return jsonify({"error": "No tienes permiso sobre esta UCA."}), 403
            return jsonify({"message": "Documento actualizado.", "documento": repo.review_document(user["fundacion_id"], document_id, action, user)}), 200
        except LookupError as exc: return jsonify({"error": str(exc)}), 404
        except Exception as exc: return jsonify({"error": str(exc)}), 400

    @bp.route("/reportes/preparar", methods=["POST"])
    @require_roles(*READ_ROLES)
    def prepare_report():
        user = _user()
        try:
            data = _payload()
            allowed = _allowed_units(user)
            if allowed is not None:
                if not data.get("unidad") and len(allowed) == 1:
                    data["unidad"] = allowed[0]
                if not data.get("unidad"):
                    raise PermissionError("Selecciona una UCA asignada para preparar el paquete.")
                if not _can_access_unit(data.get("unidad"), user):
                    raise PermissionError("No tienes permiso sobre esta UCA.")
            return jsonify({"message": "Paquete preparado para revisión.", "producto": repo.prepare_summary_package(user["fundacion_id"], user, data)}), 201
        except PermissionError as exc: return jsonify({"error": str(exc)}), 403
        except Exception as exc: return jsonify({"error": str(exc)}), 400

    app.register_blueprint(bp)
