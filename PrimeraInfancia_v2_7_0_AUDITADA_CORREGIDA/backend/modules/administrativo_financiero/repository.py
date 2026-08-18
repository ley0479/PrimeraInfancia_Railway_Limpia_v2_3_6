from __future__ import annotations
import json
from datetime import date,datetime
from typing import Any
from modules.dbapi_compat import sqlite3
from .schema import SCHEMA_SQL,SCHEMA_VERSION
def now():return datetime.now().isoformat(timespec='seconds')
class AdministrativoFinancieroRepository:
 def __init__(self,database_path):self.database_path=database_path
 def connect(self):
  c=sqlite3.connect(self.database_path,timeout=30);c.row_factory=sqlite3.Row;c.execute('PRAGMA foreign_keys=ON');return c
 def init_schema(self):
  with self.connect() as c:c.executescript(SCHEMA_SQL);c.execute("INSERT INTO af_schema_version(id,version,fecha_actualizacion) VALUES(1,?,?) ON CONFLICT(id) DO UPDATE SET version=excluded.version,fecha_actualizacion=excluded.fecha_actualizacion",(SCHEMA_VERSION,now()));c.commit()
 def audit(self,fid,u,a,e,eid,d=None):
  with self.connect() as c:c.execute('INSERT INTO af_auditoria(fundacion_id,usuario_id,usuario,accion,entidad,entidad_id,detalle_json,fecha) VALUES(?,?,?,?,?,?,?,?)',(fid,u.get('id'),u.get('username'),a,e,eid,json.dumps(d or {},ensure_ascii=False),now()));c.commit()
 def dashboard(self,fid,vigencia=None):
  self.init_schema();vigencia=vigencia or str(date.today().year)
  with self.connect() as c:
   budgets=[dict(x) for x in c.execute('SELECT * FROM af_presupuestos WHERE fundacion_id=? AND vigencia=? ORDER BY codigo_rubro',(fid,vigencia)).fetchall()]
   moves=[dict(x) for x in c.execute('SELECT * FROM af_movimientos WHERE fundacion_id=? AND presupuesto_id IN (SELECT id FROM af_presupuestos WHERE fundacion_id=? AND vigencia=?) ORDER BY fecha DESC,id DESC',(fid,fid,vigencia)).fetchall()]
   suppliers=[dict(x) for x in c.execute("SELECT * FROM af_proveedores WHERE fundacion_id=? AND estado='ACTIVO' ORDER BY razon_social",(fid,)).fetchall()]
   purchases=[dict(x) for x in c.execute('SELECT c.*,p.razon_social proveedor FROM af_compras c LEFT JOIN af_proveedores p ON p.id=c.proveedor_id AND p.fundacion_id=c.fundacion_id WHERE c.fundacion_id=? ORDER BY c.fecha_solicitud DESC,c.id DESC',(fid,)).fetchall()]
   legal=[dict(x) for x in c.execute('SELECT l.*,c.numero compra_numero,c.objeto FROM af_legalizaciones l JOIN af_compras c ON c.id=l.compra_id AND c.fundacion_id=l.fundacion_id WHERE l.fundacion_id=? ORDER BY l.fecha_limite,l.id DESC',(fid,)).fetchall()]
   try:accounts=int(c.execute('SELECT COUNT(*) n FROM cuentas_cobro_generadas WHERE fundacion_id=?',(fid,)).fetchone()['n'])
   except Exception:
    try:accounts=int(c.execute('SELECT COUNT(*) n FROM cuentas_cobro_generadas').fetchone()['n'])
    except Exception:accounts=0
  approved=sum(float(x['valor_aprobado'] or 0)+float(x['valor_modificado'] or 0) for x in budgets);executed=sum(float(x['valor'] or 0) for x in moves if x['tipo'] in ('COMPROMISO','OBLIGACION','PAGO'))
  return {'vigencia':vigencia,'resumen':{'presupuesto':approved,'ejecutado':executed,'disponible':approved-executed,'proveedores':len(suppliers),'compras_pendientes':sum(x['estado'] not in ('PAGADA','CANCELADA') for x in purchases),'legalizaciones_pendientes':sum(x['estado']!='APROBADA' for x in legal),'cuentas_cobro_generadas':accounts},'presupuestos':budgets,'movimientos':moves,'proveedores':suppliers,'compras':purchases,'legalizaciones':legal}
 def create(self,entity,fid,p,u):
  self.init_schema();stamp=now()
  with self.connect() as c:
   if entity=='presupuestos':cur=c.execute('INSERT INTO af_presupuestos(fundacion_id,contrato_id,vigencia,codigo_rubro,nombre_rubro,valor_aprobado,valor_modificado,estado,observaciones,creado_por,actualizado_por,fecha_creacion,fecha_actualizacion) VALUES(?,?,?,?,?,?,0,\'BORRADOR\',?,?,?,?,?)',(fid,p.get('contrato_id'),p.get('vigencia') or str(date.today().year),p.get('codigo_rubro'),p.get('nombre_rubro'),float(p.get('valor_aprobado') or 0),p.get('observaciones'),u.get('id'),u.get('id'),stamp,stamp))
   elif entity=='proveedores':cur=c.execute('INSERT INTO af_proveedores(fundacion_id,tipo_documento,documento,razon_social,contacto,telefono,email,estado,creado_por,fecha_creacion,fecha_actualizacion) VALUES(?,?,?,?,?,?,?,\'ACTIVO\',?,?,?)',(fid,p.get('tipo_documento'),p.get('documento'),p.get('razon_social'),p.get('contacto'),p.get('telefono'),p.get('email'),u.get('id'),stamp,stamp))
   elif entity=='compras':cur=c.execute('INSERT INTO af_compras(fundacion_id,contrato_id,presupuesto_id,proveedor_id,unidad,numero,objeto,fecha_solicitud,valor,estado,responsable_id,responsable_nombre,soporte_referencia,observaciones,creado_por,actualizado_por,fecha_creacion,fecha_actualizacion) VALUES(?,?,?,?,?,?,?,?,?,\'SOLICITADA\',?,?,?,?,?,?,?,?)',(fid,p.get('contrato_id'),p.get('presupuesto_id'),p.get('proveedor_id'),p.get('unidad'),p.get('numero'),p.get('objeto'),p.get('fecha_solicitud') or date.today().isoformat(),float(p.get('valor') or 0),p.get('responsable_id'),p.get('responsable_nombre'),p.get('soporte_referencia'),p.get('observaciones'),u.get('id'),u.get('id'),stamp,stamp))
   elif entity=='movimientos':cur=c.execute('INSERT INTO af_movimientos(fundacion_id,presupuesto_id,compra_id,tipo,fecha,valor,concepto,referencia_tipo,referencia_id,creado_por,fecha_creacion) VALUES(?,?,?,?,?,?,?,?,?,?,?)',(fid,p.get('presupuesto_id'),p.get('compra_id'),p.get('tipo'),p.get('fecha') or date.today().isoformat(),float(p.get('valor') or 0),p.get('concepto'),p.get('referencia_tipo'),p.get('referencia_id'),u.get('id'),stamp))
   elif entity=='legalizaciones':cur=c.execute('INSERT INTO af_legalizaciones(fundacion_id,compra_id,fecha_limite,valor_legalizado,estado,soporte_referencia,observaciones,creado_por,fecha_creacion,fecha_actualizacion) VALUES(?,?,?,?,\'PENDIENTE\',?,?,?,?,?)',(fid,p.get('compra_id'),p.get('fecha_limite'),float(p.get('valor_legalizado') or 0),p.get('soporte_referencia'),p.get('observaciones'),u.get('id'),stamp,stamp))
   else:raise ValueError('Entidad administrativa inválida.')
   eid=int(cur.lastrowid);c.commit()
  self.audit(fid,u,'CREAR_'+entity.upper(),'af_'+entity,eid);return eid
