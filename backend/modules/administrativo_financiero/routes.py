from flask import Blueprint,g,jsonify,request
from modules.seguridad.services import require_roles
from .repository import AdministrativoFinancieroRepository
ROLES=('SUPERADMIN','GERENTE','COORDINADOR','AUXILIAR_ADMINISTRATIVO')
def register_routes(app,database_path,data_dir,output_folder):
 repo=AdministrativoFinancieroRepository(database_path);repo.init_schema();bp=Blueprint('administrativo_financiero',__name__,url_prefix='/api/administrativo-financiero')
 def user():
  u=dict(getattr(g,'current_user',None) or {});u['fundacion_id']=int(u.get('fundacion_id') or 1);u['username']=u.get('username') or u.get('email') or 'sistema';return u
 @bp.get('/salud')
 def health():return jsonify({'status':'ok','module':'administrativo_financiero','schema_version':1})
 @bp.get('/dashboard')
 @require_roles(*ROLES)
 def dashboard():u=user();return jsonify(repo.dashboard(u['fundacion_id'],request.args.get('vigencia')))
 @bp.post('/<string:entity>')
 @require_roles(*ROLES)
 def create(entity):
  u=user()
  try:eid=repo.create(entity,u['fundacion_id'],request.get_json(silent=True) or {},u);return jsonify({'message':'Registro administrativo creado como dato trazable.','id':eid}),201
  except Exception as exc:return jsonify({'error':str(exc)}),400
 app.register_blueprint(bp)
