from __future__ import annotations

import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path

from modules.dbapi_compat import sqlite3
from services.data_import.catalog import CANONICAL_FIELDS, CATALOG_VERSION, NEGATIVE_TERMS
from services.data_import.normalizers import normalize_header

from .schema import SCHEMA_SQL


def now_iso(): return datetime.now(timezone.utc).isoformat(timespec="seconds")


class UniversalImportRepository:
    def __init__(self, database_path: str): self.database_path = str(database_path)
    def connect(self):
        Path(self.database_path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.database_path); conn.row_factory = sqlite3.Row; return conn
    def init_schema(self):
        with self.connect() as conn:
            conn.executescript(SCHEMA_SQL)
            now=now_iso()
            for field,config in CANONICAL_FIELDS.items():
                for index,alias in enumerate(config.get("aliases",[])):
                    conn.execute("""INSERT INTO aliases_campos_universal(tenant_id,institucion,fuente,campo_canonico,alias_original,alias_normalizado,tipo,peso,version,creado_en)
                      VALUES(0,'','',?,?,?,?,?,?,?) ON CONFLICT(tenant_id,institucion,fuente,campo_canonico,alias_normalizado,tipo,version) DO NOTHING""",
                      (field,alias,normalize_header(alias),"POSITIVO",100 if index == 0 else 80,CATALOG_VERSION,now))
            for field,terms in NEGATIVE_TERMS.items():
                for term,weight in terms.items():
                    conn.execute("""INSERT INTO aliases_campos_universal(tenant_id,institucion,fuente,campo_canonico,alias_original,alias_normalizado,tipo,peso,version,creado_en)
                      VALUES(0,'','',?,?,?,?,?,?,?) ON CONFLICT(tenant_id,institucion,fuente,campo_canonico,alias_normalizado,tipo,version) DO NOTHING""",
                      (field,term,normalize_header(term),"NEGATIVO",weight,CATALOG_VERSION,now))
            conn.commit()
    def find_hash(self, tenant_id: int, digest: str):
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM importaciones_universales WHERE tenant_id=? AND hash_sha256=?", (tenant_id, digest)).fetchone()
            return dict(row) if row else None
    def create(self, data):
        now = now_iso()
        with self.connect() as conn:
            cur = conn.execute("""INSERT INTO importaciones_universales
              (tenant_id,usuario_id,nombre_archivo,nombre_guardado,tipo_archivo,hash_sha256,estado,porcentaje,etapa_actual,resultado_json,creado_en,actualizado_en)
              VALUES(?,?,?,?,?,?,'RECIBIDO',5,'Archivo recibido','{}',?,?)""",
              (data["tenant_id"],data.get("usuario_id"),data["nombre_archivo"],data["nombre_guardado"],data["tipo_archivo"],data["hash_sha256"],now,now))
            conn.commit(); return int(cur.lastrowid)
    def update_analysis(self, import_id: int, tenant_id: int, result):
        now = now_iso(); units=result["units"]
        state = "REQUIERE_CONFIRMACION" if result["requires_confirmation"] else "LISTO_PARA_IMPORTAR"
        with self.connect() as conn:
            conn.execute("""UPDATE importaciones_universales SET estado=?,porcentaje=70,etapa_actual=?,tabla_seleccionada=?,fila_encabezado=?,cantidad_filas=?,cantidad_unidades=?,fingerprint_estructura=?,resultado_json=?,actualizado_en=? WHERE id=? AND tenant_id=?""",
              (state,"Esperando confirmación" if result["requires_confirmation"] else "Validación completada",result["selected_table"],result["preview"]["header_row"],len(result["preview"]["rows"]),units["count"],result["structure_fingerprint"],json.dumps(result,ensure_ascii=False,default=str),now,import_id,tenant_id))
            conn.execute("INSERT INTO auditoria_importaciones_universal(importacion_id,tenant_id,evento,detalle_json,creado_en) VALUES(?,?,?,?,?)",(import_id,tenant_id,"ANALIZADA",json.dumps({"estado":state,"unidades":units["count"]}),now)); conn.commit()
        return state
    def replace_staging(self, import_id: int, tenant_id: int, rows) -> int:
        total=0
        with self.connect() as conn:
            conn.execute("DELETE FROM importaciones_filas_staging WHERE importacion_id=? AND tenant_id=?",(import_id,tenant_id))
            for item in rows:
                normalized=json.dumps({"canonical":item["canonical"],"provenance":item["provenance"]},ensure_ascii=False,default=str)
                original=json.dumps(item["original"],ensure_ascii=False,default=str)
                digest=hashlib.sha256(normalized.encode()).hexdigest()
                conn.execute("INSERT INTO importaciones_filas_staging(importacion_id,tenant_id,numero_fila,hash_fila,original_json,normalizado_json) VALUES(?,?,?,?,?,?)",(import_id,tenant_id,item["row_number"],digest,original,normalized)); total += 1
            conn.execute("UPDATE importaciones_universales SET cantidad_filas=?,actualizado_en=? WHERE id=? AND tenant_id=?",(total,now_iso(),import_id,tenant_id)); conn.commit()
        return total

    def confirmed_mapping(self, tenant_id: int, fingerprint: str):
        with self.connect() as conn:
            row=conn.execute("SELECT mapeo_json FROM perfiles_mapeo_universal WHERE tenant_id IN (0,?) AND fingerprint_estructura=? AND estado='PUBLICADO' ORDER BY CASE WHEN tenant_id=? THEN 0 ELSE 1 END, version DESC LIMIT 1",(tenant_id,fingerprint,tenant_id)).fetchone()
            return json.loads(row["mapeo_json"]) if row else None

    def validate(self, import_id: int, tenant_id: int):
        item=self.get(import_id,tenant_id)
        if not item: raise ValueError("Importación no encontrada")
        errors=[]; warnings=[]
        mapping=item["resultado"].get("mapping",{})
        for field in ("unidad.nombre","participante.numero_documento"):
            decision=mapping.get(field,{})
            if not decision.get("selected"): errors.append({"field":field,"code":"REQUIRED_FIELD_NOT_MAPPED"})
            elif decision.get("status") != "AUTO" and not item.get("perfil_mapeo_id"): errors.append({"field":field,"code":"MAPPING_REQUIRES_CONFIRMATION"})
        units=item["resultado"].get("units",{})
        if units.get("missing_name"): warnings.append({"field":"unidad.nombre","code":"MISSING_VALUES","count":units["missing_name"]})
        state="LISTO_PARA_IMPORTAR" if not errors else "REQUIERE_CONFIRMACION"
        with self.connect() as conn:
            conn.execute("UPDATE importaciones_universales SET estado=?,porcentaje=?,etapa_actual=?,cantidad_errores=?,cantidad_advertencias=?,errores_json=?,actualizado_en=? WHERE id=? AND tenant_id=?",(state,90 if not errors else 75,"Validación completada",len(errors),len(warnings),json.dumps(errors+warnings),now_iso(),import_id,tenant_id)); conn.commit()
        return {"estado":state,"errores":errors,"advertencias":warnings,"formatos":item["resultado"].get("format_compatibility",{})}

    def cancel(self, import_id: int, tenant_id: int, user_id=None):
        with self.connect() as conn:
            cur=conn.execute("UPDATE importaciones_universales SET estado='CANCELADO',etapa_actual='Cancelado por usuario',actualizado_en=? WHERE id=? AND tenant_id=? AND estado NOT IN ('COMPLETADO','CANCELADO')",(now_iso(),import_id,tenant_id))
            conn.commit(); return bool(cur.rowcount)

    def import_to_base_master(self, import_id: int, tenant_id: int, user_id=None, username="sistema"):
        item=self.get(import_id,tenant_id)
        if not item: raise ValueError("Importación no encontrada")
        if item["estado"] != "LISTO_PARA_IMPORTAR": raise ValueError("La importación debe validarse y confirmar su mapeo antes de importar.")
        now=now_iso()
        with self.connect() as conn:
            corporation=conn.execute("SELECT id FROM corporaciones WHERE fundacion_id=? ORDER BY id LIMIT 1",(tenant_id,)).fetchone()
            corporation_id=int(corporation["id"]) if corporation else None
            cur=conn.execute("""INSERT INTO cargas_archivos(tipo_fuente,nombre_archivo_original,nombre_archivo_guardado,extension,fecha_carga,usuario_id,usuario,corporacion_id,fundacion_id,total_registros,registros_validos,registros_error,estado,columnas_json,errores_json,metadata_json,fecha_actualizacion)
                VALUES('cuentame',?,?,?,?,?,?,?,?,?,?,0,'validado','[]','[]',?,?)""",
                (item["nombre_archivo"],item["nombre_guardado"],item["tipo_archivo"],now,user_id,username,corporation_id,tenant_id,item["cantidad_filas"],item["cantidad_filas"],json.dumps({"origen":"MOTOR_UNIVERSAL","importacion_id":import_id,"perfil_id":item["perfil_mapeo_id"]}),now))
            load_id=int(cur.lastrowid); imported=0; skipped=0
            rows=conn.execute("SELECT numero_fila,original_json,normalizado_json FROM importaciones_filas_staging WHERE importacion_id=? AND tenant_id=? ORDER BY numero_fila",(import_id,tenant_id)).fetchall()
            seen=set()
            for staged in rows:
                bundle=json.loads(staged["normalizado_json"]); data=bundle.get("canonical",{}); doc=data.get("participante.numero_documento")
                if not doc or doc in seen: skipped += 1; continue
                seen.add(doc)
                first=data.get("participante.primer_nombre") or ""; second=data.get("participante.segundo_nombre") or ""; last=data.get("participante.primer_apellido") or ""; second_last=data.get("participante.segundo_apellido") or ""
                names=" ".join(v for v in (first,second) if v).strip(); surnames=" ".join(v for v in (last,second_last) if v).strip(); full=data.get("participante.nombre_completo") or " ".join(v for v in (names,surnames) if v).strip()
                conn.execute("""INSERT INTO staging_cuentame(carga_id,fila,documento,tipo_documento,nombres,apellidos,nombre_completo,fecha_nacimiento,grupo_etario,sexo,estado,unidad_servicio,codigo_unidad,corporacion_id,fundacion_id,datos_json,errores_json,fecha_creacion)
                  VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",(load_id,staged["numero_fila"],doc,data.get("participante.tipo_documento"),names,surnames,full,data.get("participante.fecha_nacimiento"),data.get("participante.grupo_etario"),data.get("participante.sexo"),data.get("participante.estado") or "ACTIVO",data.get("unidad.nombre"),data.get("unidad.codigo"),corporation_id,tenant_id,staged["original_json"],"[]",now)); imported += 1
            result=item["resultado"]; result["base_maestra_carga_id"]=load_id; result["import_summary"]={"imported":imported,"skipped":skipped}
            conn.execute("UPDATE importaciones_universales SET estado=?,porcentaje=100,etapa_actual='Importado a staging de Base Maestra',resultado_json=?,actualizado_en=? WHERE id=? AND tenant_id=?",("COMPLETADO_CON_ADVERTENCIAS" if skipped else "COMPLETADO",json.dumps(result,ensure_ascii=False,default=str),now,import_id,tenant_id))
            conn.execute("INSERT INTO auditoria_importaciones_universal(importacion_id,tenant_id,usuario_id,evento,detalle_json,creado_en) VALUES(?,?,?,?,?,?)",(import_id,tenant_id,user_id,"IMPORTADO_BASE_MAESTRA",json.dumps({"carga_id":load_id,"importados":imported,"omitidos":skipped}),now)); conn.commit()
        return {"estado":"COMPLETADO_CON_ADVERTENCIAS" if skipped else "COMPLETADO","base_maestra_carga_id":load_id,"registros_importados":imported,"registros_omitidos":skipped,"siguiente_paso":"Consolidar y publicar desde Base Maestra"}
    def get(self, import_id: int, tenant_id: int):
        with self.connect() as conn:
            row=conn.execute("SELECT * FROM importaciones_universales WHERE id=? AND tenant_id=?",(import_id,tenant_id)).fetchone()
            if not row: return None
            data=dict(row); data["resultado"]=json.loads(data.pop("resultado_json") or "{}"); data["errores"]=json.loads(data.pop("errores_json") or "[]"); return data
    def audit(self, import_id: int, tenant_id: int):
        with self.connect() as conn: return [dict(r) for r in conn.execute("SELECT * FROM auditoria_importaciones_universal WHERE importacion_id=? AND tenant_id=? ORDER BY id",(import_id,tenant_id)).fetchall()]
    def save_profile(self, import_id: int, tenant_id: int, user_id: int | None, mapping: dict):
        item=self.get(import_id,tenant_id)
        if not item: raise ValueError("Importación no encontrada")
        now=now_iso()
        with self.connect() as conn:
            version=conn.execute("SELECT COALESCE(MAX(version),0)+1 v FROM perfiles_mapeo_universal WHERE tenant_id=? AND fingerprint_estructura=?",(tenant_id,item["fingerprint_estructura"])).fetchone()["v"]
            cur=conn.execute("INSERT INTO perfiles_mapeo_universal(tenant_id,nombre,fingerprint_estructura,version,estado,mapeo_json,catalogo_version,usuario_id,creado_en,publicado_en) VALUES(?,?,?,?, 'PUBLICADO',?,?,?,?,?)",(tenant_id,item["nombre_archivo"],item["fingerprint_estructura"],version,json.dumps(mapping,ensure_ascii=False),item["resultado"].get("catalog_version","unknown"),user_id,now,now))
            profile_id=int(cur.lastrowid)
            staged=conn.execute("SELECT id,normalizado_json FROM importaciones_filas_staging WHERE importacion_id=? AND tenant_id=?",(import_id,tenant_id)).fetchall()
            for row in staged:
                bundle=json.loads(row["normalizado_json"] or "{}"); provenance=bundle.get("provenance",{})
                for evidence in provenance.values():
                    evidence["confirmed_by"]=user_id; evidence["mapping_profile_id"]=profile_id; evidence["mapping_profile_version"]=version
                conn.execute("UPDATE importaciones_filas_staging SET normalizado_json=? WHERE id=?",(json.dumps(bundle,ensure_ascii=False,default=str),row["id"]))
            conn.execute("UPDATE importaciones_universales SET perfil_mapeo_id=?,estado='LISTO_PARA_IMPORTAR',porcentaje=80,etapa_actual='Mapeo confirmado',confirmado_en=?,actualizado_en=? WHERE id=? AND tenant_id=?",(profile_id,now,now,import_id,tenant_id))
            conn.execute("INSERT INTO auditoria_importaciones_universal(importacion_id,tenant_id,usuario_id,evento,detalle_json,creado_en) VALUES(?,?,?,?,?,?)",(import_id,tenant_id,user_id,"MAPEO_CONFIRMADO",json.dumps({"perfil_id":profile_id,"version":version}),now)); conn.commit()
            return {"perfil_id":profile_id,"version":version,"estado":"LISTO_PARA_IMPORTAR"}
