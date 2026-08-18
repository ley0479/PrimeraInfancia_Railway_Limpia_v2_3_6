#!/usr/bin/env python3
"""Fase 11: indicadores reales por UDS, responsable, rol y componente."""
from __future__ import annotations
import sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'backend'))
from modules.calendario_inteligente.repository import CalendarioInteligenteRepository
from modules.seguridad.tenant_context import tenant_context
def req(ok,msg):
    if not ok:raise AssertionError(msg)
def run():
    with tempfile.TemporaryDirectory(prefix='pi-phase11-') as td:
        repo=CalendarioInteligenteRepository(str(Path(td)/'db.sqlite3'),str(Path(td)/'uploads'));repo.init_schema(force=True)
        user={'id':1,'username':'coord','rol':'COORDINADOR'}
        with tenant_context(1,role='COORDINADOR',username='coord'):
            items=[]
            for uds,comp,role in [('UDS A','PEDAGÓGICO','DOCENTE'),('UDS A','SALUD','NUTRICIONISTA'),('UDS B','PEDAGÓGICO','DOCENTE')]:
                items.append(repo.create_obligacion({'componente':comp,'titulo':f'Obligación {len(items)+1}','periodo':'2026-08','unidad':uds,'responsable_rol':role,'responsable_nombre':'Ana','requisitos':['Acta']},user))
            repo.update_asignacion_estado(items[0]['id'],'APROBADO','',user)
            repo.update_asignacion_estado(items[1]['id'],'NO_APLICA','No hubo caso',user)
            board=repo.tablero_cumplimiento('2026-08')
            req(board['resumen']=={'total':3,'exigibles':2,'aprobadas':1,'no_aplica':1,'cumplimiento':50.0},'Fórmula general incorrecta')
            uds_a=next(x for x in board['por_uds'] if x['nombre']=='UDS A')
            req(uds_a['cumplimiento']==100.0 and uds_a['no_aplica']==1,'Cálculo UDS incorrecto')
            req(board['por_rol'] and board['por_componente'] and board['por_responsable'],'Faltan dimensiones')
        with tenant_context(2,role='COORDINADOR',username='coord'):
            req(repo.tablero_cumplimiento('2026-08')['resumen']['total']==0,'Tablero cruzó tenants')
    print('PASS test_calendar_phase11_compliance_v2_7_0')
if __name__=='__main__':run()
