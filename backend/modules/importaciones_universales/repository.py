from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from modules.dbapi_compat import sqlite3

from .schema import SCHEMA_SQL


def now_iso(): return datetime.now(timezone.utc).isoformat(timespec="seconds")


class UniversalImportRepository:
    def __init__(self, database_path: str): self.database_path = str(database_path)
    def connect(self):
        Path(self.database_path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.database_path); conn.row_factory = sqlite3.Row; return conn
    def init_schema(self):
        with self.connect() as conn: conn.executescript(SCHEMA_SQL); conn.commit()
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
            conn.execute("UPDATE importaciones_universales SET perfil_mapeo_id=?,estado='LISTO_PARA_IMPORTAR',porcentaje=80,etapa_actual='Mapeo confirmado',confirmado_en=?,actualizado_en=? WHERE id=? AND tenant_id=?",(profile_id,now,now,import_id,tenant_id))
            conn.execute("INSERT INTO auditoria_importaciones_universal(importacion_id,tenant_id,usuario_id,evento,detalle_json,creado_en) VALUES(?,?,?,?,?,?)",(import_id,tenant_id,user_id,"MAPEO_CONFIRMADO",json.dumps({"perfil_id":profile_id,"version":version}),now)); conn.commit()
            return {"perfil_id":profile_id,"version":version,"estado":"LISTO_PARA_IMPORTAR"}
