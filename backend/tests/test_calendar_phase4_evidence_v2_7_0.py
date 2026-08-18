#!/usr/bin/env python3
"""Fase 4: evidencias seguras, versiones, revisión e aislamiento tenant."""
from __future__ import annotations

import io
import sys
import tempfile
from pathlib import Path

from werkzeug.datastructures import FileStorage

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from modules.calendario_inteligente.repository import CalendarioInteligenteRepository  # noqa: E402
from modules.seguridad.tenant_context import tenant_context  # noqa: E402


def require(value, message: str) -> None:
    if not value:
        raise AssertionError(message)


def upload(name: str, content: bytes, mime: str = "application/pdf") -> FileStorage:
    return FileStorage(stream=io.BytesIO(content), filename=name, content_type=mime)


def run() -> None:
    with tempfile.TemporaryDirectory(prefix="pi-phase4-") as temp:
        root = Path(temp)
        repo = CalendarioInteligenteRepository(str(root / "db.sqlite3"), str(root / "uploads"))
        repo.init_schema(force=True)
        user = {"id": 10, "username": "ana", "nombre_completo": "Ana Docente", "rol": "DOCENTE"}
        coord = {"id": 1, "username": "coord", "nombre_completo": "Coordinación", "rol": "COORDINADOR"}
        with tenant_context(1, role="COORDINADOR", username="coord"):
            item = repo.create_recurrentes({"titulo": "Acta mensual", "fecha_limite": "2026-08-20", "responsable_id": 10, "responsable_nombre": "Ana Docente"})[0]
            first = repo.add_evidencia("ENTREGABLE", item["id"], None, upload("Acta agosto.pdf", b"PDF-version-1"), "Original", user)
            second = repo.add_evidencia("ENTREGABLE", item["id"], None, upload("Acta agosto.pdf", b"PDF-version-2"), "Corrección", user)
            require((first["version"], second["version"]) == (1, 2), "No versionó el archivo original")
            require(first["sha256"] != second["sha256"] and len(first["sha256"]) == 64, "Hash de integridad inválido")
            require("ruta_archivo" not in repo.list_evidencias("ENTREGABLE", item["id"])[0], "Expuso ruta física al frontend")
            resolved = repo.evidencia_path(first["id"])
            require(resolved and resolved[0].is_file() and resolved[1] == "Acta agosto.pdf", "No resolvió descarga segura")
            repo.enviar_evidencias_revision("ENTREGABLE", item["id"])
            try:
                repo.revisar_evidencias("ENTREGABLE", item["id"], "DEVUELTA", "", coord)
                raise AssertionError("Permitió devolver sin observación")
            except ValueError:
                pass
            returned = repo.revisar_evidencias("ENTREGABLE", item["id"], "DEVUELTA", "Corregir firmas", coord)
            require(returned["actualizadas"] == 2 and repo.get_entregable(item["id"])["estado"] == "rechazado", "No registró devolución")
            repo.add_evidencia("ENTREGABLE", item["id"], None, upload("Acta agosto.pdf", b"PDF-version-3"), "Reentrega", user)
            approved = repo.revisar_evidencias("ENTREGABLE", item["id"], "APROBADA", "", coord)
            require(approved["actualizadas"] == 1 and repo.get_entregable(item["id"])["estado"] == "aprobado", "No aprobó la reentrega")
            try:
                repo.add_evidencia("ENTREGABLE", item["id"], None, upload("malware.exe", b"MZ", "application/x-msdownload"), "", user)
                raise AssertionError("Aceptó extensión peligrosa")
            except ValueError:
                pass
        with tenant_context(2, role="COORDINADOR", username="coord"):
            require(repo.get_evidencia(first["id"]) is None, "Una evidencia cruzó tenants")
            require(not repo.list_evidencias("ENTREGABLE", item["id"]), "El historial cruzó tenants")

    frontend = (ROOT / "frontend/js/modules/calendario-inteligente.js").read_text(encoding="utf-8")
    require("ciAbrirEvidencias" in frontend and "multiple" in frontend and "/revision" in frontend, "Falta interfaz completa de evidencias")
    print("PASS test_calendar_phase4_evidence_v2_7_0")


if __name__ == "__main__":
    run()
