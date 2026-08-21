from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))

from migrations.migrate_centro_documental_v7 import migrate
from modules.centro_documental.data_context_service import search_participants,search_professionals
from modules.centro_documental.narrative_service import assemble_narrative
from modules.centro_documental.repository import CentroDocumentalRepository


def run():
    with tempfile.TemporaryDirectory() as folder:
        database=Path(folder)/"flow.sqlite"; migrate(str(database))
        connection=sqlite3.connect(database)
        connection.executescript("""
        CREATE TABLE master_ninos(id INTEGER PRIMARY KEY,documento TEXT,nui TEXT,nombre_completo TEXT,fecha_nacimiento TEXT,grupo_etario TEXT,sexo TEXT,unidad_servicio TEXT,codigo_unidad TEXT,estado TEXT,fundacion_id INTEGER,activo INTEGER);
        CREATE TABLE th_personas(id INTEGER PRIMARY KEY,nombre TEXT,cargo TEXT,rol_normalizado TEXT,unidad TEXT,estado TEXT,fundacion_id INTEGER,activo INTEGER);
        """)
        connection.executemany("INSERT INTO master_ninos VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",[(1,"100","N1","Niña Fundación A","2022-01-01","PRIMERA INFANCIA","F","UDS A","001","ACTIVO",1,1),(2,"200","N2","Niño Fundación B","2022-02-01","PRIMERA INFANCIA","M","UDS B","002","ACTIVO",2,1)])
        connection.executemany("INSERT INTO th_personas VALUES(?,?,?,?,?,?,?,?)",[(1,"Docente A","Docente","DOCENTE","UDS A","ACTIVO",1,1),(2,"Docente B","Docente","DOCENTE","UDS B","ACTIVO",2,1)]); connection.commit(); connection.close()
        assert [x["nombre_completo"] for x in search_participants(str(database),1)["participantes"]]==["Niña Fundación A"]
        assert [x["nombre"] for x in search_professionals(str(database),2)["profesionales"]]==["Docente B"]

        repo=CentroDocumentalRepository(str(database)); catalogs=repo.list_catalogs(1,"PEDAGOGICO"); assert catalogs
        option=next(o for c in catalogs if c["categoria"]=="PARTICIPACION" for o in c["opciones"] if o["codigo"]=="ACTIVA")
        item=repo.create_instance(1,{"tipo_documento":"ACTA_HOGAR","componente":"PEDAGOGICO","uds":"UDS A","tema":"Juego","planeacion":{"clasificacion":"PLANEADO"}},10)
        assert repo.get_instance(item["id"],2) is None
        selections=repo.replace_selections(item["id"],1,[{"categoria":"PARTICIPACION","opcion_id":option["id"]}],10)
        narrative=assemble_narrative([{"categoria":x["categoria"],"codigo":x["codigo"],"texto":x["texto"]} for x in selections])
        updated=repo.save_narrative(item["id"],1,narrative["texto"],10); assert updated["estado"]=="EN_ELABORACION"
        reviewed=repo.transition(item["id"],1,"ENVIAR_REVISION",10); assert reviewed["estado"]=="EN_REVISION"
        try: repo.transition(item["id"],1,"DEVOLVER",20,""); raise AssertionError("devolución sin observación")
        except ValueError: pass
        returned=repo.transition(item["id"],1,"DEVOLVER",20,"Ajustar compromiso"); assert returned["estado"]=="DEVUELTO"
        repo.transition(item["id"],1,"REENVIAR",10)
        approved=repo.transition(item["id"],1,"APROBAR",20); assert approved["estado"]=="APROBADO" and len(approved["revisiones"])==4
    print("PASS test_centro_documental_flow_v7")


if __name__=="__main__": run()
