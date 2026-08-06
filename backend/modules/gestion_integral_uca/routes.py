from __future__ import annotations

import json
import os
import re
import uuid
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from flask import Blueprint, g, jsonify, request, send_file
from werkzeug.utils import secure_filename

from modules.seguridad.services import require_roles
from modules.seguridad.tenant_context import tenant_storage_root

from .repository import GestionIntegralRepository
from .library_updates import LibraryUpdateError, fetch_authorized_catalog
from .services import MODULE_LINKS, file_sha256, parse_json, safe_state, unit_key

ALLOWED_EVIDENCE = {".pdf", ".doc", ".docx", ".xlsx", ".xls", ".xlsm", ".csv", ".txt", ".png", ".jpg", ".jpeg", ".webp", ".zip"}
ALLOWED_LIBRARY = ALLOWED_EVIDENCE | {".ppt", ".pptx", ".odt", ".ods"}
MAX_EVIDENCE_MB = 40
MAX_LIBRARY_MB = 80
MANAGEMENT_ROLES = {"SUPERADMIN", "GERENTE"}
COORDINATION_ROLES = MANAGEMENT_ROLES | {"COORDINADOR", "AUXILIAR_ADMINISTRATIVO"}
ALL_OPERATIONAL_ROLES = COORDINATION_ROLES | {"DOCENTE", "NUTRICIONISTA", "PSICOSOCIAL"}
ROUTE_REVIEW_STATES = {"PENDIENTE_REVISION", "DEVUELTA", "APROBADA", "CERRADA", "NO_APLICA"}
PLAN_REVIEW_STATES = {"APROBADO", "CERRADO"}


def _user() -> dict[str, Any]:
    user = getattr(g, "current_user", None) or {}
    return {
        **user,
        "id": user.get("id"),
        "username": user.get("username") or user.get("email") or "sistema",
        "rol": str(user.get("rol") or "").upper(),
        "fundacion_id": int(user.get("fundacion_id") or 1),
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
    # Compatibilidad con usuarios históricos que todavía no tienen la asignación
    # normalizada. El aislamiento por fundación permanece activo.
    return None


def _can_access_unit(unit_name: str, user: dict[str, Any]) -> bool:
    allowed = _allowed_units(user)
    if allowed is None:
        return True
    allowed_keys = {unit_key(value) for value in allowed}
    return unit_key(unit_name) in allowed_keys


def _validate_upload(file, allowed: set[str], max_mb: int):
    if not file or not file.filename:
        raise ValueError("No se seleccionó ningún archivo.")
    extension = os.path.splitext(file.filename.lower())[1]
    if extension not in allowed:
        raise ValueError("Extensión no permitida para este módulo.")
    try:
        position = file.stream.tell()
        file.stream.seek(0, os.SEEK_END)
        size = file.stream.tell()
        file.stream.seek(position)
    except Exception:
        size = 0
    if size > max_mb * 1024 * 1024:
        raise ValueError(f"El archivo supera el máximo permitido de {max_mb} MB.")
    return extension


def _safe_tenant_file(path_value: str, data_dir: str, fundacion_id: int) -> Path | None:
    try:
        path = Path(path_value).resolve(strict=True)
        root = tenant_storage_root(Path(data_dir), fundacion_id).resolve()
        path.relative_to(root)
    except (OSError, ValueError):
        return None
    return path if path.is_file() else None


def _safe_web_url(value: str | None) -> str | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    parsed = urlparse(raw)
    if parsed.scheme not in {"https", "http"} or not parsed.netloc:
        raise ValueError("La URL de origen debe usar http o https.")
    return raw[:1000]


def register_routes(app, database_path: str, data_dir: str, output_folder: str) -> None:
    repo = GestionIntegralRepository(database_path, data_dir, output_folder)
    repo.init_schema()
    bp = Blueprint("gestion_integral_uca", __name__, url_prefix="/api/gestion-integral-uca")

    def _require_expediente(expediente_id: int, user: dict[str, Any]) -> dict[str, Any]:
        expediente = repo.get_expediente(expediente_id, user["fundacion_id"])
        if not expediente:
            raise LookupError("Expediente operativo no encontrado.")
        if not _can_access_unit(expediente["unidad_nombre"], user):
            raise PermissionError("No tienes permiso sobre esta UCA.")
        return expediente

    def _route_item(expediente: dict[str, Any], instance_id: int) -> dict[str, Any]:
        item = next((row for row in expediente.get("ruta", []) if int(row.get("id") or 0) == int(instance_id)), None)
        if not item:
            raise LookupError("Actividad de ruta no encontrada.")
        return item

    def _role_can_edit_route(item: dict[str, Any], user: dict[str, Any]) -> bool:
        if user["rol"] in COORDINATION_ROLES:
            return True
        return user["rol"] in set(item.get("roles") or [])

    @bp.route("/salud", methods=["GET"])
    def health():
        return jsonify({"status": "ok", "module": "gestion_integral_uca", "schema_version": 3, "capability": "expediente_uca_biblioteca_controlada"}), 200

    @bp.route("/unidades", methods=["GET"])
    def units():
        user = _user()
        return jsonify({"unidades": repo.list_units(user["fundacion_id"], _allowed_units(user))}), 200

    @bp.route("/dashboard", methods=["GET"])
    def dashboard():
        user = _user()
        vigencia = request.args.get("vigencia") or str(date.today().year)
        return jsonify(repo.dashboard(user["fundacion_id"], vigencia, _allowed_units(user))), 200

    @bp.route("/sincronizar", methods=["POST"])
    @require_roles(*COORDINATION_ROLES)
    def sync_units():
        user = _user()
        data = _payload()
        vigencia = str(data.get("vigencia") or date.today().year)
        contrato = str(data.get("contrato") or "").strip()
        result = repo.sync_all_units(user["fundacion_id"], vigencia, contrato, user, _allowed_units(user))
        repo.audit(user["fundacion_id"], user, "SINCRONIZAR_EXPEDIENTES_UCA", "giu_expedientes_uca", None, {"total": len(result), "vigencia": vigencia, "contrato": contrato})
        return jsonify({"message": f"Se sincronizaron {len(result)} expedientes operativos.", "expedientes": result}), 200

    @bp.route("/expedientes", methods=["GET", "POST"])
    def expedientes():
        user = _user()
        if request.method == "GET":
            return jsonify({"expedientes": repo.list_expedientes(user["fundacion_id"], request.args.get("vigencia"), _allowed_units(user))}), 200
        if user["rol"] not in COORDINATION_ROLES:
            return jsonify({"error": "No tienes permiso para crear expedientes operativos."}), 403
        data = _payload()
        unit_name = str(data.get("unidad_nombre") or "").strip()
        if not unit_name:
            return jsonify({"error": "unidad_nombre es obligatorio."}), 400
        if not _can_access_unit(unit_name, user):
            return jsonify({"error": "No tienes permiso sobre esta UCA."}), 403
        known = {unit_key(item["nombre"]): item for item in repo.list_units(user["fundacion_id"], _allowed_units(user))}
        unit = known.get(unit_key(unit_name)) or {
            "id": data.get("unidad_id"), "nombre": unit_name, "codigo": data.get("codigo_unidad"),
            "coordinador": data.get("coordinador_nombre"), "modalidad": data.get("servicio_modalidad"), "unidad_clave": unit_key(unit_name),
        }
        result = repo.ensure_expediente(
            user["fundacion_id"], unit, str(data.get("vigencia") or date.today().year), str(data.get("contrato") or ""), user,
            servicio_modalidad=data.get("servicio_modalidad"),
        )
        repo.audit(user["fundacion_id"], user, "CREAR_EXPEDIENTE_UCA", "giu_expedientes_uca", result.get("id"), {"unidad": unit_name})
        return jsonify({"message": "Expediente operativo preparado.", "expediente": result}), 201

    @bp.route("/expedientes/<int:expediente_id>", methods=["GET"])
    def expediente_detail(expediente_id: int):
        user = _user()
        try:
            expediente = _require_expediente(expediente_id, user)
        except LookupError as exc:
            return jsonify({"error": str(exc)}), 404
        except PermissionError as exc:
            return jsonify({"error": str(exc)}), 403
        return jsonify({"expediente": expediente}), 200

    @bp.route("/expedientes/<int:expediente_id>/vista-unica", methods=["GET"])
    def expediente_integrated_view(expediente_id: int):
        user = _user()
        try:
            _require_expediente(expediente_id, user)
            view = repo.integrated_view(user["fundacion_id"], expediente_id)
            return jsonify({"vista": view}), 200
        except LookupError as exc:
            return jsonify({"error": str(exc)}), 404
        except PermissionError as exc:
            return jsonify({"error": str(exc)}), 403

    @bp.route("/expedientes/<int:expediente_id>/preparacion-supervision", methods=["GET"])
    def expediente_supervision_preview(expediente_id: int):
        user = _user()
        try:
            _require_expediente(expediente_id, user)
            return jsonify({"preparacion": repo.supervision_preview(user["fundacion_id"], expediente_id)}), 200
        except LookupError as exc:
            return jsonify({"error": str(exc)}), 404
        except PermissionError as exc:
            return jsonify({"error": str(exc)}), 403

    @bp.route("/expedientes/<int:expediente_id>/documentos", methods=["GET", "POST"])
    def expediente_documents(expediente_id: int):
        user = _user()
        try:
            _require_expediente(expediente_id, user)
            if request.method == "POST":
                view = repo.integrated_view(user["fundacion_id"], expediente_id)
                repo.audit(
                    user["fundacion_id"], user, "SINCRONIZAR_VINCULOS_DOCUMENTALES",
                    "giu_expedientes_uca", expediente_id,
                    {"total": len(view.get("documentos") or []), "expediente_id": expediente_id},
                )
            return jsonify({"documentos": repo.list_document_links(user["fundacion_id"], expediente_id)}), 200
        except LookupError as exc:
            return jsonify({"error": str(exc)}), 404
        except PermissionError as exc:
            return jsonify({"error": str(exc)}), 403

    @bp.route("/expedientes/<int:expediente_id>/documentos/<int:link_id>/descargar", methods=["GET"])
    def download_linked_document(expediente_id: int, link_id: int):
        user = _user()
        try:
            _require_expediente(expediente_id, user)
        except LookupError as exc:
            return jsonify({"error": str(exc)}), 404
        except PermissionError as exc:
            return jsonify({"error": str(exc)}), 403
        found = repo.linked_document_path(user["fundacion_id"], expediente_id, link_id)
        if not found:
            return jsonify({"error": "El documento vinculado no está disponible dentro del almacenamiento autorizado."}), 404
        raw_path, name = found
        repo.audit(user["fundacion_id"], user, "DESCARGAR_DOCUMENTO_VINCULADO", "giu_vinculos_documentales", link_id, {"expediente_id": expediente_id, "archivo": name})
        return send_file(raw_path, as_attachment=True, download_name=name)

    @bp.route("/expedientes/<int:expediente_id>/ruta/<int:instance_id>", methods=["PATCH", "PUT"])
    def update_route(expediente_id: int, instance_id: int):
        user = _user()
        try:
            expediente = _require_expediente(expediente_id, user)
            item = _route_item(expediente, instance_id)
            if not _role_can_edit_route(item, user):
                return jsonify({"error": "Tu rol no está autorizado para actualizar esta actividad."}), 403
            data = _payload()
            requested_state = safe_state(data.get("estado")) if data.get("estado") else None
            if requested_state in ROUTE_REVIEW_STATES and user["rol"] not in COORDINATION_ROLES:
                return jsonify({"error": "La revisión, devolución, aprobación, cierre o declaración de no aplica corresponde a coordinación."}), 403
            updated = repo.update_route_instance(user["fundacion_id"], expediente_id, instance_id, data, user)
            return jsonify({"message": "Actividad de ruta actualizada.", "actividad": updated}), 200
        except LookupError as exc:
            return jsonify({"error": str(exc)}), 404
        except PermissionError as exc:
            return jsonify({"error": str(exc)}), 403
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 409

    @bp.route("/expedientes/<int:expediente_id>/ruta/<int:instance_id>/evidencias", methods=["GET", "POST"])
    def route_evidence(expediente_id: int, instance_id: int):
        user = _user()
        try:
            expediente = _require_expediente(expediente_id, user)
            item = _route_item(expediente, instance_id)
        except LookupError as exc:
            return jsonify({"error": str(exc)}), 404
        except PermissionError as exc:
            return jsonify({"error": str(exc)}), 403
        if request.method == "GET":
            return jsonify({"evidencias": repo.list_evidence(user["fundacion_id"], instance_id)}), 200
        if not _role_can_edit_route(item, user):
            return jsonify({"error": "Tu rol no está autorizado para cargar evidencias en esta actividad."}), 403
        file = request.files.get("file")
        try:
            _validate_upload(file, ALLOWED_EVIDENCE, MAX_EVIDENCE_MB)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        tenant_root = tenant_storage_root(Path(data_dir), user["fundacion_id"])
        folder = tenant_root / "gestion_integral_uca" / f"expediente_{expediente_id}" / "evidencias" / f"actividad_{instance_id}"
        folder.mkdir(parents=True, exist_ok=True)
        safe_name = secure_filename(file.filename) or "evidencia"
        stored_name = f"{uuid.uuid4().hex[:12]}_{safe_name}"
        path = (folder / stored_name).resolve()
        file.save(path)
        if not path.is_file() or path.stat().st_size <= 0:
            return jsonify({"error": "El archivo no pudo guardarse correctamente."}), 500
        evidence = repo.add_evidence(
            user["fundacion_id"], expediente_id, instance_id,
            {
                "nombre_original": file.filename,
                "nombre_guardado": stored_name,
                "ruta_archivo": str(path),
                "mime_type": file.mimetype or "application/octet-stream",
                "tamano_bytes": path.stat().st_size,
                "sha256": file_sha256(str(path)),
                "observaciones": request.form.get("observaciones"),
            },
            user,
        )
        return jsonify({"message": "Evidencia cargada y versionada.", "evidencia": evidence}), 201

    @bp.route("/evidencias/<int:evidence_id>/descargar", methods=["GET"])
    def download_evidence(evidence_id: int):
        user = _user()
        found = repo.evidence_path(user["fundacion_id"], evidence_id)
        if not found:
            return jsonify({"error": "Evidencia no encontrada."}), 404
        raw_path, name = found
        path = _safe_tenant_file(raw_path, data_dir, user["fundacion_id"])
        if not path:
            return jsonify({"error": "La evidencia no está disponible dentro del almacenamiento autorizado."}), 404
        repo.audit(user["fundacion_id"], user, "DESCARGAR_EVIDENCIA_RUTA", "giu_ruta_evidencias", evidence_id, {"archivo": name})
        return send_file(path, as_attachment=True, download_name=name)

    @bp.route("/expedientes/<int:expediente_id>/planes/<int:plan_id>", methods=["PATCH", "PUT"])
    def update_plan(expediente_id: int, plan_id: int):
        user = _user()
        try:
            _require_expediente(expediente_id, user)
            if user["rol"] not in ALL_OPERATIONAL_ROLES:
                return jsonify({"error": "No tienes permiso para actualizar planes."}), 403
            data = _payload()
            requested_state = str(data.get("estado") or "").strip().upper().replace(" ", "_")
            if requested_state in PLAN_REVIEW_STATES and user["rol"] not in COORDINATION_ROLES:
                return jsonify({"error": "La aprobación o cierre de planes corresponde a coordinación."}), 403
            plan = repo.update_plan(user["fundacion_id"], expediente_id, plan_id, data, user)
            return jsonify({"message": "Plan actualizado.", "plan": plan}), 200
        except LookupError as exc:
            return jsonify({"error": str(exc)}), 404
        except PermissionError as exc:
            return jsonify({"error": str(exc)}), 403
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

    @bp.route("/expedientes/<int:expediente_id>/paquete-supervision", methods=["GET"])
    @require_roles(*COORDINATION_ROLES)
    def supervision_package(expediente_id: int):
        user = _user()
        try:
            _require_expediente(expediente_id, user)
            path = repo.build_supervision_package(user["fundacion_id"], expediente_id, user)
            return send_file(path, as_attachment=True, download_name=os.path.basename(path))
        except LookupError as exc:
            return jsonify({"error": str(exc)}), 404
        except PermissionError as exc:
            return jsonify({"error": str(exc)}), 403

    @bp.route("/biblioteca/documentos", methods=["GET", "POST"])
    def library_documents():
        user = _user()
        if request.method == "GET":
            return jsonify({"documentos": repo.list_library_documents(user["fundacion_id"], include_versions=True), "modulos": MODULE_LINKS}), 200
        if user["rol"] not in (MANAGEMENT_ROLES | {"AUXILIAR_ADMINISTRATIVO"}):
            return jsonify({"error": "No tienes permiso para administrar la biblioteca."}), 403
        data = _payload()
        try:
            if data.get("fuente_url"):
                data["fuente_url"] = _safe_web_url(data.get("fuente_url"))
            document = repo.create_library_document(user["fundacion_id"], data, user)
            return jsonify({"message": "Documento guardado en la biblioteca.", "documento": document}), 201
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

    @bp.route("/biblioteca/documentos/<int:document_id>/relaciones", methods=["GET", "PUT"])
    def library_relations(document_id: int):
        user = _user()
        if request.method == "GET":
            return jsonify({"relaciones": repo.list_library_relations(user["fundacion_id"], document_id)}), 200
        if user["rol"] not in (MANAGEMENT_ROLES | {"AUXILIAR_ADMINISTRATIVO"}):
            return jsonify({"error": "No tienes permiso para modificar relaciones."}), 403
        try:
            relations = repo.set_library_relations(user["fundacion_id"], document_id, _payload().get("relaciones") or [], user)
            return jsonify({"message": "Relaciones actualizadas.", "relaciones": relations}), 200
        except LookupError as exc:
            return jsonify({"error": str(exc)}), 404

    @bp.route("/biblioteca/documentos/<int:document_id>/versiones", methods=["POST"])
    def library_version_upload(document_id: int):
        user = _user()
        if user["rol"] not in (MANAGEMENT_ROLES | {"AUXILIAR_ADMINISTRATIVO"}):
            return jsonify({"error": "No tienes permiso para cargar versiones."}), 403
        payload = request.form.to_dict() if request.form else _payload()
        if payload.get("fuente_url"):
            try:
                payload["fuente_url"] = _safe_web_url(payload.get("fuente_url"))
            except ValueError as exc:
                return jsonify({"error": str(exc)}), 400
        file = request.files.get("file")
        file_meta = None
        if file and file.filename:
            try:
                _validate_upload(file, ALLOWED_LIBRARY, MAX_LIBRARY_MB)
            except ValueError as exc:
                return jsonify({"error": str(exc)}), 400
            tenant_root = tenant_storage_root(Path(data_dir), user["fundacion_id"])
            folder = tenant_root / "institutional" / "biblioteca_icbf" / f"documento_{document_id}"
            folder.mkdir(parents=True, exist_ok=True)
            safe_name = secure_filename(file.filename) or "documento"
            stored_name = f"{uuid.uuid4().hex[:12]}_{safe_name}"
            path = (folder / stored_name).resolve()
            file.save(path)
            file_meta = {
                "nombre_original": file.filename,
                "nombre_guardado": stored_name,
                "ruta_archivo": str(path),
                "mime_type": file.mimetype or "application/octet-stream",
                "tamano_bytes": path.stat().st_size,
                "sha256": file_sha256(str(path)),
            }
        try:
            version = repo.add_library_version(user["fundacion_id"], document_id, payload, file_meta, user)
            return jsonify({"message": "Versión registrada con trazabilidad.", "version": version}), 201
        except LookupError as exc:
            return jsonify({"error": str(exc)}), 404
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

    @bp.route("/biblioteca/versiones/<int:version_id>/activar", methods=["POST"])
    @require_roles("SUPERADMIN", "GERENTE")
    def activate_library_version(version_id: int):
        user = _user()
        try:
            version = repo.activate_library_version(user["fundacion_id"], version_id, user)
            return jsonify({"message": "Versión marcada como vigente.", "version": version}), 200
        except LookupError as exc:
            return jsonify({"error": str(exc)}), 404

    @bp.route("/biblioteca/versiones/<int:version_id>/descargar", methods=["GET"])
    def download_library_version(version_id: int):
        user = _user()
        found = repo.library_version_path(user["fundacion_id"], version_id)
        if not found:
            return jsonify({"error": "Archivo de la versión no encontrado."}), 404
        raw_path, name = found
        path = _safe_tenant_file(raw_path, data_dir, user["fundacion_id"])
        if not path:
            return jsonify({"error": "El archivo no está disponible dentro del almacenamiento autorizado."}), 404
        repo.audit(user["fundacion_id"], user, "DESCARGAR_VERSION_BIBLIOTECA", "biblioteca_icbf_versiones", version_id, {"archivo": name})
        return send_file(path, as_attachment=True, download_name=name)


    @bp.route("/biblioteca/documentos/<int:document_id>/sugerir-relaciones", methods=["GET", "POST"])
    def suggest_library_relations(document_id: int):
        user = _user()
        try:
            if request.method == "POST":
                if user["rol"] not in (MANAGEMENT_ROLES | {"AUXILIAR_ADMINISTRATIVO"}):
                    return jsonify({"error": "No tienes permiso para aplicar relaciones."}), 403
                relations = repo.apply_suggested_library_relations(user["fundacion_id"], document_id, user)
                return jsonify({"message": "Relaciones sugeridas aplicadas para revisión.", "relaciones": relations}), 200
            return jsonify({"sugerencias": repo.suggest_library_relations(user["fundacion_id"], document_id)}), 200
        except LookupError as exc:
            return jsonify({"error": str(exc)}), 404

    @bp.route("/biblioteca/fuentes", methods=["GET", "POST"])
    def library_sources():
        user = _user()
        if request.method == "GET":
            return jsonify({"fuentes": repo.list_library_sources(user["fundacion_id"])}), 200
        if user["rol"] not in (MANAGEMENT_ROLES | {"AUXILIAR_ADMINISTRATIVO"}):
            return jsonify({"error": "No tienes permiso para administrar fuentes."}), 403
        try:
            source = repo.save_library_source(user["fundacion_id"], _payload(), user)
            return jsonify({"message": "Fuente guardada. La verificación remota solo se ejecutará si está autorizada, habilitada y configurada.", "fuente": source}), 201
        except Exception as exc:
            return jsonify({"error": str(exc)}), 400

    @bp.route("/biblioteca/fuentes/<int:source_id>/verificar", methods=["POST"])
    @require_roles("SUPERADMIN", "GERENTE", "AUXILIAR_ADMINISTRATIVO")
    def verify_library_source(source_id: int):
        user = _user()
        source = repo.get_library_source(user["fundacion_id"], source_id)
        if not source:
            return jsonify({"error": "Fuente no encontrada."}), 404
        try:
            result = fetch_authorized_catalog(source)
            if result.get("not_modified"):
                repo.update_source_check_status(user["fundacion_id"], source_id, status="SIN_CAMBIOS", detail="La fuente respondió 304; no hay cambios.", etag=result.get("etag"), last_modified=result.get("last_modified"))
                return jsonify({"message": "La fuente no reportó cambios.", "resultado": {"detectadas": 0, "sin_cambios": True}}), 200
            imported = repo.import_library_candidates(user["fundacion_id"], source_id, result.get("items") or [], user)
            repo.update_source_check_status(user["fundacion_id"], source_id, status="OK", detail=f"Catálogo consultado; {imported['detectadas']} candidatos detectados.", etag=result.get("etag"), last_modified=result.get("last_modified"))
            return jsonify({"message": "Fuente autorizada verificada.", "resultado": imported}), 200
        except LibraryUpdateError as exc:
            repo.update_source_check_status(user["fundacion_id"], source_id, status="ERROR", detail=str(exc))
            return jsonify({"error": str(exc), "modo_seguro": "No se aplicó ninguna actualización."}), 400

    @bp.route("/biblioteca/candidatos/importar", methods=["POST"])
    @require_roles("SUPERADMIN", "GERENTE", "AUXILIAR_ADMINISTRATIVO")
    def import_library_candidates():
        user = _user()
        data = _payload()
        try:
            result = repo.import_library_candidates(
                user["fundacion_id"], int(data.get("fuente_id") or 0) or None,
                data.get("documentos") or data.get("items") or [], user,
            )
            return jsonify({"message": "Catálogo importado para revisión manual.", "resultado": result}), 201
        except Exception as exc:
            return jsonify({"error": str(exc)}), 400

    @bp.route("/biblioteca/candidatos", methods=["GET"])
    def library_candidates():
        user = _user()
        return jsonify({"candidatos": repo.list_library_candidates(user["fundacion_id"], request.args.get("estado"))}), 200

    @bp.route("/biblioteca/candidatos/<int:candidate_id>/<string:action>", methods=["POST"])
    @require_roles("SUPERADMIN", "GERENTE")
    def decide_library_candidate(candidate_id: int, action: str):
        user = _user()
        try:
            result = repo.decide_library_candidate(user["fundacion_id"], candidate_id, action, user, _payload().get("observaciones"))
            return jsonify({"message": "Candidato actualizado. Ninguna versión se vuelve vigente sin activación explícita y archivo verificado.", "candidato": result}), 200
        except LookupError as exc:
            return jsonify({"error": str(exc)}), 404
        except Exception as exc:
            return jsonify({"error": str(exc)}), 400

    @bp.route("/biblioteca/notificaciones", methods=["GET"])
    def library_notifications():
        user = _user()
        unread = str(request.args.get("no_leidas") or "").lower() in {"1", "true", "si", "sí"}
        return jsonify({"notificaciones": repo.list_library_notifications(user["fundacion_id"], unread_only=unread)}), 200

    @bp.route("/biblioteca/notificaciones/<int:notification_id>/leer", methods=["POST"])
    def library_notification_read(notification_id: int):
        user = _user()
        if not repo.mark_library_notification_read(user["fundacion_id"], notification_id, user):
            return jsonify({"error": "Notificación no encontrada."}), 404
        return jsonify({"message": "Notificación marcada como leída."}), 200

    @bp.route("/biblioteca/historial", methods=["GET"])
    def library_history():
        user = _user()
        return jsonify({"historial": repo.list_library_history(user["fundacion_id"], request.args.get("documento_id", type=int), request.args.get("limite", type=int) or 500)}), 200

    app.register_blueprint(bp)
