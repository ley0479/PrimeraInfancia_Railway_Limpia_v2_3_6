#!/usr/bin/env python3
"""Fases 9-10: integración formato/evidencia y alertas idempotentes."""
from __future__ import annotations
import sys,tempfile
from datetime import date,timedelta
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'backend'))
from modules.calendario_inteligente.repository import CalendarioInteligenteRepository
from modules.seguridad.tenant_context import tenant_context
def req(ok,msg):
    if not ok:raise AssertionError(msg)
def run():
    with tempfile.TemporaryDirectory(prefix='pi-phase10-') as td:
        repo=CalendarioInteligenteRepository(str(Path(td)/'db.sqlite3'),str(Path(td)/'uploads'));repo.init_schema(force=True)
        with tenant_context(1,role='COORDINADOR',username='coord'):
            due=(date.today()+timedelta(days=5)).isoformat()
            event=repo.create_entregable({'titulo':'Entrega RAM','fecha_limite':due,'modulo':'RAM/RAN/Asistencia','unidad':'UDS A','responsable_id':7})
            first=repo.alertas([event]);second=repo.alertas([event])
            with repo.connect() as conn:
                count=conn.execute('SELECT COUNT(*) n FROM calendario_alertas WHERE fundacion_id=1 AND entregable_id=?',(event['id'],)).fetchone()['n']
            req(count==5,'Alertas duplicadas al recalcular dashboard')
            req(len(first)==len(second)==1 and first[0]['tipo']=='VENCE_5_DIAS','Recordatorio programado incorrecto')
        with tenant_context(2,role='COORDINADOR',username='coord'):
            req(not repo.alertas([]),'Alertas cruzaron tenants')
    js=(ROOT/'frontend/js/modules/calendario-inteligente.js').read_text(encoding='utf-8')
    req('Generar listado RAM' in js and 'ciAbrirEvidencias' in js and 'ciRevisarEvidencias' in js,'Flujo formato-evidencia-revisión incompleto')
    print('PASS test_calendar_phase9_10_integration_alerts_v2_7_0')
if __name__=='__main__':run()
