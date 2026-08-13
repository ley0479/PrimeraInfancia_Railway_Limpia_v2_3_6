from pathlib import Path
import tempfile,sys
from flask import Flask,g
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'backend'))
from database import database
from modules.sqlalchemy_compat import CoreConnection
from modules.gerencia_general.services import GerenciaGeneralService

with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
    db=Path(tmp)/'bi.sqlite3';app=Flask(__name__);app.secret_key='test'
    app.config.update(DATABASE_URL=f'sqlite:///{db.as_posix()}',DATABASE_PATH=str(db),SQLALCHEMY_ENGINE_OPTIONS={})
    database.configure(app);service=GerenciaGeneralService(str(db),tmp);service.init_schema();conn=CoreConnection()
    conn.executescript("""
    CREATE TABLE af_presupuestos(id INTEGER PRIMARY KEY,fundacion_id INTEGER,vigencia TEXT,valor_aprobado REAL,valor_modificado REAL);
    CREATE TABLE af_movimientos(id INTEGER PRIMARY KEY,fundacion_id INTEGER,presupuesto_id INTEGER,tipo TEXT,fecha TEXT,valor REAL);
    CREATE TABLE th_personas(id INTEGER PRIMARY KEY,fundacion_id INTEGER,activo INTEGER);
    CREATE TABLE th_documentos(id INTEGER PRIMARY KEY,fundacion_id INTEGER,fecha_vencimiento TEXT,estado TEXT);
    CREATE TABLE aep_activos(id INTEGER PRIMARY KEY,fundacion_id INTEGER,activo INTEGER,estado TEXT,unidad_nombre TEXT);
    CREATE TABLE aep_mantenimientos(id INTEGER PRIMARY KEY,fundacion_id INTEGER,estado TEXT,fecha_programada TEXT,unidad_nombre TEXT);
    CREATE TABLE csc_hallazgos(id INTEGER PRIMARY KEY,fundacion_id INTEGER,activa INTEGER,estado TEXT,unidad_nombre TEXT);
    INSERT INTO af_presupuestos VALUES(1,1,'2026',1000,0);
    INSERT INTO af_movimientos VALUES(1,1,1,'COMPROMISO','2026-08-01',400);
    INSERT INTO th_personas VALUES(1,1,1);
    INSERT INTO aep_activos VALUES(1,1,1,'MALO','UCA QA');
    INSERT INTO csc_hallazgos VALUES(1,1,1,'ABIERTO','UCA QA');
    """);conn.commit();conn.close()
    with app.test_request_context('/'):
        g.current_user={'id':1,'rol':'GERENTE','fundacion_id':1,'username':'qa'}
        c=service.connect();bi=service.inteligencia_negocio(c.cursor(),'2026-08',{});c.close()
        assert bi['indicadores']['presupuesto']==1000
        assert bi['indicadores']['ejecutado']==400
        assert bi['indicadores']['ambientes_criticos']==1
        assert bi['indicadores']['hallazgos_abiertos']==1
        assert bi['interpretacion'].startswith('Análisis descriptivo')

routes=(ROOT/'backend/modules/gerencia_general/routes.py').read_text(encoding='utf-8')
html=(ROOT/'frontend/index.html').read_text(encoding='utf-8')
assert '/inteligencia-negocio' in routes and 'gg-bi-semaforos' in html
print('Gerencia BI 2.7.0: PASS')
