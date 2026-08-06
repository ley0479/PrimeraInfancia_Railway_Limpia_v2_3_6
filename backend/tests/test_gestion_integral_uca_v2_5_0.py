#!/usr/bin/env python3
"""Pruebas funcionales del Expediente Operativo UCA y Biblioteca ICBF 2.5.0.

La prueba usa SQLite temporal y datos totalmente ficticios. Valida idempotencia,
aislamiento por fundación, reglas de evidencias, planes, calendario, biblioteca,
paquete de supervisión e integración estática con seguridad y frontend.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import tempfile
import zipfile
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from modules.gestion_integral_uca.repository import GestionIntegralRepository
from modules.gestion_integral_uca.schema import DEFAULT_PLANS
from modules.gestion_integral_uca.services import ROUTE_CATALOG, file_sha256


def require(value, message: str) -> None:
    if not value:
        raise AssertionError(message)


def prepare_database(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE fundaciones (
            id INTEGER PRIMARY KEY,
            nombre TEXT NOT NULL,
            estado TEXT DEFAULT 'ACTIVA'
        );
        INSERT INTO fundaciones(id,nombre,estado) VALUES
            (1,'FUNDACION PRUEBA A','ACTIVA'),
            (2,'FUNDACION PRUEBA B','ACTIVA');

        CREATE TABLE master_unidades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fundacion_id INTEGER NOT NULL,
            nombre TEXT NOT NULL,
            codigo_unidad TEXT,
            coordinador TEXT,
            total_ninos INTEGER DEFAULT 0,
            total_talento INTEGER DEFAULT 0,
            modalidad TEXT,
            activo INTEGER DEFAULT 1
        );
        INSERT INTO master_unidades
            (fundacion_id,nombre,codigo_unidad,coordinador,total_ninos,total_talento,modalidad)
        VALUES
            (1,'UCA FICTICIA COMPARTIDA','UCA-A','COORDINADOR A',12,4,'Propia e Intercultural'),
            (2,'UCA FICTICIA COMPARTIDA','UCA-B','COORDINADOR B',18,5,'Propia e Intercultural');

        CREATE TABLE master_ninos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fundacion_id INTEGER NOT NULL,
            unidad_servicio TEXT,
            activo INTEGER DEFAULT 1
        );
        INSERT INTO master_ninos(fundacion_id,unidad_servicio) VALUES
            (1,'UCA FICTICIA COMPARTIDA'),
            (2,'UCA FICTICIA COMPARTIDA');

        CREATE TABLE calendario_entregables (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fundacion_id INTEGER,
            usuario_creador_id INTEGER,
            titulo TEXT,
            descripcion TEXT,
            fecha_inicio TEXT,
            fecha_limite TEXT,
            modulo TEXT,
            tipo_formato TEXT,
            responsable_id INTEGER,
            responsable_nombre TEXT,
            unidad TEXT,
            estado TEXT,
            prioridad TEXT,
            requiere_evidencia INTEGER DEFAULT 0,
            observaciones TEXT,
            creado_por TEXT,
            fecha_creacion TEXT,
            actualizado_en TEXT,
            clave_unica TEXT UNIQUE,
            origen TEXT
        );
        """
    )
    conn.commit()
    conn.close()


def run() -> None:
    with tempfile.TemporaryDirectory(prefix="pi-giu-v250-") as temp:
        root = Path(temp)
        database = root / "database.sqlite3"
        data_dir = root / "data"
        output_dir = root / "output"
        prepare_database(database)

        repo = GestionIntegralRepository(str(database), str(data_dir), str(output_dir))
        repo.init_schema()
        user_a = {"id": 101, "username": "superadmin.a", "rol": "SUPERADMIN", "fundacion_id": 1}
        user_b = {"id": 202, "username": "superadmin.b", "rol": "SUPERADMIN", "fundacion_id": 2}

        units_a = repo.list_units(1)
        units_b = repo.list_units(2)
        require(len(units_a) == 1 and units_a[0]["codigo"] == "UCA-A", "Fundación A ve unidades incorrectas")
        require(len(units_b) == 1 and units_b[0]["codigo"] == "UCA-B", "Fundación B ve unidades incorrectas")
        require(repo.list_units(1, []) == [], "Un usuario sin UCA asignadas recibió acceso a todas las unidades")
        require(len(repo.list_units(1, ["UCA FICTICIA COMPARTIDA"])) == 1, "El filtro de UCA asignada no funciona")

        exp_a = repo.sync_all_units(1, "2026", "CONTRATO-A", user_a)
        exp_b = repo.sync_all_units(2, "2026", "CONTRATO-B", user_b)
        require(len(exp_a) == 1 and len(exp_b) == 1, "No se creó un expediente por fundación")
        require(exp_a[0]["id"] != exp_b[0]["id"], "Los tenants comparten el mismo expediente")
        require(len(exp_a[0]["ruta"]) == len(ROUTE_CATALOG), "Checklist de ruta incompleto")
        require(len(exp_a[0]["planes"]) == len(DEFAULT_PLANS) == 8, "No se sembraron los ocho planes")

        # La sincronización debe ser idempotente.
        again = repo.sync_all_units(1, "2026", "CONTRATO-A", user_a)
        require(again[0]["id"] == exp_a[0]["id"], "La sincronización duplicó el expediente")
        require(len(again[0]["ruta"]) == len(ROUTE_CATALOG), "La sincronización duplicó o perdió actividades")

        activity = next(item for item in exp_a[0]["ruta"] if item["requiere_evidencia"])
        try:
            repo.update_route_instance(1, exp_a[0]["id"], activity["id"], {"estado": "APROBADA"}, user_a)
        except ValueError:
            pass
        else:
            raise AssertionError("Se aprobó una actividad sin evidencia obligatoria")

        evidence = root / "acta_ficticia.txt"
        evidence.write_text("EVIDENCIA TOTALMENTE FICTICIA", encoding="utf-8")
        saved = repo.add_evidence(
            1,
            exp_a[0]["id"],
            activity["id"],
            {
                "nombre_original": evidence.name,
                "nombre_guardado": evidence.name,
                "ruta_archivo": str(evidence),
                "mime_type": "text/plain",
                "tamano_bytes": evidence.stat().st_size,
                "sha256": file_sha256(str(evidence)),
                "observaciones": "Prueba automática",
            },
            user_a,
        )
        require(saved["version"] == 1, "La evidencia no inició en versión 1")
        updated = repo.update_route_instance(
            1,
            exp_a[0]["id"],
            activity["id"],
            {
                "estado": "APROBADA",
                "fecha_inicio": "2026-08-01",
                "fecha_limite": "2026-08-25",
                "responsable_nombre": "RESPONSABLE FICTICIO",
            },
            user_a,
        )
        require(updated["estado"] == "APROBADA", "No se aprobó la actividad después de aportar evidencia")

        conn = sqlite3.connect(database)
        conn.row_factory = sqlite3.Row
        calendar = conn.execute(
            "SELECT * FROM calendario_entregables WHERE fundacion_id=1 AND origen='gestion_integral_uca'"
        ).fetchall()
        conn.close()
        require(calendar and calendar[0]["fecha_limite"] == "2026-08-25", "La ruta no se sincronizó con el calendario")

        first_plan = exp_a[0]["planes"][0]
        plan = repo.update_plan(
            1,
            exp_a[0]["id"],
            first_plan["id"],
            {"estado": "EN_EJECUCION", "progreso": 35, "responsable_nombre": "EQUIPO FICTICIO"},
            user_a,
        )
        require(plan["estado"] == "EN_EJECUCION" and float(plan["progreso"]) == 35, "No se actualizó el plan")

        docs_a = repo.list_library_documents(1, include_versions=True)
        docs_b = repo.list_library_documents(2, include_versions=True)
        require({item["codigo"] for item in docs_a} >= {"MT3.PP", "FORMATO_RAM", "FORMATO_RPP", "FORMATO_BIENESTARINA"}, "Biblioteca A incompleta")
        require({item["codigo"] for item in docs_b} >= {"MT3.PP", "FORMATO_RAM", "FORMATO_RPP", "FORMATO_BIENESTARINA"}, "Biblioteca B incompleta")

        custom = repo.create_library_document(
            1,
            {
                "codigo": "FORMATO_FICTICIO",
                "nombre": "Formato ficticio de prueba",
                "tipo_documento": "FORMATO_OFICIAL",
                "componente": "Transversal",
                "fuente_tipo": "REPOSITORIO_CONTROLADO",
            },
            user_a,
        )
        version_file = root / "formato_ficticio.txt"
        version_file.write_text("VERSION 1 FICTICIA", encoding="utf-8")
        version = repo.add_library_version(
            1,
            custom["id"],
            {"version": "1", "estado": "VIGENTE", "fecha_documento": "2026-08-05"},
            {
                "nombre_original": version_file.name,
                "nombre_guardado": version_file.name,
                "ruta_archivo": str(version_file),
                "mime_type": "text/plain",
                "tamano_bytes": version_file.stat().st_size,
                "sha256": file_sha256(str(version_file)),
            },
            user_a,
        )
        require(version["estado"] == "VIGENTE", "La versión no quedó vigente")
        repo.set_library_relations(
            1,
            custom["id"],
            [{"version_id": version["id"], "modulo": "expediente-operativo-uca", "tipo_relacion": "FORMATO", "obligatorio": True}],
            user_a,
        )
        require(len(repo.list_library_relations(1, custom["id"])) == 1, "No se guardó la relación biblioteca-módulo")
        require(not any(item["codigo"] == "FORMATO_FICTICIO" for item in repo.list_library_documents(2, True)), "La biblioteca cruzó fundaciones")

        package = Path(repo.build_supervision_package(1, exp_a[0]["id"], user_a))
        require(package.is_file() and package.stat().st_size > 0, "No se generó el paquete de supervisión")
        with zipfile.ZipFile(package) as archive:
            names = set(archive.namelist())
            required = {
                "00_RESUMEN_EXPEDIENTE.json",
                "01_RUTA_OPERATIVA.csv",
                "02_OCHO_PLANES.csv",
                "03_MANIFIESTO_EVIDENCIAS.csv",
                "04_TRAZABILIDAD.csv",
                "LEEME.txt",
            }
            require(required <= names, "El paquete de supervisión está incompleto")
            summary = json.loads(archive.read("00_RESUMEN_EXPEDIENTE.json"))
            require(summary["fundacion_id"] == 1, "El paquete contiene un tenant incorrecto")

    app_text = (BACKEND / "app.py").read_text(encoding="utf-8")
    security_text = (BACKEND / "modules" / "seguridad" / "services.py").read_text(encoding="utf-8")
    migration_text = (BACKEND / "migrations" / "migrate_multitenant_phase3.py").read_text(encoding="utf-8")
    html_text = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    js_text = (ROOT / "frontend" / "js" / "app.js").read_text(encoding="utf-8")
    module_js = (ROOT / "frontend" / "js" / "modules" / "gestion-integral-uca.js").read_text(encoding="utf-8")

    for needle in ["register_gestion_integral_uca", "/api/gestion-integral-uca"]:
        require(needle in app_text or needle in security_text, f"Falta integración estática: {needle}")
    require("'giu_', 'biblioteca_'" in migration_text, "La migración no reconoce las nuevas familias tenant")
    for needle in ["expediente-operativo-uca", "biblioteca-icbf"]:
        require(needle in html_text and needle in js_text + module_js, f"Falta UI de {needle}")
    require("gestion-integral-uca.js" in html_text, "El HTML no carga el módulo de Gestión Integral UCA")
    require("seccion === 'expediente-operativo-uca'" in js_text, "La SPA no inicializa el expediente UCA")
    require("seccion === 'biblioteca-icbf'" in js_text, "La SPA no inicializa la biblioteca")

    print(json.dumps({
        "ok": True,
        "ruta_actividades": len(ROUTE_CATALOG),
        "planes": len(DEFAULT_PLANS),
        "checks": [
            "aislamiento por fundación y UCA",
            "sincronización idempotente",
            "evidencia obligatoria",
            "calendario",
            "ocho planes",
            "biblioteca versionada",
            "paquete de supervisión",
            "integración frontend/backend",
        ],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    run()
