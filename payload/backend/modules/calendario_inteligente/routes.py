"""Rutas Flask del Calendario Inteligente de Entregables y Alertas Operativas."""
from __future__ import annotations

import os
from datetime import date

from flask import Blueprint, jsonify, request, send_from_directory, send_file
from modules.seguridad.tenant_context import tenant_path
from werkzeug.utils import secure_filename
from modules.operational_jobs import start_job

from .repository import CalendarioInteligenteRepository
from .services import parse_fecha

ALLOWED_CRONOGRAMA = {".xlsx", ".xls", ".xlsm", ".ods", ".csv", ".txt", ".tsv", ".tab", ".dat", ".docx", ".pdf", ".pptx", ".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}
ALLOWED_EVIDENCE = {".pdf", ".doc", ".docx", ".xlsx", ".xls", ".xlsm", ".csv", ".txt", ".png", ".jpg", ".jpeg", ".zip", ".rar"}


def _json_payload() -> dict:
    return request.get_json(silent=True) or {}


def _filters_from_request() -> dict:
    return {
        "periodo": request.args.get("periodo"),
        "anio": request.args.get("anio"),
        "coordinador": request.args.get("coordinador"),
        "unidad": request.args.get("unidad"),
        "modulo": request.args.get("modulo"),
        "estado": request.args.get("estado"),
        "responsable_nombre": request.args.get("responsable"),
        "municipio": request.args.get("municipio"),
        "fecha": request.args.get("fecha"),
    }


def register_calendario_inteligente(app, database_path: str, upload_folder: str) -> None:
    repo = CalendarioInteligenteRepository(database_path, upload_folder)
    repo.init_schema()
    module_upload = tenant_path(upload_folder, "calendario_inteligente")
    os.makedirs(module_upload, exist_ok=True)

    bp = Blueprint("calendario_inteligente", __name__, url_prefix="/api/calendario-inteligente")

    @bp.route("/dashboard", methods=["GET"])
    def dashboard():
        periodo = request.args.get("periodo") or date.today().isoformat()[:7]
        anio = request.args.get("anio") or periodo[:4]
        filters = {k: v for k, v in _filters_from_request().items() if v and k not in {"periodo", "anio"}}
        return jsonify(repo.dashboard(periodo=periodo, anio=anio, filters=filters)), 200

    @bp.route("/catalogos", methods=["GET"])
    def catalogos():
        return jsonify(repo.catalogos()), 200

    @bp.route("/entregables", methods=["GET", "POST"])
    def entregables():
        if request.method == "GET":
            filters = {k: v for k, v in _filters_from_request().items() if v}
            return jsonify({"entregables": repo.list_entregables(filters)}), 200
        data = _json_payload()
        try:
            entregable = repo.create_entregable(data, origen="manual")
            return jsonify({"message": "Entregable creado correctamente.", "entregable": entregable}), 201
        except Exception as exc:
            return jsonify({"error": str(exc)}), 400

    @bp.route("/entregables/<int:entregable_id>", methods=["GET", "PUT", "PATCH", "DELETE"])
    def entregable_detalle(entregable_id: int):
        if request.method == "GET":
            entregable = repo.get_entregable(entregable_id)
            if not entregable:
                return jsonify({"error": "Entregable no encontrado."}), 404
            return jsonify({"entregable": entregable}), 200
        if request.method in {"PUT", "PATCH"}:
            try:
                updated = repo.update_entregable(entregable_id, _json_payload())
            except Exception as exc:
                return jsonify({"error": str(exc)}), 400
            if not updated:
                return jsonify({"error": "Entregable no encontrado."}), 404
            return jsonify({"message": "Entregable actualizado.", "entregable": updated}), 200
        if not repo.delete_entregable(entregable_id):
            return jsonify({"error": "Entregable no encontrado."}), 404
        return jsonify({"message": "Entregable eliminado."}), 200

    @bp.route("/entregables/<int:entregable_id>/entregar", methods=["POST"])
    def marcar_entregado(entregable_id: int):
        data = request.form.to_dict() if request.form else _json_payload()
        updated = repo.marcar_entregado(entregable_id, observaciones=data.get("observaciones"))
        if not updated:
            return jsonify({"error": "Entregable no encontrado."}), 404
        return jsonify({"message": "Entregable marcado como entregado.", "entregable": updated}), 200

    @bp.route("/cargar-cronograma", methods=["POST"])
    def cargar_cronograma():
        if "file" not in request.files:
            return jsonify({"error": "Archivo requerido."}), 400
        file = request.files["file"]
        if not file.filename:
            return jsonify({"error": "Archivo sin nombre."}), 400
        ext = os.path.splitext(file.filename.lower())[1]
        if ext not in ALLOWED_CRONOGRAMA:
            return jsonify({"error": "Extensión no permitida para cronograma. Usa Excel, CSV, TXT, Word, PDF, PowerPoint o imagen."}), 400
        original_filename = file.filename
        saved = f"CRONOGRAMA_{date.today().isoformat()}_{secure_filename(original_filename)}"
        path = os.path.join(module_upload, saved)
        file.save(path)

        usuario = request.form.get("usuario") or request.headers.get("X-User-Name") or "sistema"
        # ALPHA33: por defecto NO guarda actividades. Primero devuelve vista previa editable.
        guardar_directo = str(request.args.get("guardar_directo") or request.form.get("guardar_directo") or "").lower() in {"1", "true", "si", "sí"}
        if not guardar_directo:
            try:
                preview = repo.registrar_preview_cronograma(path, original_filename, usuario=usuario)
            except Exception as exc:
                return jsonify({
                    "error": f"No se pudo leer el cronograma cargado: {exc}",
                    "archivo": saved,
                    "recomendacion": "Verifique que el documento tenga fecha, actividad, módulo/responsable o que la imagen tenga texto legible. Si es foto o PDF escaneado, revise OCR/Tesseract."
                }), 400
            return jsonify({
                "message": "Cronograma leído. Revisa la vista previa antes de guardar en calendario.",
                "archivo": saved,
                "cronograma_id": preview.get("cronograma_id"),
                "preview": preview,
                "modo": "preview",
            }), 200

        sync_mode = str(request.args.get("sync") or request.form.get("sync") or "").lower() in {"1", "true", "si", "sí"}
        if sync_mode:
            try:
                result = repo.import_cronograma(path, original_filename)
            except Exception as exc:
                return jsonify({
                    "error": f"No se pudo leer el cronograma cargado: {exc}",
                    "archivo": saved,
                    "recomendacion": "Verifique que el documento tenga fecha, actividad, módulo/responsable o que la imagen tenga texto legible."
                }), 400
            return jsonify({"message": "Cronograma procesado.", "archivo": saved, "resultado": result}), 200

        def _job(update):
            update(progreso=10, etapa="Leyendo cronograma", log=f"Archivo: {original_filename}")
            result = repo.import_cronograma(path, original_filename)
            update(progreso=100, etapa="Cronograma procesado")
            return {"message": "Cronograma procesado.", "archivo": saved, "resultado": result}

        job = start_job(
            "cargar_cronograma_calendario",
            _job,
            metadata={"archivo": saved, "ruta": path},
            descripcion="Carga de cronograma mensual al calendario inteligente",
        )
        return jsonify({
            "message": "Cronograma recibido. Se está procesando en segundo plano para evitar errores por túnel.",
            "job_id": job["id"],
            "job": job,
            "status_url": f"/api/jobs/{job['id']}",
            "archivo": saved,
            "modo": "segundo_plano",
        }), 202

    @bp.route("/confirmar-cronograma", methods=["POST"])
    def confirmar_cronograma():
        data = _json_payload()
        cronograma_id = int(data.get("cronograma_id") or 0)
        if not cronograma_id:
            return jsonify({"error": "cronograma_id es obligatorio."}), 400
        usuario = data.get("usuario") or request.headers.get("X-User-Name") or "sistema"
        try:
            result = repo.confirmar_cronograma(cronograma_id, data.get("actividades") or [], usuario=usuario)
            return jsonify({"message": "Cronograma guardado en calendario.", "resultado": result}), 200
        except Exception as exc:
            return jsonify({"error": str(exc)}), 400

    @bp.route("/exportar-excel", methods=["GET"])
    def exportar_excel():
        filters = {k: v for k, v in _filters_from_request().items() if v}
        try:
            out_path = repo.exportar_cronograma_excel(filters)
        except Exception as exc:
            return jsonify({"error": str(exc)}), 400
        return send_file(out_path, as_attachment=True, download_name=os.path.basename(out_path))

    @bp.route("/exportar-pdf", methods=["GET"])
    def exportar_pdf():
        filters = {k: v for k, v in _filters_from_request().items() if v}
        try:
            out_path = repo.exportar_cronograma_pdf(filters)
        except Exception as exc:
            return jsonify({"error": str(exc)}), 400
        return send_file(out_path, as_attachment=True, download_name=os.path.basename(out_path))

    @bp.route("/evidencias/upload", methods=["POST"])
    def subir_evidencia():
        if "file" not in request.files:
            return jsonify({"error": "Archivo requerido."}), 400
        file = request.files["file"]
        entregable_id = request.form.get("entregable_id", type=int)
        if not entregable_id:
            return jsonify({"error": "entregable_id es obligatorio."}), 400
        ext = os.path.splitext(file.filename.lower())[1]
        if ext not in ALLOWED_EVIDENCE:
            return jsonify({"error": "Extensión no permitida."}), 400
        saved = f"EVIDENCIA_{entregable_id}_{date.today().isoformat()}_{secure_filename(file.filename)}"
        path = os.path.join(module_upload, saved)
        file.save(path)
        updated = repo.update_entregable(entregable_id, {
            "archivo_evidencia": saved,
            "estado": "entregado" if request.form.get("marcar_entregado", "1") == "1" else request.form.get("estado", "pendiente"),
            "fecha_entrega": parse_fecha(request.form.get("fecha_entrega")) or date.today().isoformat(),
            "observaciones": request.form.get("observaciones") or "Evidencia cargada desde calendario inteligente.",
        })
        if not updated:
            return jsonify({"error": "Entregable no encontrado."}), 404
        return jsonify({"message": "Evidencia cargada correctamente.", "entregable": updated}), 200

    @bp.route("/evidencias/<path:nombre>", methods=["GET"])
    def descargar_evidencia(nombre: str):
        return send_from_directory(module_upload, nombre, as_attachment=True)

    @bp.route("/sincronizar-entrega", methods=["POST"])
    def sincronizar_entrega():
        try:
            entregable = repo.sincronizar_entrega(_json_payload())
            return jsonify({"message": "Calendario actualizado desde módulo operativo.", "entregable": entregable}), 200
        except Exception as exc:
            return jsonify({"error": str(exc)}), 400


    # ALPHA33: alias compatibles con el requerimiento /api/calendario sin retirar rutas existentes.
    alias_bp = Blueprint("calendario_alias", __name__, url_prefix="/api/calendario")

    @alias_bp.route("/cargar-cronograma", methods=["POST"])
    def alias_cargar_cronograma():
        return cargar_cronograma()

    @alias_bp.route("/confirmar-cronograma", methods=["POST"])
    def alias_confirmar_cronograma():
        return confirmar_cronograma()

    @alias_bp.route("/actividades", methods=["GET"])
    def alias_actividades():
        filters = {k: v for k, v in _filters_from_request().items() if v}
        return jsonify({"actividades": repo.list_entregables(filters)}), 200

    @alias_bp.route("/resumen", methods=["GET"])
    def alias_resumen():
        periodo = request.args.get("periodo") or date.today().isoformat()[:7]
        anio = request.args.get("anio") or periodo[:4]
        filters = {k: v for k, v in _filters_from_request().items() if v and k not in {"periodo", "anio"}}
        data = repo.dashboard(periodo=periodo, anio=anio, filters=filters)
        return jsonify({"resumen": data.get("resumen"), "alertas": data.get("alertas")}), 200

    @alias_bp.route("/actividad/<int:entregable_id>", methods=["PUT", "PATCH"])
    def alias_actualizar_actividad(entregable_id: int):
        try:
            updated = repo.update_entregable(entregable_id, _json_payload())
        except Exception as exc:
            return jsonify({"error": str(exc)}), 400
        if not updated:
            return jsonify({"error": "Actividad no encontrada."}), 404
        return jsonify({"message": "Actividad actualizada.", "actividad": updated}), 200

    @alias_bp.route("/actividad/<int:entregable_id>/entregar", methods=["POST"])
    def alias_entregar_actividad(entregable_id: int):
        return marcar_entregado(entregable_id)

    @alias_bp.route("/actividad/<int:entregable_id>", methods=["DELETE"])
    def alias_eliminar_actividad(entregable_id: int):
        if not repo.delete_entregable(entregable_id):
            return jsonify({"error": "Actividad no encontrada."}), 404
        return jsonify({"message": "Actividad eliminada."}), 200

    @alias_bp.route("/exportar-excel", methods=["GET"])
    def alias_exportar_excel():
        return exportar_excel()

    @alias_bp.route("/exportar-pdf", methods=["GET"])
    def alias_exportar_pdf():
        return exportar_pdf()

    app.register_blueprint(bp)
    app.register_blueprint(alias_bp)
