from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
import json

from modules.dbapi_compat import sqlite3


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


class CentroDocumentalRepository:
    def __init__(self, database_path: str):
        self.database_path = str(database_path)

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
        finally:
            connection.close()

    def audit(self, tenant: int, entity: str, entity_id: int | None, action: str, user_id=None, detail=None) -> None:
        with self.connect() as connection:
            connection.execute("INSERT INTO doc_auditoria(fundacion_id,entidad,entidad_id,accion,usuario_id,detalle_json,creado_en) VALUES(?,?,?,?,?,?,?)", (tenant,entity,entity_id,action,user_id,json.dumps(detail or {},ensure_ascii=False),now_iso()))
            connection.commit()

    def list_templates(self, tenant: int) -> list[dict]:
        with self.connect() as connection:
            rows = connection.execute("SELECT * FROM doc_plantillas WHERE (scope='GLOBAL' AND fundacion_id IS NULL) OR fundacion_id=? ORDER BY tipo_documento,nombre",(tenant,)).fetchall()
        return [dict(row) for row in rows]

    def create_template_version(self, template: dict, version: dict, user_id=None) -> dict:
        tenant = int(template["fundacion_id"])
        with self.connect() as connection:
            row = connection.execute("SELECT id FROM doc_plantillas WHERE fundacion_id=? AND codigo=?",(tenant,template["codigo"])).fetchone()
            if row:
                template_id = int(row["id"])
            else:
                cursor = connection.execute("INSERT INTO doc_plantillas(codigo,nombre,componente,tipo_documento,scope,fundacion_id,estado,protegida,creado_por,creado_en,actualizado_en) VALUES(?,?,?,?,?,?,?,?,?,?,?)",(template["codigo"],template["nombre"],template["componente"],template["tipo_documento"],template.get("scope","FUNDACION"),tenant,"CARGADA",1,user_id,now_iso(),now_iso()))
                template_id = int(cursor.lastrowid)
            duplicate = connection.execute("SELECT id FROM doc_plantilla_versiones WHERE fundacion_id=? AND hash_sha256=?",(tenant,version["hash_sha256"])).fetchone()
            if duplicate:
                raise ValueError("Esta plantilla ya fue cargada anteriormente.")
            cursor = connection.execute("INSERT INTO doc_plantilla_versiones(plantilla_id,fundacion_id,version,nombre_original,nombre_seguro,ruta_privada,mime_type,extension,hash_sha256,estado,inspeccion_json,mapa_version,usuario_creador_id,creado_en,actualizado_en) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(template_id,tenant,version["version"],version["nombre_original"],version["nombre_seguro"],version["ruta_privada"],version.get("mime_type"),version["extension"],version["hash_sha256"],version.get("estado","MAPEO_PROPUESTO"),json.dumps(version.get("inspeccion") or {},ensure_ascii=False),0,user_id,now_iso(),now_iso()))
            version_id = int(cursor.lastrowid)
            connection.execute("UPDATE doc_plantillas SET estado='MAPEO_PROPUESTO',actualizado_en=? WHERE id=?",(now_iso(),template_id))
            connection.commit()
        self.audit(tenant,"PLANTILLA_VERSION",version_id,"CARGADA",user_id,{"hash":version["hash_sha256"],"codigo":template["codigo"]})
        return self.get_version(version_id,tenant)

    def get_version(self, version_id: int, tenant: int) -> dict | None:
        with self.connect() as connection:
            row=connection.execute("SELECT v.*,p.codigo,p.nombre,p.componente,p.tipo_documento,p.scope FROM doc_plantilla_versiones v JOIN doc_plantillas p ON p.id=v.plantilla_id WHERE v.id=? AND (v.fundacion_id=? OR (v.fundacion_id IS NULL AND p.scope='GLOBAL'))",(version_id,tenant)).fetchone()
        item=dict(row) if row else None
        if item: item["inspeccion"]=json.loads(item.get("inspeccion_json") or "{}")
        return item

    def save_mapping(self, version_id: int, tenant: int, mapping: dict, user_id=None) -> dict:
        with self.connect() as connection:
            owner=connection.execute("SELECT id FROM doc_plantilla_versiones WHERE id=? AND fundacion_id=?",(version_id,tenant)).fetchone()
            if not owner: raise KeyError("Plantilla no encontrada.")
            count=connection.execute("SELECT COALESCE(MAX(version),0) n FROM doc_mapeos WHERE plantilla_version_id=?",(version_id,)).fetchone()["n"]
            cursor=connection.execute("INSERT INTO doc_mapeos(plantilla_version_id,fundacion_id,version,estado,mapa_json,usuario_creador_id,creado_en) VALUES(?,?,?,?,?,?,?)",(version_id,tenant,int(count)+1,"PROPUESTO",json.dumps(mapping,ensure_ascii=False),user_id,now_iso()))
            mapping_id=int(cursor.lastrowid); connection.commit()
        self.audit(tenant,"MAPEO",mapping_id,"PROPUESTO",user_id)
        return {"id":mapping_id,"version":int(count)+1,"estado":"PROPUESTO","mapeo":mapping}

    def approve_mapping(self, version_id: int, tenant: int, user_id=None) -> dict:
        with self.connect() as connection:
            mapping=connection.execute("SELECT * FROM doc_mapeos WHERE plantilla_version_id=? AND fundacion_id=? ORDER BY version DESC LIMIT 1",(version_id,tenant)).fetchone()
            if not mapping: raise ValueError("No existe un mapa propuesto para aprobar.")
            connection.execute("UPDATE doc_mapeos SET estado='APROBADO',usuario_aprobador_id=?,aprobado_en=? WHERE id=?",(user_id,now_iso(),mapping["id"]))
            connection.execute("UPDATE doc_plantilla_versiones SET estado='APROBADA',usuario_aprobador_id=?,mapa_version=?,actualizado_en=? WHERE id=? AND fundacion_id=?",(user_id,mapping["version"],now_iso(),version_id,tenant)); connection.commit()
        self.audit(tenant,"MAPEO",mapping["id"],"APROBADO",user_id)
        return {"id":mapping["id"],"estado":"APROBADO","version":mapping["version"]}
