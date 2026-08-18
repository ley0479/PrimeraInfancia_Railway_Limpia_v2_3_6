from flask import Blueprint,g,jsonify,request
from modules.seguridad.services import require_roles
from .repository import IntegracionesConfiguracionRepository
def register_routes(app,database_path,project_root,data_dir):
 repo=IntegracionesConfiguracionRepository(database_path,project_root,data_dir);repo.init_schema();bp=Blueprint('integraciones_configuracion',__name__,url_prefix='/api/integraciones-configuracion')
 def user():u=dict(getattr(g,'current_user',None) or {});u['fundacion_id']=int(u.get('fundacion_id') or 1);u['username']=u.get('username') or 'sistema';return u
 @bp.get('/salud')
 def health():return jsonify({'status':'ok','module':'integraciones_configuracion','schema_version':1})
 @bp.get('/dashboard')
 @require_roles('SUPERADMIN','GERENTE')
 def dashboard():u=user();return jsonify(repo.dashboard(u['fundacion_id']))
 @bp.post('/parametros')
 @require_roles('SUPERADMIN')
 def parameter():
  u=user()
  try:return jsonify({'id':repo.save_parameter(u['fundacion_id'],request.get_json(silent=True) or {},u),'message':'Parámetro no sensible guardado.'}),201
  except ValueError as e:return jsonify({'error':str(e)}),400
 @bp.post('/integraciones')
 @require_roles('SUPERADMIN')
 def integration():
  u=user()
  try:return jsonify({'id':repo.save_integration(u['fundacion_id'],request.get_json(silent=True) or {},u),'message':'Conector registrado en borrador; no se ejecutó ninguna conexión externa.'}),201
  except ValueError as e:return jsonify({'error':str(e)}),400
 @bp.get('/limpieza-operativa')
 @require_roles('SUPERADMIN')
 def cleanup_preview():
  u=user();return jsonify(repo.operational_reset_preview(u['fundacion_id']))
 @bp.post('/limpieza-operativa')
 @require_roles('SUPERADMIN')
 def cleanup_operational():
  u=user();data=request.get_json(silent=True) or {}
  try:return jsonify(repo.reset_operational_data(u['fundacion_id'],u,data.get('confirmacion')))
  except ValueError as e:return jsonify({'error':str(e)}),400
  except Exception as e:return jsonify({'error':f'No se realizó la limpieza; la transacción fue revertida: {e}'}),409
 app.register_blueprint(bp)
