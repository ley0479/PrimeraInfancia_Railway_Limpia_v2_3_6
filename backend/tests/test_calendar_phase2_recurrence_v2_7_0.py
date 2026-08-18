#!/usr/bin/env python3
"""Pruebas Fase 2: recurrencias finitas, rol y aislamiento tenant."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from modules.calendario_inteligente.repository import CalendarioInteligenteRepository  # noqa: E402
from modules.calendario_inteligente.services import fechas_recurrentes  # noqa: E402
from modules.seguridad.tenant_context import tenant_context  # noqa: E402


def require(value, message: str) -> None:
    if not value:
        raise AssertionError(message)


def require_error(callback, message: str) -> None:
    try:
        callback()
    except ValueError:
        return
    raise AssertionError(message)


def run() -> None:
    require(fechas_recurrentes("2026-01-31", "mensual", "2026-04-30") == [
        "2026-01-31", "2026-02-28", "2026-03-31", "2026-04-30",
    ], "La recurrencia mensual no conserva correctamente el día ancla")
    require(fechas_recurrentes("2026-08-03", "semanal", "2026-08-31", 2) == [
        "2026-08-03", "2026-08-17", "2026-08-31",
    ], "El intervalo semanal es incorrecto")
    require_error(lambda: fechas_recurrentes("2026-08-03", "semanal"), "Se inventó una fecha final")
    require_error(lambda: fechas_recurrentes("2026-08-03", "diaria", "2028-08-03"), "No se aplicó el límite de instancias")

    with tempfile.TemporaryDirectory(prefix="pi-calendar-phase2-") as temp:
        root = Path(temp)
        repo = CalendarioInteligenteRepository(str(root / "db.sqlite3"), str(root / "uploads"))
        repo.init_schema(force=True)
        with tenant_context(1, role="COORDINADOR", username="coord"):
            rows = repo.create_recurrentes({
                "titulo": "Seguimiento quincenal",
                "fecha_limite": "2026-08-03",
                "recurrencia": "semanal",
                "recurrencia_intervalo": 2,
                "recurrencia_hasta": "2026-08-31",
                "responsable_id": 9,
                "responsable_nombre": "Docente Uno",
                "responsable_rol": "DOCENTE",
                "unidad": "UDS A",
            })
            require(len(rows) == 3, "La serie no creó tres instancias")
            require(len({row["serie_id"] for row in rows}) == 1, "Las instancias no comparten serie")
            require([row["instancia_numero"] for row in rows] == [1, 2, 3], "Numeración de serie incorrecta")
            require(all(row["responsable_rol"] == "DOCENTE" for row in rows), "Se perdió el rol responsable")
        with tenant_context(2, role="COORDINADOR", username="coord"):
            require(not repo.list_entregables({"anio": "2026"}), "La serie cruzó el aislamiento tenant")

    frontend = (ROOT / "frontend" / "js" / "modules" / "calendario-inteligente.js").read_text(encoding="utf-8")
    require("ci-new-recurrencia" in frontend and "ci-new-responsable-rol" in frontend, "Faltan controles Fase 2")
    print("PASS test_calendar_phase2_recurrence_v2_7_0")


if __name__ == "__main__":
    run()
