from __future__ import annotations

import os
from pathlib import Path

from flask import Blueprint, g, jsonify, request
from werkzeug.utils import secure_filename

from modules.seguridad.services import require_roles
from modules.seguridad.tenant_context import current_tenant_id, tenant_path
from services.data_import import UniversalMappingService
from services.data_import.service import file_sha256

from .repository import UniversalImportRepository

ALLOWED = {".xlsx", ".xls", ".xlsm", ".csv", ".tsv", ".txt", ".ods", ".json", ".ndjson"}
ROLES = ("SUPERADMIN", "GERENTE", "AUXILIAR_ADMINISTRATIVO", "NUTRICIONISTA")


def register_importaciones_universales(app, database_path: str, upload_folder: str) -> None:
    enabled = str(app.config.get("ENABLE_UNIVERSAL_DATA_MAPPER", os.getenv("ENABLE_UNIVERSAL_DATA_MAPPER", "false"))).lower() in {"1","true","yes","si","sí","on"}
    if not enabled: return
    repo = UniversalImportRepository(database_path); repo.init_schema()
    storage = tenant_path(upload_folder, "importaciones_universales")
    bp = Blueprint("importaciones_universales", __name__, url_prefix="/api/importaciones")

    def context():
        user=getattr(g,"current_user",{}) or {}; tenant=int(current_tenant_id(user.get("fundacion_id") or 1) or 1)
        return tenant, user.get("id")

    @bp.post("/analizar")
    @require_roles(*ROLES)
    def analyze():
        file=request.files.get("file")
        if not file or not file.filename: return jsonify({"error":"Selecciona una fuente tabular."}),400
        ext=Path(file.filename).suffix.lower()
        if ext not in ALLOWED: return jsonify({"error":"Formato tabular no permitido."}),400
        tenant,user_id=context(); os.makedirs(storage,exist_ok=True)
        name=secure_filename(file.filename) or f"fuente{ext}"; path=Path(os.fspath(storage))/name; file.save(path)
        digest=file_sha256(str(path)); previous=repo.find_hash(tenant,digest)
        if previous: return jsonify({"error":"Este archivo ya fue importado anteriormente.","importacion_id":previous["id"],"estado":previous["estado"]}),409
        import_id=repo.create({"tenant_id":tenant,"usuario_id":user_id,"nombre_archivo":file.filename,"nombre_guardado":name,"tipo_archivo":ext,"hash_sha256":digest})
        try:
            result=UniversalMappingService().analyze(str(path),request.form.get("tabla") or None)
            state=repo.update_analysis(import_id,tenant,result)
            return jsonify({"importacion_id":import_id,"estado":state,**result}),201
        except Exception as exc:
            return jsonify({"error":f"No se pudo analizar la fuente: {exc}","importacion_id":import_id}),400

    @bp.get("/<int:import_id>")
    @require_roles(*ROLES,"COORDINADOR")
    def get_import(import_id):
        tenant,_=context(); item=repo.get(import_id,tenant)
        return (jsonify(item),200) if item else (jsonify({"error":"Importación no encontrada."}),404)

    @bp.get("/<int:import_id>/tablas")
    @require_roles(*ROLES,"COORDINADOR")
    def tables(import_id):
        tenant,_=context(); item=repo.get(import_id,tenant)
        return (jsonify({"tablas":item["resultado"].get("inspection",{}).get("tables",[])}),200) if item else (jsonify({"error":"Importación no encontrada."}),404)

    @bp.get("/<int:import_id>/mapeo")
    @require_roles(*ROLES,"COORDINADOR")
    def mapping(import_id):
        tenant,_=context(); item=repo.get(import_id,tenant)
        return (jsonify({"mapeo":item["resultado"].get("mapping",{})}),200) if item else (jsonify({"error":"Importación no encontrada."}),404)

    @bp.put("/<int:import_id>/mapeo")
    @require_roles(*ROLES)
    def save_mapping(import_id):
        tenant,user_id=context(); data=request.get_json(silent=True) or {}; mapping=data.get("mapping")
        if not isinstance(mapping,dict): return jsonify({"error":"mapping debe ser un objeto JSON."}),400
        try: return jsonify(repo.save_profile(import_id,tenant,user_id,mapping)),200
        except ValueError as exc: return jsonify({"error":str(exc)}),404

    @bp.get("/<int:import_id>/unidades")
    @require_roles(*ROLES,"COORDINADOR")
    def units(import_id):
        tenant,_=context(); item=repo.get(import_id,tenant)
        return (jsonify(item["resultado"].get("units",{})),200) if item else (jsonify({"error":"Importación no encontrada."}),404)

    @bp.get("/<int:import_id>/auditoria")
    @require_roles(*ROLES,"COORDINADOR")
    def audit(import_id): tenant,_=context(); return jsonify({"eventos":repo.audit(import_id,tenant)}),200

    app.register_blueprint(bp)
