from pathlib import Path
import tempfile
import sys

ROOT=Path(__file__).resolve().parents[2]; sys.path.insert(0,str(ROOT/'backend'))
from modules.integrity_stability.service import IntegrityStabilityService
from modules.dbapi_compat import sqlite3

def require(value,message):
    if not value: raise AssertionError(message)

with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
    db=str(Path(tmp)/'integrity.sqlite3')
    with sqlite3.connect(db) as conn:
        conn.execute('CREATE TABLE fundaciones(id INTEGER PRIMARY KEY)')
        conn.execute('CREATE TABLE roles_sistema(id INTEGER PRIMARY KEY)')
        conn.execute('CREATE TABLE usuarios_app(id INTEGER PRIMARY KEY,fundacion_id INTEGER,username TEXT,password_hash TEXT,rol TEXT,activo INTEGER)')
        conn.execute('CREATE TABLE sesiones_usuario(id INTEGER PRIMARY KEY,usuario_id INTEGER)')
        conn.execute('CREATE TABLE calendario_entregables(id INTEGER PRIMARY KEY,fundacion_id INTEGER)')
        conn.execute("INSERT INTO usuarios_app VALUES(1,1,'audit-user','hash-no-expuesto','SUPERADMIN',1)")
        conn.commit()
    service=IntegrityStabilityService(str(ROOT),tmp,db)
    report=service.central_diagnostic({'SECRET_KEY':'s'*40,'JWT_SECRET_KEY':'j'*40},mode='MANUAL')
    require(report['database_structure']['ok'],'Estructura mínima no validada')
    require(report['database_structure']['users']['total']==1,'Conteo agregado incorrecto')
    serialized=str(report)
    require('hash-no-expuesto' not in serialized and 'audit-user' not in serialized,'El reporte expuso credenciales o identidad')
    require(report['protection_policy']['automatic_mutation_allowed'] is False,'El diagnóstico permite mutar negocio')
    require((Path(tmp)/'integrity'/report['report_file']).is_file(),'No se generó reporte final')

routes=(ROOT/'backend/modules/integrity_stability/routes.py').read_text(encoding='utf-8')
for token in ['/diagnostic','/monitor','safe-repair']:
    require(token in routes,f'Falta endpoint {token}')
print('Motor Central de Integridad 2.7.0: PASS')
