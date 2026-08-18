#!/usr/bin/env python3
"""Fase 6: propuestas de checklist, fecha pendiente, confirmación y deduplicación."""
from __future__ import annotations
import sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]; sys.path.insert(0,str(ROOT/'backend'))
from modules.calendario_inteligente.repository import CalendarioInteligenteRepository
from modules.seguridad.tenant_context import tenant_context

def req(ok,msg):
    if not ok: raise AssertionError(msg)

def run():
    with tempfile.TemporaryDirectory(prefix='pi-phase6-') as td:
        repo=CalendarioInteligenteRepository(str(Path(td)/'db.sqlite3'),str(Path(td)/'uploads')); repo.init_schema(force=True)
        coord={'id':1,'username':'coord','rol':'COORDINADOR'}
        proposals=[{'componente':'PEDAGÓGICO','numero':'4','actividad':'Encuentro con el entorno','responsable_nombre':'Pedagogo / Psicosocial','entregables':'Acta\nListado de asistencia\nFotografías','fecha_sugerida':None}]
        with tenant_context(1,role='COORDINADOR',username='coord'):
            result=repo.confirmar_importacion_checklist(0,proposals,'2026-08',coord)
            req(result['creadas']==1,'No incorporó la propuesta confirmada')
            item=result['asignaciones'][0]
            req(item['fecha_sugerida'] is None and item['fecha_estado']=='PENDIENTE_ASIGNACION','Inventó fecha ausente')
            req(len(item['requisitos'])==3,'No separó los entregables detectados')
            repeated=repo.confirmar_importacion_checklist(0,proposals,'2026-08',coord)
            req(repeated['creadas']==0 and repeated['duplicadas_o_ignoradas']==1,'No deduplicó la obligación')
        with tenant_context(2,role='COORDINADOR',username='coord'):
            req(not repo.list_checklist('2026-08',coord)['asignaciones'],'Importación cruzó tenants')
    js=(ROOT/'frontend/js/modules/calendario-inteligente.js').read_text(encoding='utf-8')
    req('FECHA PENDIENTE DE ASIGNACIÓN' in js and 'ciConfirmarChecklistImportado' in js,'Falta revisión humana en interfaz')
    print('PASS test_calendar_phase6_checklist_import_v2_7_0')
if __name__=='__main__': run()
