"""API del componente psicosocial especializado."""
from __future__ import annotations

from typing import Any

from flask import Blueprint, g, jsonify, request, send_file

from modules.seguridad.services import require_roles
from .repository import ComponentePsicosocialRepository
from .services import COORDINATION_ROLES, READ_ROLES, normalize, parse_json, unit_key


def _user() -> dict[str, Any]:
    current=getattr(g,"current_user",None) or {}
    return {**current,"id":current.get("id"),"username":current.get("username") or current.get("email") or "sistema","rol":normalize(current.get("rol")),"fundacion_id":int(current.get("fundacion_id") or 1)}


def _payload()->dict[str,Any]: return request.get_json(silent=True) or {}


def _allowed_units(user:dict[str,Any])->list[str]|None:
    if user.get("rol") in COORDINATION_ROLES:return None
    values=parse_json(user.get("unidades"),[])
    if isinstance(values,str):values=[x.strip() for x in values.split(",") if x.strip()]
    if not isinstance(values,list):return []
    return [str(x).strip() for x in values if str(x).strip()]


def _can_access_unit(unit:str|None,user:dict[str,Any])->bool:
    allowed=_allowed_units(user)
    if allowed is None:return True
    if not unit:return False
    return unit_key(unit) in {unit_key(x) for x in allowed}


def register_componente_psicosocial(app,database_path:str,data_dir:str,output_folder:str)->None:
    repo=ComponentePsicosocialRepository(database_path,data_dir,output_folder);repo.init_schema()
    bp=Blueprint("componente_psicosocial",__name__,url_prefix="/api/psicosocial")

    def _require_case(case_id:int,user:dict[str,Any])->dict[str,Any]:
        item=repo.expediente(user["fundacion_id"],case_id,user)
        if not _can_access_unit(item.get("unidad_nombre"),user):raise PermissionError("No tienes permiso sobre esta UCA.")
        if user.get("rol")=="PSICOSOCIAL" and item.get("profesional_referente_id") not in (None,user.get("id")):raise PermissionError("El expediente está asignado a otro profesional.")
        return item

    @bp.route("/salud",methods=["GET"])
    def health():return jsonify({"status":"ok","module":"componente_psicosocial","schema_version":1,"version":"2.7.0"}),200

    @bp.route("/sincronizar",methods=["POST"])
    @require_roles(*READ_ROLES)
    def sync():
        user=_user();unit=_payload().get("unidad")
        if unit and not _can_access_unit(unit,user):return jsonify({"error":"No tienes permiso sobre esta UCA."}),403
        try:return jsonify({"message":"Expedientes psicosociales sincronizados sin duplicar participantes.","resultado":repo.sync_expedientes(user["fundacion_id"],user,unit)}),200
        except Exception as exc:return jsonify({"error":str(exc)}),400

    @bp.route("/dashboard",methods=["GET"])
    @require_roles(*READ_ROLES)
    def dashboard():
        user=_user();unit=request.args.get("unidad")
        if unit and not _can_access_unit(unit,user):return jsonify({"error":"No tienes permiso sobre esta UCA."}),403
        allowed=_allowed_units(user)
        if not unit and allowed is not None and len(allowed)==1:unit=allowed[0]
        data=repo.dashboard(user["fundacion_id"],user,{"unidad":unit,"vista_coordinacion":user.get("rol") in COORDINATION_ROLES and request.args.get("vista")=="coordinacion"})
        if allowed is not None and not unit:
            data["expedientes"]=[x for x in data.get("expedientes",[]) if _can_access_unit(x.get("unidad_nombre"),user)]
            data["por_uca"]=[x for x in data.get("por_uca",[]) if _can_access_unit(x.get("unidad"),user)]
        return jsonify(data),200

    @bp.route("/expedientes",methods=["GET"])
    @require_roles(*READ_ROLES)
    def cases():
        user=_user();filters={"unidad":request.args.get("unidad"),"estado":request.args.get("estado")}
        if user.get("rol")=="PSICOSOCIAL":filters["profesional_id"]=user.get("id")
        rows=[x for x in repo.list_expedientes(user["fundacion_id"],filters) if _can_access_unit(x.get("unidad_nombre"),user)]
        return jsonify({"expedientes":rows}),200

    @bp.route("/expedientes/<int:case_id>",methods=["GET"])
    @require_roles(*READ_ROLES)
    def case_detail(case_id:int):
        user=_user()
        try:return jsonify({"expediente":_require_case(case_id,user)}),200
        except LookupError as exc:return jsonify({"error":str(exc)}),404
        except PermissionError as exc:return jsonify({"error":str(exc)}),403

    @bp.route("/expedientes/<int:case_id>/caracterizaciones",methods=["POST"])
    @require_roles(*READ_ROLES)
    def characterization_create(case_id:int):
        user=_user()
        try:_require_case(case_id,user);return jsonify({"message":"Caracterización versionada creada como borrador.","caracterizacion":repo.create_characterization(user["fundacion_id"],case_id,_payload(),user)}),201
        except LookupError as exc:return jsonify({"error":str(exc)}),404
        except PermissionError as exc:return jsonify({"error":str(exc)}),403
        except Exception as exc:return jsonify({"error":str(exc)}),400

    @bp.route("/caracterizaciones/<int:characterization_id>/<string:action>",methods=["POST"])
    @require_roles(*COORDINATION_ROLES)
    def characterization_review(characterization_id:int,action:str):
        user=_user()
        try:return jsonify({"message":"Caracterización actualizada.","caracterizacion":repo.review_characterization(user["fundacion_id"],characterization_id,user,approve=normalize(action)=="VALIDAR")}),200
        except LookupError as exc:return jsonify({"error":str(exc)}),404
        except Exception as exc:return jsonify({"error":str(exc)}),400

    @bp.route("/expedientes/<int:case_id>/planes",methods=["POST"])
    @require_roles(*READ_ROLES)
    def plan_create(case_id:int):
        user=_user()
        try:_require_case(case_id,user);return jsonify({"message":"Plan creado como borrador.","plan":repo.create_plan(user["fundacion_id"],case_id,_payload(),user)}),201
        except LookupError as exc:return jsonify({"error":str(exc)}),404
        except PermissionError as exc:return jsonify({"error":str(exc)}),403
        except Exception as exc:return jsonify({"error":str(exc)}),400

    @bp.route("/planes/<int:plan_id>/acciones",methods=["POST"])
    @require_roles(*READ_ROLES)
    def action_create(plan_id:int):
        user=_user()
        try:
            plan=repo.plan(user["fundacion_id"],plan_id);_require_case(int(plan["expediente_id"]),user)
            return jsonify({"message":"Acción creada e integrada al Motor de Gestión.","accion":repo.create_action(user["fundacion_id"],plan_id,_payload(),user)}),201
        except LookupError as exc:return jsonify({"error":str(exc)}),404
        except PermissionError as exc:return jsonify({"error":str(exc)}),403
        except Exception as exc:return jsonify({"error":str(exc)}),400

    @bp.route("/acciones/<int:action_id>",methods=["PATCH"])
    @require_roles(*READ_ROLES)
    def action_update(action_id:int):
        user=_user()
        try:return jsonify({"message":"Acción actualizada.","accion":repo.update_action(user["fundacion_id"],action_id,_payload(),user,allow_validate=user.get("rol") in COORDINATION_ROLES)}),200
        except LookupError as exc:return jsonify({"error":str(exc)}),404
        except PermissionError as exc:return jsonify({"error":str(exc)}),403
        except Exception as exc:return jsonify({"error":str(exc)}),400

    @bp.route("/planes/<int:plan_id>/cerrar",methods=["POST"])
    @require_roles(*COORDINATION_ROLES)
    def plan_close(plan_id:int):
        user=_user()
        try:
            plan=repo.plan(user["fundacion_id"],plan_id);_require_case(int(plan["expediente_id"]),user)
            return jsonify({"message":"Plan cerrado mediante validación humana.","plan":repo.close_plan(user["fundacion_id"],plan_id,_payload(),user)}),200
        except LookupError as exc:return jsonify({"error":str(exc)}),404
        except PermissionError as exc:return jsonify({"error":str(exc)}),403
        except Exception as exc:return jsonify({"error":str(exc)}),400

    @bp.route("/expedientes/<int:case_id>/actividades/<int:activity_id>/vincular",methods=["POST"])
    @require_roles(*READ_ROLES)
    def activity_link(case_id:int,activity_id:int):
        user=_user()
        try:_require_case(case_id,user);return jsonify({"message":"Actividad vinculada sin duplicarla.","expediente":repo.link_activity(user["fundacion_id"],case_id,activity_id,user)}),200
        except LookupError as exc:return jsonify({"error":str(exc)}),404
        except PermissionError as exc:return jsonify({"error":str(exc)}),403
        except Exception as exc:return jsonify({"error":str(exc)}),400

    @bp.route("/expedientes/<int:case_id>/seguimientos",methods=["POST"])
    @require_roles(*READ_ROLES)
    def followup(case_id:int):
        user=_user()
        try:_require_case(case_id,user);return jsonify({"message":"Seguimiento registrado.","seguimiento":repo.add_followup(user["fundacion_id"],case_id,_payload(),user)}),201
        except LookupError as exc:return jsonify({"error":str(exc)}),404
        except PermissionError as exc:return jsonify({"error":str(exc)}),403
        except Exception as exc:return jsonify({"error":str(exc)}),400

    @bp.route("/expedientes/<int:case_id>/informe",methods=["POST"])
    @require_roles(*READ_ROLES)
    def report(case_id:int):
        user=_user()
        try:
            _require_case(case_id,user);restricted=bool(_payload().get("incluir_restringido")) and user.get("rol") in COORDINATION_ROLES|{"PSICOSOCIAL"}
            return jsonify({"message":"Informe preparado como borrador.","documento":repo.prepare_report(user["fundacion_id"],case_id,user,restricted)}),201
        except LookupError as exc:return jsonify({"error":str(exc)}),404
        except PermissionError as exc:return jsonify({"error":str(exc)}),403
        except Exception as exc:return jsonify({"error":str(exc)}),400

    @bp.route("/documentos/<int:document_id>/descargar",methods=["GET"])
    @require_roles(*READ_ROLES)
    def document_download(document_id:int):
        user=_user()
        try:
            meta=repo.document(user["fundacion_id"],document_id)
            if not _can_access_unit(meta.get("unidad_nombre"),user):return jsonify({"error":"No tienes permiso sobre esta UCA."}),403
            found=repo.document_path(user["fundacion_id"],document_id)
            if not found:return jsonify({"error":"Documento no encontrado o integridad inválida."}),404
            path,name,mime=found;repo.audit(user["fundacion_id"],user,"DESCARGAR_DOCUMENTO",meta.get("expediente_id"),{"documento_id":document_id})
            return send_file(path,as_attachment=True,download_name=name,mimetype=mime)
        except LookupError as exc:return jsonify({"error":str(exc)}),404

    app.register_blueprint(bp)
