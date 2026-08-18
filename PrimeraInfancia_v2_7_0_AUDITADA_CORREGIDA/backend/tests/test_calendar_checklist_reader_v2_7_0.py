#!/usr/bin/env python3
"""Regresión del lector Word de checklist y aislamiento del calendario."""
from __future__ import annotations

import tempfile
import sys
from pathlib import Path

from docx import Document

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from modules.calendario_inteligente.repository import CalendarioInteligenteRepository  # noqa: E402
from modules.seguridad.tenant_context import tenant_context  # noqa: E402


def require(value, message: str) -> None:
    if not value:
        raise AssertionError(message)


def build_checklist(path: Path) -> None:
    doc = Document()
    table = doc.add_table(rows=4, cols=4)
    for idx, value in enumerate(["N°", "ACTIVIDAD", "TH A CARGO", "ENTREGA"]):
        table.rows[0].cells[idx].text = value
    for cell in table.rows[1].cells:
        cell.text = "COMPONENTE PEDAGÓGICO"
    values = [
        ["1", "Acta de planeación pedagógica", "Pedagogo y Psicosocial", "Acta\nListado de asistencia\nEvidencia fotográfica"],
        ["2", "Entrega de RPP", "Agente educativo", "RPP\nEvidencia fotográfica"],
    ]
    for row_index, row_values in enumerate(values, start=2):
        for col_index, value in enumerate(row_values):
            table.rows[row_index].cells[col_index].text = value
    doc.save(path)


def run() -> None:
    with tempfile.TemporaryDirectory(prefix="pi-checklist-") as tmp:
        root = Path(tmp)
        source = root / "lista_chequeo.docx"
        build_checklist(source)
        repo = CalendarioInteligenteRepository(str(root / "db.sqlite3"), str(root / "uploads"))
        repo.init_schema(force=True)

        with tenant_context(1, role="COORDINADOR", username="coord.a"):
            preview = repo.registrar_preview_cronograma(str(source), source.name, usuario="coord.a")
            activities = preview.get("actividades") or []
            require(len(activities) == 2, f"Se esperaban 2 actividades, se obtuvieron {len(activities)}")
            require(preview.get("requiere_revision") is True, "Una lista sin fechas debe exigir revisión")
            require(all(not item.get("ok") for item in activities), "No se deben inventar fechas")
            require(all(item.get("componente") == "COMPONENTE PEDAGÓGICO" for item in activities), "Se perdió el componente")
            require(any("Listado de asistencia" in item.get("entregables", "") for item in activities), "Se perdieron entregables")
            event_a = repo.create_entregable({"titulo": "RPP", "fecha_limite": "2026-08-10", "unidad": "UCA A", "modulo": "RPP"})

        with tenant_context(2, role="COORDINADOR", username="coord.b"):
            event_b = repo.create_entregable({"titulo": "RPP", "fecha_limite": "2026-08-10", "unidad": "UCA B", "modulo": "RPP"})
            require(repo.get_entregable(event_a["id"]) is None, "Tenant B pudo ver el evento de A")
            require(len(repo.list_entregables()) == 1, "Tenant B recibió eventos de otro tenant")

        with tenant_context(1, role="COORDINADOR", username="coord.a"):
            require(repo.get_entregable(event_b["id"]) is None, "Tenant A pudo ver el evento de B")
            require(repo.catalogos()["unidades"] == ["UCA A"], "Catálogos no están aislados")

    print("PASS test_calendar_checklist_reader_v2_7_0")


if __name__ == "__main__":
    run()
