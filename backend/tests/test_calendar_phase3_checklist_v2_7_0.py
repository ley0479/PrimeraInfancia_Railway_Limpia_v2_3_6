#!/usr/bin/env python3
"""Fase 3: obligaciones, requisitos, asignación, NO APLICA y cumplimiento."""
from __future__ import annotations
import sys, tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]; BACKEND=ROOT/'backend'; sys.path.insert(0,str(BACKEND))
from modules.calendario_inteligente.repository import CalendarioInteligenteRepository
from modules.seguridad.tenant_context import tenant_context

def req(ok,msg):
    if not ok: raise AssertionError(msg)

def run():
    with tempfile.TemporaryDirectory(prefix='pi-phase3-') as td:
        repo=CalendarioInteligenteRepository(str(Path(td)/'db.sqlite3'),str(Path(td)/'uploads')); repo.init_schema(force=True)
        coord={'id':1,'username':'coord','rol':'COORDINADOR'}
        with tenant_context(1,role='COORDINADOR',username='coord'):
            first=repo.create_obligacion({'componente':'PEDAGOGICO','numero':'1','titulo':'Encuentro con el entorno','periodo':'2026-08','unidad':'UDS A','responsable_rol':'DOCENTE','responsable_id':10,'responsable_nombre':'Ana','requisitos':[{'nombre':'RAM'},{'nombre':'Listado'},{'nombre':'Fotos'}]},coord)
            second=repo.create_obligacion({'componente':'SALUD','numero':'2','titulo':'Seguimiento condicional','periodo':'2026-08','unidad':'UDS A','responsable_rol':'NUTRICIONISTA','requisitos':['Informe']},coord)
            req(len(first['requisitos'])==3,'No conserva requisitos múltiples')
            repo.update_asignacion_estado(first['id'],'APROBADO','',coord)
            try: repo.update_asignacion_estado(second['id'],'NO_APLICA','',coord); raise AssertionError('Aceptó NO APLICA sin motivo')
            except ValueError: pass
            na=repo.update_asignacion_estado(second['id'],'NO_APLICA','No se presentaron casos',coord)
            req(na['justificacion_no_aplica']=='No se presentaron casos' and na['no_aplica_por']==1,'No auditó NO APLICA')
            result=repo.list_checklist('2026-08',coord)
            req(result['resumen']=={'total':2,'no_aplica':1,'exigibles':1,'aprobadas':1,'cumplimiento':100.0},'Fórmula de cumplimiento incorrecta')
        with tenant_context(2,role='COORDINADOR',username='coord'):
            req(not repo.list_checklist('2026-08',coord)['asignaciones'],'Checklist cruzó tenants')
    js=(ROOT/'frontend/js/modules/calendario-inteligente.js').read_text(encoding='utf-8')
    req('ci-checklist-list' in js and 'ciNoAplica' in js,'Falta interfaz de checklist')
    print('PASS test_calendar_phase3_checklist_v2_7_0')
if __name__=='__main__': run()
