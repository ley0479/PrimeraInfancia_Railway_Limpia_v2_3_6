from __future__ import annotations

import json
from typing import Any

from .services import connect, init_schema, now_iso, public_document, validate_against_master


def _assign_path(root: dict, dotted_path: str, value: Any) -> None:
    parts = str(dotted_path or '').split('.')
    current: Any = root
    for index, part in enumerate(parts[:-1]):
        following_is_index = parts[index + 1].isdigit()
        if isinstance(current, list):
            position = int(part)
            while len(current) <= position:
                current.append({} if not following_is_index else [])
            current = current[position]
        else:
            current = current.setdefault(part, [] if following_is_index else {})
    last = parts[-1]
    if isinstance(current, list):
        position = int(last)
        while len(current) <= position:
            current.append(None)
        current[position] = value
    else:
        current[last] = value


class IDPRepository:
    def __init__(self, database_path: str):
        self.database_path = database_path
        init_schema(database_path)

    def audit(self, tenant_id: int, event: str, document_id=None, user_id=None, stage=None, status=None, detail=None):
        conn = connect(self.database_path)
        conn.execute("INSERT INTO idp_eventos_auditoria(documento_id,fundacion_id,evento,etapa,estado,detalle_json,usuario_id,fecha) VALUES(?,?,?,?,?,?,?,?)", (document_id, tenant_id, event, stage, status, json.dumps(detail or {}, ensure_ascii=False), user_id, now_iso()))
        conn.commit(); conn.close()

    def find_duplicate(self, tenant_id: int, digest: str):
        conn = connect(self.database_path)
        row = conn.execute("SELECT * FROM idp_documentos WHERE fundacion_id=? AND sha256=?", (tenant_id, digest)).fetchone()
        conn.close()
        return public_document(row) if row else None

    def create_document(self, data: dict) -> int:
        conn = connect(self.database_path); now = now_iso()
        cur = conn.execute("""INSERT INTO idp_documentos(fundacion_id,nombre_original,nombre_guardado,ruta_privada,extension,mime_type,tamano_bytes,sha256,estado,etapa,progreso,usuario_carga_id,fecha_carga,fecha_actualizacion) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (data['fundacion_id'],data['nombre_original'],data['nombre_guardado'],data['ruta_privada'],data['extension'],data.get('mime_type'),data['tamano_bytes'],data['sha256'],'RECIBIDO','RECIBIDO',5,data.get('usuario_id'),now,now))
        document_id = int(cur.lastrowid)
        conn.execute("INSERT INTO idp_ejecuciones(documento_id,fundacion_id,intento,etapa,estado,motor,inicio) VALUES(?,?,1,'VALIDANDO_ARCHIVO','EN_PROCESO','ROUTER_IDP',?)",(document_id,data['fundacion_id'],now))
        conn.commit(); conn.close()
        self.audit(data['fundacion_id'],'DOCUMENTO_RECIBIDO',document_id,data.get('usuario_id'),'RECIBIDO','RECIBIDO',{'extension':data['extension'],'tamano_bytes':data['tamano_bytes'],'sha256':data['sha256']})
        return document_id

    def complete_extraction(self, document_id: int, tenant_id: int, raw: dict, canonical: dict, fields: list[dict], classification: tuple[str,float,str], user_id=None):
        kind, confidence, rule = classification; now = now_iso()
        needs_ocr = bool(raw.get('requiere_ocr'))
        validation = validate_against_master(self.database_path,tenant_id,canonical) if not needs_ocr else {'semaforo':'GRIS','errores_criticos':0,'advertencias':1,'coincidencias':0,'total':0,'resultados':[{'ruta_canonica':'documento','regla':'OCR_REQUERIDO','nivel':'ADVERTENCIA','estado':'PENDIENTE','mensaje':'Conecte un motor OCR para continuar.','esperado':None,'evidencia':{}}]}
        status = 'REQUIERE_OCR' if needs_ocr else 'REQUIERE_REVISION'
        conn = connect(self.database_path)
        conn.execute("""UPDATE idp_documentos SET tipo_documento=?,confianza_clasificacion=?,estado=?,etapa=?,progreso=?,motor_lectura=?,resultado_bruto_json=?,resultado_canonico_json=?,validaciones_json=?,fecha_actualizacion=? WHERE id=? AND fundacion_id=?""", (kind,confidence,status,'PENDIENTE_OCR' if needs_ocr else 'REVISION_HUMANA',65 if needs_ocr else 80,raw.get('motor'),json.dumps(raw,ensure_ascii=False,default=str),json.dumps(canonical,ensure_ascii=False,default=str),json.dumps(validation,ensure_ascii=False,default=str),now,document_id,tenant_id))
        for field in fields:
            conn.execute("""INSERT INTO idp_campos_extraidos(documento_id,fundacion_id,ruta_canonica,valor_interpretado,texto_original,confianza,estado_revision,evidencia_json,motor,regla,fecha_actualizacion) VALUES(?,?,?,?,?,?,?,?,?,?,?)""", (document_id,tenant_id,field['ruta'],json.dumps(field.get('valor'),ensure_ascii=False,default=str),str(field.get('texto_original') or ''),float(field.get('confianza') or 0),'PENDIENTE',json.dumps(field.get('evidencia') or {},ensure_ascii=False),raw.get('motor'),field.get('regla'),now))
        self._store_validations(conn,document_id,tenant_id,validation,now)
        conn.execute("UPDATE idp_ejecuciones SET etapa=?,estado='COMPLETADO',motor=?,fin=? WHERE documento_id=? AND fundacion_id=? AND estado='EN_PROCESO'",('PENDIENTE_OCR' if needs_ocr else 'REVISION_HUMANA',raw.get('motor'),now,document_id,tenant_id))
        conn.commit(); conn.close()
        self.audit(tenant_id,'EXTRACCION_COMPLETADA',document_id,user_id,'REVISION_HUMANA',status,{'motor':raw.get('motor'),'tipo_documento':kind,'confianza_clasificacion':confidence,'regla_clasificacion':rule,'campos':len(fields)})

    def restart_extraction(self, document_id: int, tenant_id: int, user_id=None):
        conn=connect(self.database_path); row=conn.execute("SELECT id FROM idp_documentos WHERE id=? AND fundacion_id=?",(document_id,tenant_id)).fetchone()
        if not row: conn.close(); raise KeyError('Documento no encontrado.')
        now=now_iso(); attempt=conn.execute("SELECT COALESCE(MAX(intento),0)+1 AS siguiente FROM idp_ejecuciones WHERE documento_id=? AND fundacion_id=?",(document_id,tenant_id)).fetchone()['siguiente']
        conn.execute("DELETE FROM idp_campos_extraidos WHERE documento_id=? AND fundacion_id=?",(document_id,tenant_id)); conn.execute("DELETE FROM idp_resultados_validacion WHERE documento_id=? AND fundacion_id=?",(document_id,tenant_id))
        conn.execute("UPDATE idp_documentos SET estado='PROCESANDO',etapa='EXTRAYENDO_OCR',progreso=45,error_codigo=NULL,error_mensaje=NULL,fecha_actualizacion=? WHERE id=? AND fundacion_id=?",(now,document_id,tenant_id))
        conn.execute("INSERT INTO idp_ejecuciones(documento_id,fundacion_id,intento,etapa,estado,motor,inicio) VALUES(?,?,?,'EXTRAYENDO_OCR','EN_PROCESO','TESSERACT_LOCAL',?)",(document_id,tenant_id,attempt,now)); conn.commit(); conn.close()
        self.audit(tenant_id,'OCR_REINTENTADO',document_id,user_id,'EXTRAYENDO_OCR','PROCESANDO',{'intento':attempt})

    @staticmethod
    def _store_validations(conn, document_id: int, tenant_id: int, validation: dict, now: str):
        conn.execute("DELETE FROM idp_resultados_validacion WHERE documento_id=? AND fundacion_id=?",(document_id,tenant_id))
        for item in validation.get('resultados') or []:
            conn.execute("""INSERT INTO idp_resultados_validacion(documento_id,fundacion_id,ruta_canonica,regla,nivel,estado,mensaje,esperado_json,evidencia_json,resuelto,fecha) VALUES(?,?,?,?,?,?,?,?,?,0,?)""",(document_id,tenant_id,item.get('ruta_canonica'),item.get('regla'),item.get('nivel'),item.get('estado'),item.get('mensaje'),json.dumps(item.get('esperado'),ensure_ascii=False,default=str),json.dumps(item.get('evidencia') or {},ensure_ascii=False),now))

    def fail_extraction(self, document_id: int, tenant_id: int, error_code: str, user_id=None):
        now=now_iso(); conn=connect(self.database_path)
        conn.execute("UPDATE idp_documentos SET estado='ERROR',etapa='ERROR',error_codigo=?,error_mensaje='La extracción no pudo completarse.',fecha_actualizacion=? WHERE id=? AND fundacion_id=?",(error_code,now,document_id,tenant_id))
        conn.execute("UPDATE idp_ejecuciones SET etapa='ERROR',estado='ERROR',fin=?,error_codigo=?,error_mensaje='La extracción no pudo completarse.' WHERE documento_id=? AND fundacion_id=? AND estado='EN_PROCESO'",(now,error_code,document_id,tenant_id))
        conn.commit(); conn.close(); self.audit(tenant_id,'EXTRACCION_ERROR',document_id,user_id,'ERROR','ERROR',{'codigo':error_code})

    def list_documents(self, tenant_id: int):
        conn=connect(self.database_path); rows=conn.execute("SELECT * FROM idp_documentos WHERE fundacion_id=? ORDER BY id DESC",(tenant_id,)).fetchall(); conn.close()
        return [public_document(row) for row in rows]

    def get_document(self, document_id: int, tenant_id: int):
        conn=connect(self.database_path)
        row=conn.execute("SELECT * FROM idp_documentos WHERE id=? AND fundacion_id=?",(document_id,tenant_id)).fetchone()
        if not row: conn.close(); return None
        item=public_document(row)
        fields=[]
        for field in conn.execute("SELECT * FROM idp_campos_extraidos WHERE documento_id=? AND fundacion_id=? ORDER BY id",(document_id,tenant_id)).fetchall():
            value=dict(field)
            try: value['valor']=json.loads(value.get('valor_interpretado') or 'null')
            except Exception: value['valor']=value.get('valor_interpretado')
            try: value['evidencia']=json.loads(value.get('evidencia_json') or '{}')
            except Exception: value['evidencia']={}
            value.pop('valor_interpretado',None); value.pop('evidencia_json',None); fields.append(value)
        item['campos']=fields
        item['resultados_validacion']=[dict(x) for x in conn.execute("SELECT id,ruta_canonica,regla,nivel,estado,mensaje,esperado_json,evidencia_json,resuelto,fecha FROM idp_resultados_validacion WHERE documento_id=? AND fundacion_id=? ORDER BY id",(document_id,tenant_id)).fetchall()]
        item['eventos']=[dict(x) for x in conn.execute("SELECT evento,etapa,estado,fecha FROM idp_eventos_auditoria WHERE documento_id=? AND fundacion_id=? ORDER BY id",(document_id,tenant_id)).fetchall()]
        conn.close(); return item

    def correct_field(self, document_id: int, field_id: int, tenant_id: int, value: Any, user_id, reason=''):
        conn=connect(self.database_path)
        field=conn.execute("SELECT * FROM idp_campos_extraidos WHERE id=? AND documento_id=? AND fundacion_id=?",(field_id,document_id,tenant_id)).fetchone()
        if not field: conn.close(); raise KeyError('Campo no encontrado.')
        previous=field['valor_interpretado']; encoded=json.dumps(value,ensure_ascii=False,default=str); now=now_iso()
        document=conn.execute("SELECT resultado_canonico_json FROM idp_documentos WHERE id=? AND fundacion_id=?",(document_id,tenant_id)).fetchone()
        try: canonical=json.loads(document['resultado_canonico_json'] or '{}') if document else {}
        except Exception: canonical={}
        _assign_path(canonical,field['ruta_canonica'],value)
        conn.execute("UPDATE idp_campos_extraidos SET valor_interpretado=?,estado_revision='CORREGIDO',usuario_correccion_id=?,fecha_actualizacion=? WHERE id=?",(encoded,user_id,now,field_id))
        conn.execute("INSERT INTO idp_correcciones_humanas(documento_id,campo_id,fundacion_id,valor_anterior,valor_nuevo,motivo,usuario_id,fecha) VALUES(?,?,?,?,?,?,?,?)",(document_id,field_id,tenant_id,previous,encoded,str(reason or '')[:500],user_id,now))
        validation=validate_against_master(self.database_path,tenant_id,canonical)
        conn.execute("UPDATE idp_documentos SET resultado_canonico_json=?,validaciones_json=?,fecha_actualizacion=? WHERE id=? AND fundacion_id=?",(json.dumps(canonical,ensure_ascii=False,default=str),json.dumps(validation,ensure_ascii=False,default=str),now,document_id,tenant_id)); self._store_validations(conn,document_id,tenant_id,validation,now); conn.commit(); conn.close()
        self.audit(tenant_id,'CAMPO_CORREGIDO',document_id,user_id,'REVISION_HUMANA','REQUIERE_REVISION',{'campo_id':field_id,'ruta':field['ruta_canonica']})

    def approve(self, document_id: int, tenant_id: int, user_id):
        conn=connect(self.database_path); row=conn.execute("SELECT estado,validaciones_json FROM idp_documentos WHERE id=? AND fundacion_id=?",(document_id,tenant_id)).fetchone()
        if not row: conn.close(); raise KeyError('Documento no encontrado.')
        if row['estado']=='REQUIERE_OCR': conn.close(); raise ValueError('El documento requiere OCR antes de aprobarse.')
        try: validation=json.loads(row['validaciones_json'] or '{}')
        except Exception: validation={}
        if int(validation.get('errores_criticos') or 0)>0: conn.close(); raise ValueError('Corrige los errores críticos de validación antes de aprobar.')
        now=now_iso(); conn.execute("UPDATE idp_documentos SET estado='APROBADO',etapa='APROBADO',progreso=100,usuario_aprobador_id=?,fecha_aprobacion=?,fecha_actualizacion=? WHERE id=? AND fundacion_id=?",(user_id,now,now,document_id,tenant_id)); conn.commit(); conn.close()
        self.audit(tenant_id,'DOCUMENTO_APROBADO',document_id,user_id,'APROBADO','APROBADO',{'importado':False})
