#!/usr/bin/env python3
"""Fases 7-8: motor RAM oficial versionado y acción transversal en calendario."""
from __future__ import annotations
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def req(ok,msg):
    if not ok: raise AssertionError(msg)
def run():
    manifest=json.loads((ROOT/'backend/seed_data/templates_originales/oficiales/templates_manifest.json').read_text(encoding='utf-8'))
    ram=manifest['ram']; template=ROOT/'backend/seed_data/templates_originales/oficiales'/ram['archivo']
    digest=hashlib.sha256(template.read_bytes()).hexdigest()
    req(digest==ram['hash_sha256'],'Hash RAM activo no coincide con la plantilla real')
    req(ram['codigo']=='F27.MT1.PP' and ram['version']=='3' and ram['capacidad_por_pagina']==20,'Registro/versionado RAM incompleto')
    js=(ROOT/'frontend/js/modules/calendario-inteligente.js').read_text(encoding='utf-8')
    req('Generar listado RAM' in js and '/api/descargar/${encodeURIComponent(unidad)}/ram' in js,'Calendario no reutiliza el generador RAM existente')
    audit=(ROOT/'docs/AUDITORIA_PLANTILLA_RAM_V3.md').read_text(encoding='utf-8')
    for cell in ('A4','F7','A15:A34','AI35','AK15:AK34'):
        req(cell in audit,f'Falta documentar coordenada RAM {cell}')
    print('PASS test_calendar_phase7_8_ram_wiring_v2_7_0')
if __name__=='__main__': run()
