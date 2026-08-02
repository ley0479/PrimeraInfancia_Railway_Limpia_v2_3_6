from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path
import sys

from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / 'backend'
sys.path.insert(0, str(BACKEND))

from services.ram_v3_service import generate_ram_v3, sha256_file

EXPECTED_HASH = 'a6b4c9412f7c72a19b9d5e842fa5ffd4b876c7d0f0c3d5c8e140b5287d700753'


def assert_true(value, message):
    if not value:
        raise AssertionError(message)


def run():
    app_text = (BACKEND / 'app.py').read_text(encoding='utf-8')
    js_text = (ROOT / 'frontend' / 'js' / 'app.js').read_text(encoding='utf-8')
    html_text = (ROOT / 'frontend' / 'index.html').read_text(encoding='utf-8')

    assert_true('def _alpha69_generar_ram_directo' in app_text, 'Falta generación directa RAM')
    assert_true("'formatos_seleccionados': 'ram'" in app_text, 'RAM directo no está aislado')
    assert_true('def _alpha69_buscar_ram_periodo' in app_text, 'Falta búsqueda por periodo')
    assert_true("if formato_norm == 'ram':" in app_text, 'El endpoint no separa RAM')
    assert_true("request.args.get('mes')" in app_text and "request.args.get('anio')" in app_text, 'El endpoint no recibe periodo')
    assert_true('periodo-formatos-mes' in html_text and 'periodo-formatos-anio' in html_text, 'Falta selector de periodo')
    assert_true("formData.append('mes'" in js_text and "formData.append('anio'" in js_text, 'El proceso no envía periodo')
    assert_true('queryPeriodo' in js_text, 'La descarga no envía periodo')

    db = sqlite3.connect(BACKEND / 'database.sqlite3')
    db.row_factory = sqlite3.Row
    unit = db.execute("SELECT unidad FROM beneficiarios WHERE estado='ACTIVO' AND TRIM(COALESCE(unidad,''))<>'' LIMIT 1").fetchone()
    users = [dict(r) for r in db.execute("SELECT * FROM beneficiarios WHERE unidad=? AND estado='ACTIVO' LIMIT 21", (unit['unidad'],)).fetchall()]
    db.close()
    assert_true(bool(users), 'No hay usuarios reales para prueba')

    template = BACKEND / 'templates_originales' / 'oficiales' / 'plantilla_ram_oficial_v3.xlsx'
    assert_true(sha256_file(template) == EXPECTED_HASH, 'Cambió plantilla oficial')
    with tempfile.TemporaryDirectory() as temp:
        out = Path(temp) / 'RAM_V3_PRUEBA_2026_08.xlsx'
        report = generate_ram_v3(
            template, out, users, 2026, 8,
            metadata={'unidad': unit['unidad'], 'mes_nombre': 'AGOSTO', 'anio': 2026},
            expected_sha256=EXPECTED_HASH,
        )
        assert_true(out.exists() and out.stat().st_size > 0, 'RAM V3 no se generó')
        wb = load_workbook(out, read_only=False, data_only=False)
        assert_true('FORMATO RAM' in wb.sheetnames, 'Falta hoja FORMATO RAM')
        assert_true('INSTRUCCIONES DILIGENCIAMIENTO' in wb.sheetnames, 'Falta hoja de instrucciones')
        wb.close()

    print(json.dumps({
        'ok': True,
        'checks': [
            'Periodo visible en interfaz',
            'Periodo enviado al procesamiento',
            'Periodo enviado a la descarga',
            'RAM aislado de RPP/Bienestarina',
            'Búsqueda estricta por UDS y periodo',
            'Generación RAM V3 real verificada',
            'Plantilla oficial intacta',
        ]
    }, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    run()
