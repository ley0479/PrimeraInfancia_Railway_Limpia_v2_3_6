from __future__ import annotations
import json,re
from datetime import datetime
from pathlib import Path
from modules.dbapi_compat import sqlite3
from .schema import SCHEMA_SQL,SCHEMA_VERSION
def now():return datetime.now().isoformat(timespec='seconds')
SENSITIVE=re.compile(r'(password|passwd|secret|token|api.?key|private.?key|credential)',re.I)
RESET_OPERATIONAL_TABLES = {
 'ninos_base_maestra': [
  'master_movimientos','master_historial_cambios','master_inconsistencias','master_publicaciones',
  'master_ninos','master_salud_nutricion','master_talento_humano','master_unidades','master_versiones',
  'beneficiarios','usuarios',
 ],
 'talento_humano': [
  'th_capacidades','th_evaluaciones','th_formaciones','th_documentos','th_asignaciones',
  'th_historial','th_sincronizaciones','th_personas','coordinadores',
 ],
 'salud_nutricion': [
  'sn_entregables_validaciones','sn_entregables_observaciones','sn_entregables_evidencias','sn_entregables_archivos',
  'sn_entregables_mes','sn_evidencias_integrales','sn_seguimientos_integrales','sn_productos_actividad',
  'sn_actividad_participantes','sn_canalizaciones','sn_documentos_salud','sn_valoracion_validaciones',
  'sn_alertas','sn_calendario','sn_adjuntos','sn_actividades_integrales','sn_expedientes_integrales',
  'sn_comparaciones','sn_cargas','sn_historial_acciones','sn_valoraciones',
 ],
}
class IntegracionesConfiguracionRepository:
 def __init__(self,database_path,project_root,data_dir):self.database_path=database_path;self.root=Path(project_root);self.data=Path(data_dir)
 def connect(self):c=sqlite3.connect(self.database_path,timeout=30);c.row_factory=sqlite3.Row;return c
 def init_schema(self):
  with self.connect() as c:c.executescript(SCHEMA_SQL);c.execute("INSERT INTO ic_schema_version(id,version,fecha_actualizacion) VALUES(1,?,?) ON CONFLICT(id) DO UPDATE SET version=excluded.version,fecha_actualizacion=excluded.fecha_actualizacion",(SCHEMA_VERSION,now()));c.commit()
 def audit(self,fid,u,a,e,eid,d=None):
  safe={k:v for k,v in (d or {}).items() if not SENSITIVE.search(str(k))}
  with self.connect() as c:c.execute('INSERT INTO ic_auditoria(fundacion_id,usuario_id,usuario,accion,entidad,entidad_id,detalle_json,fecha) VALUES(?,?,?,?,?,?,?,?)',(fid,u.get('id'),u.get('username'),a,e,eid,json.dumps(safe,ensure_ascii=False),now()));c.commit()
 def dashboard(self,fid):
  self.init_schema()
  with self.connect() as c:
   params=[dict(x) for x in c.execute("SELECT id,modulo,clave,valor,tipo,descripcion,estado,fecha_actualizacion FROM ic_parametros WHERE fundacion_id=? ORDER BY modulo,clave",(fid,)).fetchall()]
   integrations=[dict(x) for x in c.execute("SELECT id,codigo,nombre,tipo,base_url,CASE WHEN credential_ref IS NULL OR credential_ref='' THEN 0 ELSE 1 END credencial_configurada,estado,alcance,timeout_segundos,ultimo_estado,ultima_prueba,observaciones,fecha_actualizacion FROM ic_integraciones WHERE fundacion_id=? ORDER BY nombre",(fid,)).fetchall()]
   tables={x['name'] for x in c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
  modules=['seguridad','backups','institucional_normativo','motor_plantillas','calendario_inteligente','integrity_stability','facturacion_suscripcion','gestion_integral_uca']
  module_state=[{'modulo':m,'instalado':(self.root/'backend'/'modules'/m).exists() or (self.root/'backend'/'modules'/f'{m}.py').exists()} for m in modules]
  reports=sorted((self.data/'integrity').glob('integrity_gate*.json'),key=lambda p:p.stat().st_mtime,reverse=True) if (self.data/'integrity').is_dir() else []
  return {'resumen':{'parametros':len(params),'integraciones':len(integrations),'integraciones_activas':sum(x['estado']=='ACTIVA' for x in integrations),'modulos_disponibles':sum(x['instalado'] for x in module_state),'tablas_detectadas':len(tables),'gate_disponible':bool(reports)},'parametros':params,'integraciones':integrations,'modulos':module_state,'fuentes_canonicas':{'institucion':'configuracion_institucional','usuarios_roles':'usuarios_app / roles_sistema','plantillas':'plantillas_oficiales','calendario':'calendario_entregables','backups':'backups_sistema','integridad':'data/integrity'},'ultimo_gate':reports[0].name if reports else None}
 def _operational_counts(self,fid,conn=None):
  own=conn is None;c=conn or self.connect();result={};total=0
  try:
   for group,names in RESET_OPERATIONAL_TABLES.items():
    items=[];group_total=0
    for table in names:
     try:
      columns={x['name'] for x in c.execute(f'PRAGMA table_info({table})').fetchall()}
     except Exception:columns=set()
     if 'fundacion_id' not in columns:continue
     count=int(c.execute(f'SELECT COUNT(*) AS total FROM {table} WHERE fundacion_id=?',(fid,)).fetchone()['total'])
     items.append({'tabla':table,'registros':count});group_total+=count
    result[group]={'total':group_total,'tablas':items};total+=group_total
   return {'fundacion_id':fid,'total':total,'grupos':result,'preservado':['usuarios y roles','fundación','configuración','plantillas oficiales','catálogos OMS','catálogo de entregables']}
  finally:
   if own:c.close()
 def operational_reset_preview(self,fid):
  self.init_schema();return self._operational_counts(fid)
 def reset_operational_data(self,fid,u,confirmation):
  if str(confirmation or '').strip()!='LIMPIAR DATOS':raise ValueError('Confirmación inválida. Escribe exactamente LIMPIAR DATOS.')
  self.init_schema();c=self.connect()
  try:
   before=self._operational_counts(fid,c);deleted={}
   for group,names in RESET_OPERATIONAL_TABLES.items():
    deleted[group]={};
    for table in names:
     try:columns={x['name'] for x in c.execute(f'PRAGMA table_info({table})').fetchall()}
     except Exception:columns=set()
     if 'fundacion_id' not in columns:continue
     cursor=c.execute(f'DELETE FROM {table} WHERE fundacion_id=?',(fid,))
     deleted[group][table]=max(0,int(cursor.rowcount or 0))
   after=self._operational_counts(fid,c);c.commit()
  except Exception:
   c.rollback();raise
  finally:c.close()
  self.audit(fid,u,'LIMPIAR_DATOS_OPERATIVOS','fundacion',fid,{'antes':before['total'],'despues':after['total'],'eliminados':deleted})
  return {'ok':True,'antes':before,'despues':after,'eliminados':deleted}
 def save_parameter(self,fid,p,u):
  key=str(p.get('clave') or '').strip();value=str(p.get('valor') or '')
  if not key or SENSITIVE.search(key) or SENSITIVE.search(value):raise ValueError('No se permiten secretos ni credenciales en parámetros. Usa una referencia segura de entorno.')
  stamp=now()
  with self.connect() as c:c.execute("INSERT INTO ic_parametros(fundacion_id,modulo,clave,valor,tipo,descripcion,estado,actualizado_por,fecha_creacion,fecha_actualizacion) VALUES(?,?,?,?,?,?, 'ACTIVO',?,?,?) ON CONFLICT(fundacion_id,modulo,clave) DO UPDATE SET valor=excluded.valor,tipo=excluded.tipo,descripcion=excluded.descripcion,actualizado_por=excluded.actualizado_por,fecha_actualizacion=excluded.fecha_actualizacion",(fid,p.get('modulo') or 'GENERAL',key,value,p.get('tipo') or 'TEXTO',p.get('descripcion'),u.get('id'),stamp,stamp));row=c.execute('SELECT id FROM ic_parametros WHERE fundacion_id=? AND modulo=? AND clave=?',(fid,p.get('modulo') or 'GENERAL',key)).fetchone();c.commit()
  eid=int(row['id']);self.audit(fid,u,'GUARDAR_PARAMETRO','ic_parametros',eid,{'modulo':p.get('modulo'),'clave':key});return eid
 def save_integration(self,fid,p,u):
  code=str(p.get('codigo') or '').strip().upper();name=str(p.get('nombre') or '').strip();ref=str(p.get('credential_ref') or '').strip()
  if not code or not name:raise ValueError('Código y nombre son obligatorios.')
  if ref and not re.fullmatch(r'(ENV|VAULT|RAILWAY):[A-Z0-9_./-]+',ref):raise ValueError('La credencial debe ser una referencia ENV:, VAULT: o RAILWAY:, nunca el secreto.')
  stamp=now()
  with self.connect() as c:c.execute("INSERT INTO ic_integraciones(fundacion_id,codigo,nombre,tipo,base_url,credential_ref,estado,alcance,timeout_segundos,observaciones,creado_por,actualizado_por,fecha_creacion,fecha_actualizacion) VALUES(?,?,?,?,?,?, 'BORRADOR',?,?,?,?,?,?,?) ON CONFLICT(fundacion_id,codigo) DO UPDATE SET nombre=excluded.nombre,tipo=excluded.tipo,base_url=excluded.base_url,credential_ref=excluded.credential_ref,alcance=excluded.alcance,timeout_segundos=excluded.timeout_segundos,observaciones=excluded.observaciones,actualizado_por=excluded.actualizado_por,fecha_actualizacion=excluded.fecha_actualizacion",(fid,code,name,p.get('tipo') or 'API',p.get('base_url'),ref or None,p.get('alcance'),int(p.get('timeout_segundos') or 10),p.get('observaciones'),u.get('id'),u.get('id'),stamp,stamp));row=c.execute('SELECT id FROM ic_integraciones WHERE fundacion_id=? AND codigo=?',(fid,code)).fetchone();c.commit()
  eid=int(row['id']);self.audit(fid,u,'GUARDAR_INTEGRACION','ic_integraciones',eid,{'codigo':code,'nombre':name});return eid
