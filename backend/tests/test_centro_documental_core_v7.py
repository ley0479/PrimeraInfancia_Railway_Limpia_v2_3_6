from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from migrations.migrate_centro_documental_v7 import migrate
from modules.centro_documental.narrative_service import assemble_narrative
from modules.centro_documental.theme_generation_service import generate_planning
from modules.centro_documental.validators import validate_special_state


def run() -> None:
    with tempfile.TemporaryDirectory() as folder:
        database = os.path.join(folder, "documents.sqlite")
        result = migrate(database)
        assert result["documents_schema_version"] == "1"
        result_second = migrate(database)
        assert result_second["ok"] is True
        connection = sqlite3.connect(database)
        names = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        connection.close()
        required = {"doc_plantillas", "doc_plantilla_versiones", "doc_mapeos", "doc_instancias", "doc_evidencias", "doc_auditoria"}
        assert required.issubset(names)

    planning = generate_planning("Vínculos afectivos mediante el juego", "PEDAGOGICO")
    assert planning["clasificacion"] == "PLANEADO"
    assert "Vínculos afectivos" in planning["objetivo"]

    try:
        validate_special_state("NO_APLICA", "")
        raise AssertionError("NO_APLICA sin justificación no debe aceptarse")
    except ValueError:
        pass
    validate_special_state("NO_APLICA", "La actividad no aplica al grupo seleccionado")

    narrative = assemble_narrative([
        {"categoria": "PARTICIPACION", "codigo": "ACTIVA", "texto": "La familia participó activamente"},
        {"categoria": "LOGRO", "codigo": "OBJETIVO_COMPLETO", "texto": "Se cumplió el objetivo planteado"},
    ])
    assert narrative["editable"] is True and narrative["estado"] == "BORRADOR_GENERADO"

    try:
        assemble_narrative([
            {"categoria": "DIFICULTAD", "codigo": "SIN_DIFICULTADES", "texto": "No se presentaron dificultades"},
            {"categoria": "DIFICULTAD", "codigo": "BAJA_PARTICIPACION", "texto": "Hubo baja participación"},
        ])
        raise AssertionError("La contradicción debe bloquear el borrador")
    except ValueError:
        pass

    print("PASS test_centro_documental_core_v7")


if __name__ == "__main__":
    run()
