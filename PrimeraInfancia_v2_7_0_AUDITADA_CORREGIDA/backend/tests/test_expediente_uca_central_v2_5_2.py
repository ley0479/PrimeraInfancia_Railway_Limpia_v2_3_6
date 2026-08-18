#!/usr/bin/env python3
"""Pruebas del Expediente Operativo central por UCA 2.5.2.

Valida integración en vivo, no duplicidad, aislamiento multi-fundación, índice
referencial de documentos, cronograma, alertas, indicadores y paquete de
supervisión ampliado. Todos los datos son ficticios.
"""
from __future__ import annotations

import json
import sqlite3
import tempfile
import zipfile
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from modules.gestion_integral_uca.repository import GestionIntegralRepository
from modules.gestion_integral_uca.schema import SCHEMA_VERSION
from modules.gestion_integral_uca.services import file_sha256


def require(value, message: str) -> None:
    if not value:
        raise AssertionError(message)


def prepare_database(path: Path, data_dir: Path) -> None:
    tenant_a = data_dir / "tenants" / "1" / "gestion_pedagogica"
    tenant_b = data_dir / "tenants" / "2" / "gestion_pedagogica"
    tenant_a.mkdir(parents=True, exist_ok=True)
    tenant_b.mkdir(parents=True, exist_ok=True)
    evidence_a = tenant_a / "evidencia_uca_a.txt"
    evidence_b = tenant_b / "evidencia_uca_b.txt"
    evidence_a.write_text("EVIDENCIA FICTICIA UCA A", encoding="utf-8")
    evidence_b.write_text("EVIDENCIA FICTICIA UCA B", encoding="utf-8")

    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE fundaciones(id INTEGER PRIMARY KEY,nombre TEXT,estado TEXT);
        INSERT INTO fundaciones VALUES(1,'FUNDACION A','ACTIVA'),(2,'FUNDACION B','ACTIVA');

        CREATE TABLE master_unidades(
          id INTEGER PRIMARY KEY AUTOINCREMENT,fundacion_id INTEGER,nombre TEXT,codigo_unidad TEXT,
          coordinador TEXT,total_ninos INTEGER,total_talento INTEGER,modalidad TEXT,activo INTEGER DEFAULT 1
        );
        INSERT INTO master_unidades(fundacion_id,nombre,codigo_unidad,coordinador,total_ninos,total_talento,modalidad) VALUES
          (1,'UCA CENTRAL A','UCA-A','COORDINACION A',2,2,'Propia e Intercultural'),
          (2,'UCA CENTRAL B','UCA-B','COORDINACION B',1,1,'Propia e Intercultural');

        CREATE TABLE master_ninos(
          id INTEGER PRIMARY KEY AUTOINCREMENT,fundacion_id INTEGER,documento TEXT,nombre_completo TEXT,
          unidad_servicio TEXT,codigo_unidad TEXT,activo INTEGER DEFAULT 1,estado TEXT,
          carne_salud TEXT,control_crecimiento TEXT,carne_crecimiento TEXT,vacunas TEXT,
          alertas_json TEXT,estado_validacion TEXT,fecha_actualizacion TEXT,fecha_consolidacion TEXT
        );
        INSERT INTO master_ninos(fundacion_id,documento,nombre_completo,unidad_servicio,codigo_unidad,carne_salud,vacunas,alertas_json,estado_validacion) VALUES
          (1,'1001','NIÑA FICTICIA A1','UCA CENTRAL A','UCA-A','SI','SI','[]','VALIDADO'),
          (1,'1002','NIÑO FICTICIO A2','UCA CENTRAL A','UCA-A','','NO','[\"REVISION\"]','PENDIENTE'),
          (2,'1001','NIÑA FICTICIA B1','UCA CENTRAL B','UCA-B','SI','SI','[]','VALIDADO');

        CREATE TABLE master_inconsistencias(
          id INTEGER PRIMARY KEY AUTOINCREMENT,fundacion_id INTEGER,unidad_servicio TEXT,severidad TEXT,
          tipo TEXT,descripcion TEXT,resuelta INTEGER DEFAULT 0,fecha_creacion TEXT
        );
        INSERT INTO master_inconsistencias(fundacion_id,unidad_servicio,severidad,tipo,descripcion,resuelta,fecha_creacion) VALUES
          (1,'UCA CENTRAL A','AMARILLO','DOCUMENTO','Documento ficticio pendiente',0,'2026-08-01'),
          (2,'UCA CENTRAL B','ROJO','OTRO','No debe verse desde A',0,'2026-08-01');

        CREATE TABLE gp_entregables(
          id INTEGER PRIMARY KEY AUTOINCREMENT,fundacion_id INTEGER,unidad TEXT,tipo TEXT,titulo TEXT,
          periodo TEXT,fecha_limite TEXT,estado TEXT,prioridad TEXT,activo INTEGER DEFAULT 1
        );
        INSERT INTO gp_entregables(fundacion_id,unidad,tipo,titulo,periodo,fecha_limite,estado,prioridad) VALUES
          (1,'UCA CENTRAL A','ACTA','Acta pedagógica A','2026-08','2026-08-25','APROBADA','MEDIA'),
          (2,'UCA CENTRAL B','ACTA','Acta pedagógica B','2026-08','2026-08-25','PENDIENTE','MEDIA');

        CREATE TABLE pp_planeaciones(
          id INTEGER PRIMARY KEY AUTOINCREMENT,fundacion_id INTEGER,unidad TEXT,periodo TEXT,tema TEXT,
          estado TEXT,fecha_programada TEXT,fecha_actualizacion TEXT,activo INTEGER DEFAULT 1,ruta_archivo TEXT
        );
        INSERT INTO pp_planeaciones(fundacion_id,unidad,periodo,tema,estado,fecha_programada,fecha_actualizacion) VALUES
          (1,'UCA CENTRAL A','2026-08','EXPLORACION','APROBADA','2026-08-20','2026-08-05'),
          (2,'UCA CENTRAL B','2026-08','JUEGO','APROBADA','2026-08-20','2026-08-05');

        CREATE TABLE gp_evidencias(
          id INTEGER PRIMARY KEY AUTOINCREMENT,fundacion_id INTEGER,unidad TEXT,titulo TEXT,estado TEXT,
          fecha_creacion TEXT,ruta_archivo TEXT
        );

        CREATE TABLE sn_valoraciones(
          id INTEGER PRIMARY KEY AUTOINCREMENT,fundacion_id INTEGER,documento TEXT,unidad TEXT,
          fecha_valoracion TEXT,nivel_alerta TEXT,estado_control TEXT,proximo_control TEXT,activo INTEGER DEFAULT 1
        );
        INSERT INTO sn_valoraciones(fundacion_id,documento,unidad,fecha_valoracion,nivel_alerta,estado_control,proximo_control) VALUES
          (1,'1001','UCA CENTRAL A','2026-08-01','VERDE','AL_DIA','2026-12-01'),
          (2,'1001','UCA CENTRAL B','2026-08-01','VERDE','AL_DIA','2026-12-01');

        CREATE TABLE sn_alertas(
          id INTEGER PRIMARY KEY AUTOINCREMENT,fundacion_id INTEGER,documento TEXT,unidad TEXT,tipo TEXT,
          nivel TEXT,mensaje TEXT,fecha_alerta TEXT,atendida INTEGER DEFAULT 0
        );
        INSERT INTO sn_alertas(fundacion_id,documento,unidad,tipo,nivel,mensaje,fecha_alerta,atendida) VALUES
          (1,'1002','UCA CENTRAL A','CONTROL','ALTO','Seguimiento ficticio requerido','2026-08-03',0),
          (2,'1001','UCA CENTRAL B','CONTROL','ALTO','No debe cruzarse','2026-08-03',0);

        CREATE TABLE sn_entregables_mes(
          id INTEGER PRIMARY KEY AUTOINCREMENT,fundacion_id INTEGER,codigo TEXT,mes INTEGER,anio INTEGER,
          uds TEXT,estado TEXT,porcentaje REAL,fecha_actualizacion TEXT
        );
        INSERT INTO sn_entregables_mes(fundacion_id,codigo,mes,anio,uds,estado,porcentaje,fecha_actualizacion) VALUES
          (1,'RAM',8,2026,'UCA CENTRAL A','GENERADO',100,'2026-08-05'),
          (1,'RPP',8,2026,'UCA CENTRAL A','PENDIENTE',40,'2026-08-05'),
          (1,'BIENESTARINA',8,2026,'UCA CENTRAL A','GENERADO',100,'2026-08-05'),
          (2,'RAM',8,2026,'UCA CENTRAL B','GENERADO',100,'2026-08-05');

        CREATE TABLE plantillas_oficiales_versiones(
          id INTEGER PRIMARY KEY AUTOINCREMENT,fundacion_id INTEGER,tipo_formato TEXT,codigo TEXT,
          version TEXT,estado TEXT,fecha_vigencia TEXT
        );
        INSERT INTO plantillas_oficiales_versiones(fundacion_id,tipo_formato,codigo,version,estado,fecha_vigencia) VALUES
          (1,'RAM','RAM','3','VIGENTE','2026-08-01'),
          (1,'RPP','RPP','1','VIGENTE','2026-08-01'),
          (1,'BIENESTARINA','BIENESTARINA','1','VIGENTE','2026-08-01'),
          (2,'RAM','RAM','3','VIGENTE','2026-08-01');

        CREATE TABLE th_personas(
          id INTEGER PRIMARY KEY AUTOINCREMENT,fundacion_id INTEGER,unidad TEXT,nombre TEXT,
          rol_normalizado TEXT,cargo TEXT,estado TEXT,activo INTEGER DEFAULT 1
        );
        INSERT INTO th_personas(fundacion_id,unidad,nombre,rol_normalizado,cargo,estado) VALUES
          (1,'UCA CENTRAL A','DOCENTE FICTICIA','DOCENTE','DOCENTE','ACTIVO'),
          (1,'UCA CENTRAL A','NUTRICIONISTA FICTICIA','NUTRICIONISTA','NUTRICIONISTA','ACTIVO'),
          (2,'UCA CENTRAL B','DOCENTE B','DOCENTE','DOCENTE','ACTIVO');

        CREATE TABLE th_asignaciones(
          id INTEGER PRIMARY KEY AUTOINCREMENT,fundacion_id INTEGER,unidad TEXT,persona_id INTEGER,
          rol TEXT,cargo TEXT,estado TEXT,fecha_inicio TEXT,fecha_fin TEXT
        );
        INSERT INTO th_asignaciones(fundacion_id,unidad,persona_id,rol,cargo,estado,fecha_inicio) VALUES
          (1,'UCA CENTRAL A',1,'DOCENTE','DOCENTE','ACTIVO','2026-01-01'),
          (1,'UCA CENTRAL A',2,'NUTRICIONISTA','NUTRICIONISTA','ACTIVO','2026-01-01'),
          (2,'UCA CENTRAL B',3,'DOCENTE','DOCENTE','ACTIVO','2026-01-01');

        CREATE TABLE calendario_entregables(
          id INTEGER PRIMARY KEY AUTOINCREMENT,fundacion_id INTEGER,titulo TEXT,descripcion TEXT,
          fecha_limite TEXT,modulo TEXT,responsable_nombre TEXT,unidad TEXT,estado TEXT,prioridad TEXT,
          clave_unica TEXT UNIQUE,origen TEXT
        );
        INSERT INTO calendario_entregables(fundacion_id,titulo,descripcion,fecha_limite,modulo,responsable_nombre,unidad,estado,prioridad,clave_unica,origen) VALUES
          (1,'Informe vencido A','Debe aparecer como alerta','2020-01-01','pedagogico','DOCENTE A','UCA CENTRAL A','PENDIENTE','ALTA','A-1','prueba'),
          (2,'Informe B','No debe verse desde A','2026-12-01','pedagogico','DOCENTE B','UCA CENTRAL B','PENDIENTE','MEDIA','B-1','prueba');

        CREATE TABLE rg_reportes(
          id INTEGER PRIMARY KEY AUTOINCREMENT,fundacion_id INTEGER,periodo TEXT,tipo TEXT,estado TEXT,
          total_indicadores INTEGER,total_hallazgos INTEGER,total_alertas INTEGER,total_pendientes INTEGER,fecha_generacion TEXT
        );
        INSERT INTO rg_reportes(fundacion_id,periodo,tipo,estado,total_indicadores,total_hallazgos,total_alertas,total_pendientes,fecha_generacion) VALUES
          (1,'2026-08','GERENCIAL','GENERADO',7,1,2,3,'2026-08-05'),
          (2,'2026-08','GERENCIAL','GENERADO',7,0,0,0,'2026-08-05');

        CREATE TABLE pm_paquetes(
          id INTEGER PRIMARY KEY AUTOINCREMENT,fundacion_id INTEGER,periodo TEXT,estado TEXT,
          total_archivos INTEGER,tamano_bytes INTEGER,fecha_creacion TEXT
        );
        INSERT INTO pm_paquetes(fundacion_id,periodo,estado,total_archivos,tamano_bytes,fecha_creacion) VALUES
          (1,'2026-08','GENERADO',5,1000,'2026-08-05'),
          (2,'2026-08','GENERADO',3,700,'2026-08-05');
        """
    )
    conn.execute(
        "INSERT INTO gp_evidencias(fundacion_id,unidad,titulo,estado,fecha_creacion,ruta_archivo) VALUES(?,?,?,?,?,?)",
        (1, "UCA CENTRAL A", "Evidencia pedagógica A", "APROBADA", "2026-08-05", str(evidence_a)),
    )
    conn.execute(
        "INSERT INTO gp_evidencias(fundacion_id,unidad,titulo,estado,fecha_creacion,ruta_archivo) VALUES(?,?,?,?,?,?)",
        (2, "UCA CENTRAL B", "Evidencia pedagógica B", "APROBADA", "2026-08-05", str(evidence_b)),
    )
    conn.commit()
    conn.close()


def run() -> None:
    require(SCHEMA_VERSION == 3, "La versión de esquema GIU no es 3")
    with tempfile.TemporaryDirectory(prefix="pi-expediente-v252-") as temp:
        root = Path(temp)
        database = root / "database.sqlite3"
        data_dir = root / "data"
        output = root / "output"
        prepare_database(database, data_dir)
        repo = GestionIntegralRepository(str(database), str(data_dir), str(output))
        repo.init_schema()
        user_a = {"id": 11, "username": "coordinador.a", "rol": "SUPERADMIN", "fundacion_id": 1}
        user_b = {"id": 22, "username": "coordinador.b", "rol": "SUPERADMIN", "fundacion_id": 2}

        exp_a = repo.sync_all_units(1, "2026", "CONTRATO-A", user_a)[0]
        exp_b = repo.sync_all_units(2, "2026", "CONTRATO-B", user_b)[0]
        view_a = repo.integrated_view(1, exp_a["id"])
        view_b = repo.integrated_view(2, exp_b["id"])

        components_a = {item["codigo"]: item for item in view_a["componentes"]}
        require(len(components_a) == 12, "La vista no contiene los doce dominios integrados")
        require({"familias_redes", "supervision_calidad", "planeacion_operativa", "psicosocial"} <= set(components_a), "Faltan dominios integrados recientes en la vista central")
        require(components_a["base_maestra"]["metricas"]["total_participantes"] == 2, "Base Maestra A no está filtrada por UCA")
        require({i["codigo"] for i in view_a["indicadores"]} >= {"UCA_PARTICIPANTES", "UCA_COBERTURA_VALORACION", "UCA_CRONOGRAMA"}, "Indicadores centrales incompletos")
        require(components_a["salud_nutricion"]["metricas"]["participantes_valorados"] == 1, "Cobertura de Salud A incorrecta")
        require(components_a["ram_rpp_bienestarina"]["metricas"]["ram_registros"] == 1, "RAM A no fue integrado")
        require(components_a["talento_humano"]["metricas"]["personas_activas"] == 2, "Talento Humano A incorrecto")
        require(view_b["componentes"][0]["metricas"]["total_participantes"] == 1, "Tenant B recibió población incorrecta")

        messages_a = " ".join(str(item.get("mensaje") or "") for item in view_a["alertas"])
        require("Seguimiento ficticio requerido" in messages_a, "No se integró la alerta de Salud A")
        require("No debe cruzarse" not in messages_a and "No debe verse" not in messages_a, "Se cruzaron alertas entre fundaciones")
        require(any(item.get("vencida") and item.get("titulo") == "Informe vencido A" for item in view_a["cronograma"]), "No se identificó el vencimiento de A")
        require(all(item.get("titulo") != "Informe B" for item in view_a["cronograma"]), "Se cruzó el cronograma de B")

        docs_first = repo.list_document_links(1, exp_a["id"])
        require(len(docs_first) >= 5 and sum(1 for item in docs_first if item["descargable"]) == 1, "El índice documental no vinculó correctamente las referencias de A")
        view_again = repo.integrated_view(1, exp_a["id"])
        docs_second = repo.list_document_links(1, exp_a["id"])
        require(len(docs_second) == len(docs_first), "La sincronización documental duplicó referencias")
        require(view_again["principio"].startswith("Lectura integrada"), "No se declara la estrategia sin duplicación")
        downloadable_link = next(item for item in docs_second if item["descargable"])
        found = repo.linked_document_path(1, exp_a["id"], downloadable_link["id"])
        require(found and Path(found[0]).is_file(), "La descarga referencial no resolvió el archivo autorizado")

        package = Path(repo.build_supervision_package(1, exp_a["id"], user_a))
        require(package.is_file(), "No se generó paquete de supervisión")
        with zipfile.ZipFile(package) as archive:
            names = set(archive.namelist())
            required = {
                "00_RESUMEN_EXPEDIENTE.json", "05_INDICADORES_UCA.csv", "06_ALERTAS_UCA.csv",
                "07_CRONOGRAMA_UCA.csv", "08_DOCUMENTOS_VINCULADOS.csv", "09_ESTADO_COMPONENTES.json",
                "10_PREPARACION_SUPERVISION.json", "11_FUENTES_INTEGRADAS.json", "LEEME.txt",
            }
            require(required <= names, "El paquete central de supervisión está incompleto")
            require(any(name.startswith("documentos_vinculados/") for name in names), "El paquete no incluyó el archivo referenciado")

        conn = sqlite3.connect(database)
        counts = {
            "master_ninos": conn.execute("SELECT COUNT(*) FROM master_ninos").fetchone()[0],
            "sn_valoraciones": conn.execute("SELECT COUNT(*) FROM sn_valoraciones").fetchone()[0],
            "giu_vinculos": conn.execute("SELECT COUNT(*) FROM giu_vinculos_documentales WHERE fundacion_id=1").fetchone()[0],
        }
        conn.close()
        require(counts["master_ninos"] == 3 and counts["sn_valoraciones"] == 2, "La integración duplicó registros operativos")
        require(counts["giu_vinculos"] == len(docs_second), "El índice referencial no es idempotente")

    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    js = (ROOT / "frontend" / "js" / "modules" / "gestion-integral-uca.js").read_text(encoding="utf-8")
    routes = (BACKEND / "modules" / "gestion_integral_uca" / "routes.py").read_text(encoding="utf-8")
    integrations = (BACKEND / "modules" / "gestion_integral_uca" / "integrations.py").read_text(encoding="utf-8")
    for text in ["Centro operativo", "Componentes", "Documentos", "Alertas", "Cronograma", "Indicadores"]:
        require(text in js, f"Falta la pestaña central: {text}")
    for endpoint in ["vista-unica", "preparacion-supervision", "documentos/<int:link_id>/descargar"]:
        require(endpoint in routes, f"Falta endpoint central: {endpoint}")
    require("class UCAIntegrationEngine" in integrations and "no se duplican registros operativos" in integrations.lower(), "Falta motor de integración o principio de no duplicación")
    require("gestion-integral-uca.css" in html and "gestion-integral-uca.js" in html, "La SPA no carga los recursos GIU")

    print(json.dumps({
        "ok": True,
        "schema_version": SCHEMA_VERSION,
        "componentes_integrados": 12,
        "pruebas": [
            "vista única por UCA", "aislamiento por fundación", "lectura en vivo sin duplicación",
            "índice documental idempotente", "alertas", "cronograma", "indicadores", "paquete de supervisión ampliado",
        ],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    run()
