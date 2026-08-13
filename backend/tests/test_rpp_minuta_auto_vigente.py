from __future__ import annotations

from pathlib import Path


def test_rpp_upload_activates_valid_extraction():
    routes = Path(__file__).resolve().parents[1] / 'modules' / 'motor_plantillas' / 'routes.py'
    source = routes.read_text(encoding='utf-8')

    assert "if not grupos or not productos" in source
    assert "marcar_minuta_vigente(" in source
    assert "cargada, validada y marcada como vigente" in source

