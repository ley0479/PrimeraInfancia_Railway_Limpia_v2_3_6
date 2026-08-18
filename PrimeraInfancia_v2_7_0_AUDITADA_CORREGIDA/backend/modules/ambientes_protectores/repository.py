from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any
from modules.dbapi_compat import sqlite3
from modules.supervision_calidad.repository import CentroSupervisionRepository
from modules.supervision_calidad.services import unit_key
from .schema import SCHEMA_SQL, SCHEMA_VERSION

ALLOWED_STATES = {'BUENO','REGULAR','MALO','FUERA_DE_SERVICIO'}
MAINT_STATES = {'PROGRAMADO','EN_PROCESO','EJECUTADO','CANCELADO'}

def now_iso(): return datetime.now().isoformat(timespec='seconds')

class AmbientesRepository:
    def __init__(self, database_path: str, data_dir: str, output_folder: str):
        self.database_path=database_path
        self.supervision=CentroSupervisionRepository(database_path,data_dir,output_folder)
    def connect(self):
        conn=sqlite3.connect(self.database_path,timeout=30); conn.row_factory=sqlite3.Row
        conn.execute('PRAGMA foreign_keys=ON'); return conn
    def init_schema(self):
        with self.connect() as conn:
            conn.executescript(SCHEMA_SQL)
            conn.execute("INSERT INTO aep_schema_version(id,version,fecha_actualizacion) VALUES(1,?,?) ON CONFLICT(id) DO UPDATE SET version=excluded.version,fecha_actualizacion=excluded.fecha_actualizacion",(SCHEMA_VERSION,now_iso()))
            conn.commit()
    def audit(self,fid,user,action,entity,eid,detail=None):
        with self.connect() as conn:
            conn.execute('INSERT INTO aep_auditoria(fundacion_id,usuario_id,usuario,accion,entidad,entidad_id,detalle_json,fecha) VALUES(?,?,?,?,?,?,?,?)',(fid,user.get('id'),user.get('username'),action,entity,eid,json.dumps(detail or {},ensure_ascii=False),now_iso())); conn.commit()
    def dashboard(self,fid,unit=None):
        where='fundacion_id=? AND activo=1'; params=[fid]
        if unit: where+=' AND unidad_clave=?'; params.append(unit_key(unit))
        with self.connect() as conn:
            assets=[dict(r) for r in conn.execute(f'SELECT * FROM aep_activos WHERE {where} ORDER BY unidad_nombre,nombre',params).fetchall()]
            mw='fundacion_id=?'; mp=[fid]
            if unit: mw+=' AND unidad_clave=?'; mp.append(unit_key(unit))
            maintenance=[dict(r) for r in conn.execute(f'SELECT * FROM aep_mantenimientos WHERE {mw} ORDER BY fecha_programada,id DESC',mp).fetchall()]
            findings=[dict(r) for r in conn.execute("SELECT * FROM csc_hallazgos WHERE fundacion_id=? AND activa=1 AND componente='Ambientes Educativos y Protectores' ORDER BY fecha_deteccion DESC",(fid,)).fetchall()]
            inspections=[dict(r) for r in conn.execute("SELECT * FROM csc_supervisiones WHERE fundacion_id=? AND activa=1 AND (tipo='AMBIENTES_PROTECTORES' OR id IN (SELECT supervision_id FROM csc_verificaciones WHERE fundacion_id=? AND componente='Ambientes Educativos y Protectores')) ORDER BY fecha_programada DESC",(fid,fid)).fetchall()]
        if unit:
            key=unit_key(unit); findings=[r for r in findings if r.get('unidad_clave')==key]; inspections=[r for r in inspections if r.get('unidad_clave')==key]
        today=date.today().isoformat()
        return {'resumen':{'activos':len(assets),'activos_criticos':sum(r['estado'] in ('MALO','FUERA_DE_SERVICIO') for r in assets),'mantenimientos_pendientes':sum(r['estado'] in ('PROGRAMADO','EN_PROCESO') for r in maintenance),'mantenimientos_vencidos':sum(r['estado']!='EJECUTADO' and r['fecha_programada']<today for r in maintenance),'hallazgos_abiertos':sum(r['estado']!='CERRADO' for r in findings),'inspecciones':len(inspections)},'activos':assets,'mantenimientos':maintenance,'hallazgos':findings,'inspecciones':inspections}
    def save_asset(self,fid,p,user,asset_id=None):
        name=str(p.get('nombre') or '').strip(); unit=str(p.get('unidad_nombre') or '').strip()
        if not name or not unit: raise ValueError('Nombre y UCA son obligatorios.')
        state=str(p.get('estado') or 'BUENO').upper(); state=state if state in ALLOWED_STATES else 'BUENO'; now=now_iso()
        with self.connect() as conn:
            if asset_id:
                conn.execute('UPDATE aep_activos SET categoria=?,nombre=?,descripcion=?,cantidad=?,estado=?,ubicacion=?,fecha_proxima_revision=?,responsable_id=?,responsable_nombre=?,actualizada_por=?,fecha_actualizacion=? WHERE fundacion_id=? AND id=?',(p.get('categoria') or 'DOTACION',name,p.get('descripcion'),max(1,int(p.get('cantidad') or 1)),state,p.get('ubicacion'),p.get('fecha_proxima_revision'),p.get('responsable_id'),p.get('responsable_nombre'),user.get('id'),now,fid,asset_id)); eid=asset_id
            else:
                code=str(p.get('codigo') or f'AEP-{datetime.now().strftime("%Y%m%d%H%M%S%f")}')
                cur=conn.execute('INSERT INTO aep_activos(fundacion_id,unidad_id,unidad_nombre,unidad_clave,codigo,categoria,nombre,descripcion,cantidad,estado,ubicacion,fecha_adquisicion,fecha_proxima_revision,responsable_id,responsable_nombre,creada_por,actualizada_por,fecha_creacion,fecha_actualizacion) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(fid,p.get('unidad_id'),unit,unit_key(unit),code,p.get('categoria') or 'DOTACION',name,p.get('descripcion'),max(1,int(p.get('cantidad') or 1)),state,p.get('ubicacion'),p.get('fecha_adquisicion'),p.get('fecha_proxima_revision'),p.get('responsable_id'),p.get('responsable_nombre'),user.get('id'),user.get('id'),now,now)); eid=int(cur.lastrowid)
            conn.commit(); row=conn.execute('SELECT * FROM aep_activos WHERE fundacion_id=? AND id=?',(fid,eid)).fetchone()
        self.audit(fid,user,'ACTUALIZAR_ACTIVO' if asset_id else 'CREAR_ACTIVO','aep_activos',eid); return dict(row)
    def create_maintenance(self,fid,p,user):
        title=str(p.get('titulo') or '').strip(); unit=str(p.get('unidad_nombre') or '').strip(); due=str(p.get('fecha_programada') or '')
        if not title or not unit or not due: raise ValueError('Título, UCA y fecha programada son obligatorios.')
        now=now_iso()
        with self.connect() as conn:
            cur=conn.execute('INSERT INTO aep_mantenimientos(fundacion_id,activo_id,unidad_id,unidad_nombre,unidad_clave,tipo,titulo,descripcion,fecha_programada,estado,prioridad,responsable_id,responsable_nombre,csc_hallazgo_id,creado_por,actualizado_por,fecha_creacion,fecha_actualizacion) VALUES(?,?,?,?,?,?,?,?,? ,?,?,?,?,?,?,?,?,?)',(fid,p.get('activo_id'),p.get('unidad_id'),unit,unit_key(unit),p.get('tipo') or 'PREVENTIVO',title,p.get('descripcion'),due,'PROGRAMADO',p.get('prioridad') or 'MEDIA',p.get('responsable_id'),p.get('responsable_nombre'),p.get('csc_hallazgo_id'),user.get('id'),user.get('id'),now,now)); eid=int(cur.lastrowid); conn.commit(); row=conn.execute('SELECT * FROM aep_mantenimientos WHERE id=? AND fundacion_id=?',(eid,fid)).fetchone()
            # calendario_entregables sigue siendo el calendario canónico; AEP guarda solo su referencia.
            calendar_key=f'aep_mantenimiento:{fid}:{eid}'
            try:
                c=conn.execute("INSERT INTO calendario_entregables(titulo,descripcion,fecha_inicio,fecha_limite,modulo,tipo_formato,responsable_id,responsable_nombre,unidad,estado,prioridad,requiere_evidencia,creado_por,fecha_creacion,actualizado_en,fundacion_id,usuario_creador_id,clave_unica,origen) VALUES(?,?,?,?,?,?,?,?,?,'pendiente',?,1,?,?,?,?,?,?,'ambientes_protectores') ON CONFLICT(clave_unica) DO UPDATE SET titulo=excluded.titulo,descripcion=excluded.descripcion,fecha_limite=excluded.fecha_limite,responsable_id=excluded.responsable_id,responsable_nombre=excluded.responsable_nombre,unidad=excluded.unidad,prioridad=excluded.prioridad,actualizado_en=excluded.actualizado_en",(title,p.get('descripcion'),date.today().isoformat(),due,'Ambientes Educativos y Protectores','MANTENIMIENTO',p.get('responsable_id'),p.get('responsable_nombre'),unit,str(p.get('prioridad') or 'MEDIA').title(),user.get('username'),now,now,fid,user.get('id'),calendar_key))
                calendar_id=int(c.lastrowid or 0)
                if not calendar_id:
                    found=conn.execute('SELECT id FROM calendario_entregables WHERE clave_unica=?',(calendar_key,)).fetchone(); calendar_id=int(found['id']) if found else 0
                conn.execute('UPDATE aep_mantenimientos SET calendario_entregable_id=? WHERE fundacion_id=? AND id=?',(calendar_id or None,fid,eid)); conn.commit()
                row=conn.execute('SELECT * FROM aep_mantenimientos WHERE id=? AND fundacion_id=?',(eid,fid)).fetchone()
            except sqlite3.OperationalError:
                conn.rollback()
        self.audit(fid,user,'PROGRAMAR_MANTENIMIENTO','aep_mantenimientos',eid); return dict(row)
    def update_maintenance(self,fid,eid,p,user,can_validate=False):
        state=str(p.get('estado') or '').upper()
        if state not in MAINT_STATES: raise ValueError('Estado de mantenimiento inválido.')
        if state=='EJECUTADO' and not can_validate: raise PermissionError('El cierre requiere validación de coordinación.')
        now=now_iso()
        with self.connect() as conn:
            conn.execute('UPDATE aep_mantenimientos SET estado=?,resultado=?,fecha_ejecucion=CASE WHEN ?=\'EJECUTADO\' THEN ? ELSE fecha_ejecucion END,validado_por=CASE WHEN ?=\'EJECUTADO\' THEN ? ELSE validado_por END,fecha_validacion=CASE WHEN ?=\'EJECUTADO\' THEN ? ELSE fecha_validacion END,actualizado_por=?,fecha_actualizacion=? WHERE fundacion_id=? AND id=?',(state,p.get('resultado'),state,date.today().isoformat(),state,user.get('id'),state,now,user.get('id'),now,fid,eid)); conn.commit(); row=conn.execute('SELECT * FROM aep_mantenimientos WHERE id=? AND fundacion_id=?',(eid,fid)).fetchone()
        if not row: raise LookupError('Mantenimiento no encontrado.')
        self.audit(fid,user,'ACTUALIZAR_MANTENIMIENTO','aep_mantenimientos',eid,{'estado':state}); return dict(row)
