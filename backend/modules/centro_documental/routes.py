from __future__ import annotations

from datetime import datetime
import hashlib
import os
from pathlib import Path
import shutil
import uuid

from flask import Blueprint, current_app, g, jsonify, request, send_file
from werkzeug.utils import secure_filename

from modules.seguridad.services import require_roles
from modules.seguridad.tenant_context import tenant_storage_root
from .repository import CentroDocumentalRepository
from .template_inspector_service import inspect_template, propose_mapping
from .theme_generation_service import generate_planning
from .narrative_service import assemble_narrative


ADMIN_ROLES = ("SUPERADMIN", "GERENTE", "ADMIN", "COORDINADOR")
PROFESSIONAL_ROLES = ADMIN_ROLES + ("DOCENTE", "NUTRICIONISTA", "PSICOSOCIAL", "ENFERMERIA")
ALLOWED_EXTENSIONS = {".docx", ".xlsx", ".xlsm", ".pdf"}
MIME_BY_EXTENSION = {
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".xlsm": "application/vnd.ms-excel.sheet.macroEnabled.12",
    ".pdf": "application/pdf",
}


def _enabled(name: str, default: bool = False) -> bool:
    value = current_app.config.get(name, os.environ.get(name, "true" if default else "false"))
    return str(value).strip().lower() in {"1", "true", "yes", "si", "sí", "on"}


def _user() -> dict:
    raw = dict(getattr(g, "current_user", {}) or {})
    return {"id": raw.get("id"), "fundacion_id": int(raw.get("fundacion_id") or 1), "rol": str(raw.get("rol") or "").upper()}


def _hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def register_centro_documental(app, database_path: str, data_dir: str) -> None:
    repository = CentroDocumentalRepository(database_path)
    blueprint = Blueprint("centro_documental", __name__, url_prefix="/api/documentos")

    @blueprint.before_request
    def feature_guard():
        if not _enabled("ENABLE_DOCUMENT_AUTOMATION", False):
            return jsonify({"error": "El Centro Documental todavía no está habilitado.", "codigo": "FEATURE_DISABLED"}), 404
        return None

    @blueprint.get("/estado")
    @require_roles(*PROFESSIONAL_ROLES)
    def state():
        return jsonify({
            "habilitado": True,
            "mapeo_plantillas": _enabled("ENABLE_TEMPLATE_MAPPING", False),
            "catalogos_respuesta": _enabled("ENABLE_RESPONSE_CATALOGS", False),
            "ia_borradores": _enabled("ENABLE_AI_DOCUMENT_DRAFTS", False),
            "ia_finalizacion": False,
            "capture": {"estado": "PLANTILLA_PENDIENTE", "generacion_habilitada": False},
        })

    @blueprint.get("/plantillas")
    @require_roles(*PROFESSIONAL_ROLES)
    def templates():
        user = _user()
        return jsonify({"plantillas": repository.list_templates(user["fundacion_id"])})

    @blueprint.post("/plantillas")
    @require_roles(*ADMIN_ROLES)
    def upload_template():
        if not _enabled("ENABLE_TEMPLATE_MAPPING", False):
            return jsonify({"error": "El mapeo de plantillas no está habilitado."}), 409
        upload = request.files.get("file")
        if not upload or not upload.filename:
            return jsonify({"error": "Falta la plantilla oficial."}), 400
        extension = Path(upload.filename).suffix.lower()
        if extension not in ALLOWED_EXTENSIONS:
            return jsonify({"error": "Solo se permiten DOCX, XLSX, XLSM o PDF."}), 415
        user = _user(); tenant = user["fundacion_id"]
        root = tenant_storage_root(data_dir, tenant) / "official_templates" / "centro_documental"
        root.mkdir(parents=True, exist_ok=True)
        temporary = root / f".upload_{uuid.uuid4().hex}{extension}"
        upload.save(temporary)
        try:
            inspection = inspect_template(temporary)
            digest = _hash(temporary)
            safe_original = secure_filename(upload.filename) or f"plantilla{extension}"
            destination = root / f"{digest}_{safe_original}"
            if not destination.exists():
                shutil.copy2(temporary, destination)
            code = str(request.form.get("codigo") or Path(safe_original).stem).strip().upper()[:100]
            document_type = str(request.form.get("tipo_documento") or code).strip().upper()[:100]
            component = str(request.form.get("componente") or "PEDAGOGICO").strip().upper()[:50]
            if document_type == "CAPTURE" and not _enabled("ENABLE_CAPTURE_FORMAT", False):
                state_value = "MAPEO_PROPUESTO"
            else:
                state_value = "MAPEO_PROPUESTO"
            version = repository.create_template_version(
                {"codigo":code,"nombre":request.form.get("nombre") or safe_original,"componente":component,"tipo_documento":document_type,"scope":"FUNDACION","fundacion_id":tenant},
                {"version":request.form.get("version") or datetime.now().strftime("%Y.%m.%d.%H%M%S"),"nombre_original":upload.filename,"nombre_seguro":destination.name,"ruta_privada":str(destination),"mime_type":MIME_BY_EXTENSION[extension],"extension":extension,"hash_sha256":digest,"estado":state_value,"inspeccion":inspection},
                user["id"],
            )
            mapping = repository.save_mapping(version["id"],tenant,propose_mapping(inspection),user["id"])
            return jsonify({"message":"Plantilla registrada; el original permanece intacto y el mapa requiere aprobación.","plantilla_version":version,"mapeo":mapping}),201
        except ValueError as exc:
            return jsonify({"error":str(exc)}),409
        finally:
            temporary.unlink(missing_ok=True)

    @blueprint.get("/plantillas/<int:version_id>/original")
    @require_roles(*ADMIN_ROLES)
    def original(version_id: int):
        user=_user(); version=repository.get_version(version_id,user["fundacion_id"])
        if not version: return jsonify({"error":"Plantilla no encontrada."}),404
        path=Path(version["ruta_privada"])
        if not path.exists(): return jsonify({"error":"Original privado no disponible."}),404
        repository.audit(user["fundacion_id"],"PLANTILLA_VERSION",version_id,"DESCARGADA",user["id"])
        return send_file(path,as_attachment=True,download_name=version["nombre_original"])

    @blueprint.put("/plantillas/<int:version_id>/mapeo")
    @require_roles(*ADMIN_ROLES)
    def update_mapping(version_id: int):
        user=_user(); payload=request.get_json(silent=True) or {}
        try: result=repository.save_mapping(version_id,user["fundacion_id"],payload,user["id"])
        except KeyError as exc: return jsonify({"error":str(exc)}),404
        return jsonify({"mapeo":result})

    @blueprint.post("/plantillas/<int:version_id>/aprobar")
    @require_roles(*ADMIN_ROLES)
    def approve_mapping(version_id: int):
        user=_user(); version=repository.get_version(version_id,user["fundacion_id"])
        if not version: return jsonify({"error":"Plantilla no encontrada."}),404
        if version["tipo_documento"] == "CAPTURE" and not _enabled("ENABLE_CAPTURE_FORMAT",False):
            return jsonify({"error":"CAPTURE permanece desactivado hasta completar su prueba oficial.","codigo":"CAPTURE_PILOT_REQUIRED"}),409
        try: approved=repository.approve_mapping(version_id,user["fundacion_id"],user["id"])
        except ValueError as exc: return jsonify({"error":str(exc)}),409
        return jsonify({"message":"Mapa aprobado.","mapeo":approved})

    @blueprint.post("/tema/generar-planeacion")
    @require_roles(*PROFESSIONAL_ROLES)
    def planning():
        payload=request.get_json(silent=True) or {}
        try: result=generate_planning(payload.get("tema"),payload.get("componente"),payload.get("tipo_actividad") or "",payload.get("grupo_poblacional") or "")
        except ValueError as exc: return jsonify({"error":str(exc)}),400
        return jsonify({"planeacion":result})

    @blueprint.post("/narrativa")
    @require_roles(*PROFESSIONAL_ROLES)
    def narrative():
        payload=request.get_json(silent=True) or {}
        try: result=assemble_narrative(payload.get("selecciones") or [])
        except ValueError as exc: return jsonify({"error":str(exc),"codigo":"CONTRADICCION"}),409
        return jsonify({"narrativa":result})

    app.register_blueprint(blueprint)
