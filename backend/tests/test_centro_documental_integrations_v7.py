from __future__ import annotations

import hashlib
import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))

from migrations.migrate_centro_documental_v7 import migrate
from modules.centro_documental.repository import CentroDocumentalRepository


def run():
    with tempfile.TemporaryDirectory() as folder:
        root=Path(folder); database=root/"integration.sqlite"; migrate(str(database)); connection=sqlite3.connect(database)
        connection.executescript("""
        CREATE TABLE master_ninos(id INTEGER PRIMARY KEY,documento TEXT,nui TEXT,nombre_completo TEXT,unidad_servicio TEXT,fundacion_id INTEGER,activo INTEGER);
        CREATE TABLE th_personas(id INTEGER PRIMARY KEY,nombre TEXT,documento TEXT,unidad TEXT,fundacion_id INTEGER,activo INTEGER);
        CREATE TABLE calendario_asignaciones(id INTEGER PRIMARY KEY,obligacion_id INTEGER,estado TEXT,fundacion_id INTEGER);
        CREATE TABLE calendario_requisitos(id INTEGER PRIMARY KEY,obligacion_id INTEGER,tipo TEXT,nombre TEXT,obligatorio INTEGER,orden INTEGER,fundacion_id INTEGER);
        """)
        connection.execute("INSERT INTO master_ninos VALUES(1,'100','N1','Participante A','UDS A',1,1)"); connection.execute("INSERT INTO master_ninos VALUES(2,'200','N2','Participante B','UDS B',2,1)")
        connection.execute("INSERT INTO th_personas VALUES(1,'Profesional A','900','UDS A',1,1)"); connection.execute("INSERT INTO calendario_asignaciones VALUES(50,7,'PENDIENTE',1)")
        connection.execute("INSERT INTO calendario_requisitos VALUES(1,7,'DOCUMENTO','Acta',1,1,1)"); connection.execute("INSERT INTO calendario_requisitos VALUES(2,7,'CAPTURE','CAPTURE',1,2,1)"); connection.commit(); connection.close()
        repo=CentroDocumentalRepository(str(database)); document=repo.create_instance(1,{"tipo_documento":"ACTA_GRUPAL","componente":"PEDAGOGICO","actividad_id":50,"uds":"UDS A"},1)
        participants=repo.replace_participants(document["id"],1,[{"origen_tipo":"BENEFICIARIO","origen_id":1},{"origen_tipo":"TALENTO_HUMANO","origen_id":1}]); assert len(participants)==2
        try: repo.replace_participants(document["id"],1,[{"origen_tipo":"BENEFICIARIO","origen_id":2}]); raise AssertionError("No debe vincular participante de B")
        except ValueError: pass
        requirements=repo.calendar_requirements(document["id"],1); assert requirements["vinculada"] and [x["nombre"] for x in requirements["requisitos"]]==["Acta","CAPTURE"]
        evidence=root/"foto.jpg"; evidence.write_bytes(b"fake-image-content"); digest=hashlib.sha256(evidence.read_bytes()).hexdigest()
        saved=repo.add_evidence(document["id"],1,{"actividad_id":50,"requisito":"FOTO","nombre_original":"foto.jpg","nombre_seguro":"safe.jpg","ruta_privada":str(evidence),"mime_type":"image/jpeg","tamano_bytes":evidence.stat().st_size,"hash_sha256":digest},1)
        assert saved["version"]==1 and repo.get_evidence(saved["id"],2) is None and len(repo.list_evidence(document["id"],1))==1
        generated=repo.record_version(document["id"],1,{"estado":"BORRADOR"},"documento.docx",None,"abc123",1)
        assert generated["id"]>0 and generated["version"]==1
        assert repo.get_generated_version(document["id"],1)["id"]==generated["id"]
    print("PASS test_centro_documental_integrations_v7")


if __name__=="__main__": run()
