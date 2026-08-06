#!/usr/bin/env python3
"""Pruebas integrales de Supervisión/Calidad y Familias/Redes v2.5.4.

Todos los datos son ficticios. Las pruebas validan no duplicación, aislamiento,
trazabilidad, generación de productos y cierres exclusivamente humanos.
"""
from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
import zipfile
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(BACKEND / "tests"))

from modules.familias_redes.repository import FamiliasRedesRepository
from modules.familias_redes.schema import SCHEMA_VERSION as FCR_SCHEMA_VERSION
from modules.gestion_integral_uca.repository import GestionIntegralRepository
from modules.motor_gestion_proyecto.repository import MotorGestionRepository
from modules.supervision_calidad.repository import CentroSupervisionRepository
from modules.supervision_calidad.schema import SCHEMA_VERSION as CSC_SCHEMA_VERSION
from test_expediente_uca_central_v2_5_2 import prepare_database


def require(value, message: str) -> None:
    if not value:
        raise AssertionError(message)


class Upload:
    def __init__(self, name: str, content: str, mime: str = "text/plain") -> None:
        self.filename = name
        self.mimetype = mime
        self._content = content

    def save(self, path) -> None:
        Path(path).write_text(self._content, encoding="utf-8")


def expect_error(fn, contains: str) -> None:
    try:
        fn()
    except Exception as exc:  # noqa: BLE001 - la prueba valida el mensaje funcional
        require(contains.lower() in str(exc).lower(), f"Error inesperado: {exc}")
        return
    raise AssertionError(f"Se esperaba un error que contuviera: {contains}")


def run() -> None:
    require(FCR_SCHEMA_VERSION == 1, "Versión de esquema FCR inesperada")
    require(CSC_SCHEMA_VERSION == 1, "Versión de esquema CSC inesperada")

    with tempfile.TemporaryDirectory(prefix="pi-v254-") as temp:
        root = Path(temp)
        database = root / "database.sqlite3"
        data_dir = root / "data"
        output = root / "output"
        output.mkdir(parents=True, exist_ok=True)
        prepare_database(database, data_dir)

        giu = GestionIntegralRepository(str(database), str(data_dir), str(output))
        giu.init_schema()
        motor = MotorGestionRepository(str(database), str(data_dir), str(output))
        motor.init_schema()
        familias = FamiliasRedesRepository(str(database), str(data_dir), str(output))
        familias.init_schema()
        supervision = CentroSupervisionRepository(str(database), str(data_dir), str(output))
        supervision.init_schema()

        user_a = {
            "id": 11,
            "username": "coordinacion.a",
            "nombre_completo": "Coordinación A",
            "rol": "COORDINADOR",
            "fundacion_id": 1,
        }
        user_b = {
            "id": 22,
            "username": "coordinacion.b",
            "nombre_completo": "Coordinación B",
            "rol": "COORDINADOR",
            "fundacion_id": 2,
        }

        exp_a = giu.sync_all_units(1, "2026", "CONTRATO-A", user_a)[0]
        exp_b = giu.sync_all_units(2, "2026", "CONTRATO-B", user_b)[0]

        # Familias, comunidad y redes: sincronización referencial e idempotente.
        first_sync = familias.sync_family_records(1, exp_a["id"], exp_a["unidad_nombre"], exp_a.get("unidad_id"), user_a)
        second_sync = familias.sync_family_records(1, exp_a["id"], exp_a["unidad_nombre"], exp_a.get("unidad_id"), user_a)
        require(first_sync["creados"] == 2, "No se crearon los dos expedientes familiares ficticios")
        require(second_sync["creados"] == 0 and second_sync["actualizados"] == 2, "La sincronización familiar no es idempotente")
        records = familias.list_family_records(1, {"unidad": exp_a["unidad_nombre"]})
        require(len(records) == 2, "Cantidad incorrecta de expedientes familiares")

        activity = familias.create_activity(
            1,
            {
                "expediente_uca_id": exp_a["id"],
                "unidad_id": exp_a.get("unidad_id"),
                "unidad_nombre": exp_a["unidad_nombre"],
                "tipo": "ESCUELA_FAMILIAS",
                "titulo": "Escuela de familias ficticia",
                "objetivo": "Fortalecer prácticas de cuidado y crianza",
                "metodologia": "Diálogo de saberes",
                "fecha_programada": date.today().isoformat(),
                "fecha_limite_cierre": (date.today() + timedelta(days=3)).isoformat(),
                "expedientes_familiares": [row["id"] for row in records],
            },
            user_a,
        )
        generated_types = {row["tipo_documento"] for row in activity["documentos_preparados"]}
        require(generated_types == {"ACTA", "LISTADO_ASISTENCIA"}, "No se generaron acta y listado como borradores")
        require(all(row["estado"] == "BORRADOR" for row in activity["documentos_preparados"]), "Un documento fue aprobado automáticamente")

        attendance = activity["asistencias"][0]
        activity = familias.update_attendance(1, activity["id"], {"id": attendance["id"], "asistio": True}, user_a)
        require(activity["participantes_asistentes"] == 1, "No se actualizó el listado de asistencia")

        commitment = familias.create_commitment(
            1,
            {
                "actividad_id": activity["id"],
                "expediente_familiar_id": records[0]["id"],
                "expediente_uca_id": exp_a["id"],
                "unidad_nombre": exp_a["unidad_nombre"],
                "titulo": "Compromiso de seguimiento ficticio",
                "descripcion": "Asistir al próximo acompañamiento",
                "responsable_nombre": "Familia ficticia",
                "fecha_limite": (date.today() + timedelta(days=7)).isoformat(),
                "prioridad": "ALTA",
            },
            user_a,
        )
        expect_error(lambda: familias.close_commitment(1, commitment["id"], {"observaciones_cierre": "Aún no cumplido"}, user_a), "100%")
        commitment = familias.add_followup(
            1,
            commitment["id"],
            {"resultado": "Compromiso atendido", "porcentaje_reportado": 100, "fecha": date.today().isoformat()},
            user_a,
        )
        commitment = familias.close_commitment(1, commitment["id"], {"observaciones_cierre": "Validado por coordinación"}, user_a)
        require(commitment["estado"] == "CERRADO", "El compromiso no cerró mediante validación humana")

        network = familias.create_network(
            1,
            {
                "nombre": "Red territorial ficticia",
                "tipo_actor": "SALUD",
                "territorio": "Territorio de prueba",
                "contacto_nombre": "Enlace ficticio",
                "servicios": ["Orientación"],
                "rutas": ["Ruta de salud"],
            },
            user_a,
        )
        network = familias.verify_network(1, network["id"], user_a)
        require(network["fecha_verificacion"], "La red no quedó verificada")

        alert = familias.create_alert(
            1,
            {
                "expediente_familiar_id": records[0]["id"],
                "actividad_id": activity["id"],
                "expediente_uca_id": exp_a["id"],
                "unidad_nombre": exp_a["unidad_nombre"],
                "tipo": "RIESGO_DERECHOS",
                "nivel": "ALTO",
                "descripcion": "Alerta ficticia para acompañamiento",
                "entidad_ruta_id": network["id"],
                "fecha_proximo_seguimiento": (date.today() + timedelta(days=2)).isoformat(),
            },
            user_a,
        )
        expect_error(lambda: familias.update_alert(1, alert["id"], {"estado": "CERRADA"}, user_a), "validación explícita")
        expect_error(lambda: familias.close_alert(1, alert["id"], {"resultado_cierre": "Atendida"}, user_a), "evidencia")
        alert = familias.close_alert(
            1,
            alert["id"],
            {"resultado_cierre": "Ruta verificada", "evidencia_cierre": "Referencia ficticia EV-001"},
            user_a,
        )
        require(alert["estado"] == "CERRADA", "La alerta no cerró mediante resultado y evidencia")
        open_alert = familias.create_alert(
            1,
            {
                "expediente_familiar_id": records[1]["id"],
                "expediente_uca_id": exp_a["id"],
                "unidad_nombre": exp_a["unidad_nombre"],
                "tipo": "ACOMPANAMIENTO",
                "nivel": "MEDIO",
                "descripcion": "Alerta abierta ficticia para integración UCA",
                "fecha_proximo_seguimiento": (date.today() + timedelta(days=4)).isoformat(),
            },
            user_a,
        )
        require(open_alert["estado"] == "ABIERTA", "La alerta de integración no quedó abierta")

        family_evidence = familias.add_evidence(
            1,
            Upload("soporte_familia.txt", "SOPORTE FICTICIO"),
            {"actividad_id": activity["id"], "expediente_familiar_id": records[0]["id"], "tipo": "SOPORTE"},
            user_a,
        )
        require(familias.evidence_path(1, family_evidence["id"]), "La evidencia familiar no conserva integridad")

        family_package = familias.prepare_summary_package(1, user_a, {"unidad": exp_a["unidad_nombre"]})
        package_path = familias.package_path(1, family_package["ruta"])
        require(package_path and package_path.is_file(), "No se generó el paquete familiar")
        with zipfile.ZipFile(package_path) as archive:
            require({"00_RESUMEN.json", "LEEME.txt"} <= set(archive.namelist()), "Paquete familiar incompleto")

        # Supervisión, auditoría y calidad.
        supervision.ensure_catalog(1, user_a["id"])
        visit = supervision.create_supervision(
            1,
            {
                "expediente_id": exp_a["id"],
                "tipo": "VISITA_CALIDAD",
                "modalidad": "EN_SITIO",
                "titulo": "Visita de calidad ficticia",
                "objetivo": "Verificar condiciones de calidad",
                "fecha_programada": date.today().isoformat(),
            },
            user_a,
        )
        require(len(visit["verificaciones"]) == 14, "La lista de verificación inicial debe contener 14 criterios")
        first_check = visit["verificaciones"][0]
        supervision.update_verification(
            1,
            first_check["id"],
            {"resultado": "NO_CUMPLE", "nivel_riesgo": "ALTO", "observaciones": "Soporte pendiente"},
            user_a,
        )
        finding = supervision.create_finding(
            1,
            {
                "supervision_id": visit["id"],
                "verificacion_id": first_check["id"],
                "titulo": "Hallazgo ficticio",
                "descripcion": "Debe completarse la evidencia",
                "nivel_riesgo": "ALTO",
                "fecha_limite": (date.today() + timedelta(days=5)).isoformat(),
            },
            user_a,
        )
        expect_error(
            lambda: supervision.update_finding(1, finding["id"], {"estado": "CERRADO", "motivo_cierre": "Intento prematuro"}, user_a, allow_close=True),
            "plan de mejora",
        )
        plan = supervision.create_plan(
            1,
            {
                "hallazgo_id": finding["id"],
                "nombre": "Plan ficticio",
                "objetivo": "Completar evidencia",
                "fecha_limite": (date.today() + timedelta(days=10)).isoformat(),
            },
            user_a,
        )
        action = supervision.create_action(
            1,
            plan["id"],
            {
                "titulo": "Adjuntar evidencia ficticia",
                "descripcion": "Recopilar soporte",
                "fecha_limite": (date.today() + timedelta(days=3)).isoformat(),
                "evidencia_requerida": False,
            },
            user_a,
        )
        action = supervision.update_action(
            1,
            action["id"],
            {"estado": "COMPLETADA", "progreso": 100, "resultado": "Soporte revisado"},
            user_a,
            allow_validate=True,
        )
        require(action["estado"] == "COMPLETADA", "La acción no fue validada")
        supervision.add_followup(1, "PLAN", plan["id"], {"descripcion": "Seguimiento de prueba", "resultado": "Acción verificada"}, user_a)
        plan = supervision.update_plan(1, plan["id"], {"estado": "CERRADO"}, user_a, allow_review=True)
        require(plan["estado"] == "CERRADO", "El plan no cerró")
        finding = supervision.update_finding(
            1,
            finding["id"],
            {"estado": "CERRADO", "motivo_cierre": "Validación humana con soporte"},
            user_a,
            allow_close=True,
        )
        require(finding["estado"] == "CERRADO", "El hallazgo no cerró de forma explícita")

        current_visit = supervision.supervision(1, visit["id"])
        for check in current_visit["verificaciones"]:
            supervision.update_verification(1, check["id"], {"resultado": "CUMPLE", "observaciones": "Verificado"}, user_a)
        closed_visit = supervision.update_supervision(
            1,
            visit["id"],
            {"estado": "CERRADA", "resultado_general": "Revisión finalizada"},
            user_a,
            allow_close=True,
        )
        require(closed_visit["estado"] == "CERRADA", "La supervisión no cerró")
        products = supervision.build_products(1, visit["id"], user_a)
        require({row["tipo_producto"] for row in products} == {"MATRIZ_EXCEL", "INFORME_PDF", "PAQUETE_ZIP"}, "Productos de supervisión incompletos")
        for product in products:
            found = supervision.product_path(1, product["id"])
            require(found and found[0].is_file() and found[0].stat().st_size > 0, "Producto de supervisión no verificable")

        # Motor idempotente, integración por UCA y aislamiento por tenant.
        first_motor = motor.synchronize(1, user_a)
        second_motor = motor.synchronize(1, user_a)
        require(second_motor["creadas"] == 0, "La segunda sincronización del Motor creó duplicados")
        require(first_motor["fuentes_leidas"] >= 1, "El Motor no encontró fuentes operativas")

        view = giu.integrated_view(1, exp_a["id"])
        codes = {row["codigo"] for row in view["componentes"]}
        require({"familias_redes", "supervision_calidad", "planeacion_operativa", "psicosocial"} <= codes and len(codes) == 12, "La vista UCA no integra los dominios actuales")
        require(any(row.get("source_table") == "fcr_alertas" for row in view["alertas"]), "No se integraron las alertas familiares")
        require(any(str(row.get("source_table") or "").startswith("csc_") for row in view["cronograma"]), "No se integró el cronograma de supervisión")
        document_links = giu.list_document_links(1, exp_a["id"])
        require(any(row.get("source_module") == "familias-redes" for row in document_links), "No se vincularon documentos de Familias/Redes")
        require(any(row.get("source_module") == "supervision-calidad" for row in document_links), "No se vincularon productos de Supervisión")

        require(not familias.list_family_records(2, {"unidad": exp_a["unidad_nombre"]}), "Se cruzaron familias entre fundaciones")
        require(not supervision.list_supervisions(2, {"unidad": exp_a["unidad_nombre"]}), "Se cruzaron supervisiones entre fundaciones")

        conn = sqlite3.connect(database)
        duplicate_sources = conn.execute(
            """SELECT fuente_tabla,fuente_clave,COUNT(*) n
                 FROM mgp_tareas WHERE fundacion_id=1 AND (fuente_tabla LIKE 'fcr_%' OR fuente_tabla LIKE 'csc_%')
                 GROUP BY fuente_tabla,fuente_clave HAVING COUNT(*)>1"""
        ).fetchall()
        source_counts = dict(
            conn.execute(
                "SELECT CASE WHEN fuente_tabla LIKE 'fcr_%' THEN 'fcr' ELSE 'csc' END grupo,COUNT(*) FROM mgp_tareas WHERE fundacion_id=1 AND (fuente_tabla LIKE 'fcr_%' OR fuente_tabla LIKE 'csc_%') GROUP BY grupo"
            ).fetchall()
        )
        conn.close()
        require(not duplicate_sources, "El Motor contiene tareas duplicadas de FCR/CSC")
        require(source_counts.get("fcr", 0) > 0 and source_counts.get("csc", 0) > 0, "Faltan tareas FCR o CSC en el Motor")

    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    family_js = (ROOT / "frontend" / "js" / "modules" / "familias-redes.js").read_text(encoding="utf-8")
    supervision_js = (ROOT / "frontend" / "js" / "modules" / "supervision-calidad.js").read_text(encoding="utf-8")
    routes_family = (BACKEND / "modules" / "familias_redes" / "routes.py").read_text(encoding="utf-8")
    require("familias-redes" in html and "supervision-calidad" in html, "Faltan las nuevas secciones en la SPA")
    require("prepareDocs" in family_js and "prepareReport" in family_js, "Interfaz de Familias/Redes incompleta")
    require("prepareProducts" in supervision_js and "createPlan" in supervision_js, "Interfaz de Supervisión incompleta")
    require("return []" in routes_family and "No tienes permiso sobre esta UCA" in routes_family, "El acceso por UCA no es fail-closed")

    print(json.dumps({
        "ok": True,
        "version": "2.5.4-supervision-familias-redes",
        "fcr_schema": FCR_SCHEMA_VERSION,
        "csc_schema": CSC_SCHEMA_VERSION,
        "pruebas": [
            "expedientes familiares idempotentes",
            "acta y listado automáticos en borrador",
            "compromisos y alertas con cierre humano",
            "redes y evidencias",
            "checklist, hallazgos, planes y acciones",
            "productos XLSX/PDF/ZIP con integridad",
            "Motor idempotente",
            "Expediente UCA con doce dominios",
            "aislamiento multi-fundación",
        ],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    run()
