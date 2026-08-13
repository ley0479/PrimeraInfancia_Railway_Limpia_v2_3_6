from __future__ import annotations
from flask import Blueprint, g, jsonify, request
from modules.supervision_calidad.services import parse_json, unit_key
from .repository import AmbientesRepository

COORD={'SUPERADMIN','GERENTE','COORDINADOR','AUXILIAR_ADMINISTRATIVO'}
ALL=COORD|{'DOCENTE','NUTRICIONISTA','PSICOSOCIAL'}
def _user():
    u=dict(getattr(g,'current_user',None) or {}); u['fundacion_id']=int(u.get('fundacion_id') or 1); u['rol']=str(u.get('rol') or '').upper(); u['username']=u.get('username') or u.get('email') or 'sistema'; return u
def _allowed(u):
    if u['rol'] in COORD:return None
    values=parse_json(u.get('unidades'),[]); values=[values] if isinstance(values,str) else values
    return {unit_key(x) for x in (values or [])}
def _check(unit,u):
    allowed=_allowed(u)
    if allowed is not None and unit_key(unit) not in allowed: raise PermissionError('No tienes permiso sobre esta UCA.')
def register_routes(app,database_path,data_dir,output_folder):
    repo=AmbientesRepository(database_path,data_dir,output_folder); repo.init_schema()
    bp=Blueprint('ambientes_protectores',__name__,url_prefix='/api/ambientes-protectores')
    @bp.get('/salud')
    def health(): return jsonify({'status':'ok','module':'ambientes_protectores','schema_version':1}),200
    @bp.get('/dashboard')
    def dashboard():
        u=_user(); unit=request.args.get('unidad');
        if unit:_check(unit,u)
        data=repo.dashboard(u['fundacion_id'],unit)
        allowed=_allowed(u)
        if allowed is not None:
            for key in ('activos','mantenimientos','hallazgos','inspecciones'): data[key]=[x for x in data[key] if x.get('unidad_clave') in allowed]
        return jsonify(data),200
    @bp.post('/activos')
    def create_asset():
        u=_user(); p=request.get_json(silent=True) or {}; _check(p.get('unidad_nombre'),u)
        try:return jsonify({'activo':repo.save_asset(u['fundacion_id'],p,u)}),201
        except (ValueError,PermissionError) as e:return jsonify({'error':str(e)}),400 if isinstance(e,ValueError) else 403
    @bp.patch('/activos/<int:eid>')
    def update_asset(eid):
        u=_user(); p=request.get_json(silent=True) or {}
        try:return jsonify({'activo':repo.save_asset(u['fundacion_id'],p,u,eid)}),200
        except Exception as e:return jsonify({'error':str(e)}),400
    @bp.post('/mantenimientos')
    def create_maintenance():
        u=_user(); p=request.get_json(silent=True) or {}; _check(p.get('unidad_nombre'),u)
        try:return jsonify({'mantenimiento':repo.create_maintenance(u['fundacion_id'],p,u)}),201
        except (ValueError,PermissionError) as e:return jsonify({'error':str(e)}),400 if isinstance(e,ValueError) else 403
    @bp.patch('/mantenimientos/<int:eid>')
    def update_maintenance(eid):
        u=_user()
        try:return jsonify({'mantenimiento':repo.update_maintenance(u['fundacion_id'],eid,request.get_json(silent=True) or {},u,u['rol'] in {'SUPERADMIN','GERENTE','COORDINADOR'})}),200
        except LookupError as e:return jsonify({'error':str(e)}),404
        except PermissionError as e:return jsonify({'error':str(e)}),403
        except ValueError as e:return jsonify({'error':str(e)}),400
    app.register_blueprint(bp)
