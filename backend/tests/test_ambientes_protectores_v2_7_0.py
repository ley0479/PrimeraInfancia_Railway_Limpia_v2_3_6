from pathlib import Path
import tempfile

from modules.supervision_calidad.repository import CentroSupervisionRepository
from modules.ambientes_protectores.repository import AmbientesRepository


def test_ambientes_inventario_mantenimiento_y_tenant():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        root=Path(tmp); db=str(root/'test.sqlite3')
        CentroSupervisionRepository(db,str(root/'data'),str(root/'out')).init_schema()
        repo=AmbientesRepository(db,str(root/'data'),str(root/'out')); repo.init_schema()
        with repo.connect() as conn:
            conn.execute("CREATE TABLE calendario_entregables(id INTEGER PRIMARY KEY AUTOINCREMENT,titulo TEXT,descripcion TEXT,fecha_inicio TEXT,fecha_limite TEXT,modulo TEXT,tipo_formato TEXT,responsable_id INTEGER,responsable_nombre TEXT,unidad TEXT,estado TEXT,prioridad TEXT,requiere_evidencia INTEGER,creado_por TEXT,fecha_creacion TEXT,actualizado_en TEXT,fundacion_id INTEGER,usuario_creador_id INTEGER,clave_unica TEXT UNIQUE,origen TEXT)")
        admin={'id':1,'username':'admin'}
        asset=repo.save_asset(1,{'unidad_nombre':'UCA Norte','nombre':'Extintor','categoria':'GESTION_RIESGO','cantidad':2,'estado':'BUENO'},admin)
        assert asset['fundacion_id']==1 and asset['unidad_clave']=='UCA_NORTE'
        maintenance=repo.create_maintenance(1,{'unidad_nombre':'UCA Norte','activo_id':asset['id'],'titulo':'Recarga anual','fecha_programada':'2027-01-15','prioridad':'ALTA'},admin)
        assert maintenance['estado']=='PROGRAMADO' and maintenance['calendario_entregable_id']
        assert repo.dashboard(1)['resumen']['activos']==1
        assert repo.dashboard(2)['resumen']['activos']==0


def test_cierre_requiere_validacion():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        root=Path(tmp); db=str(root/'test.sqlite3')
        CentroSupervisionRepository(db,str(root/'data'),str(root/'out')).init_schema()
        repo=AmbientesRepository(db,str(root/'data'),str(root/'out')); repo.init_schema()
        user={'id':2,'username':'operador'}
        row=repo.create_maintenance(1,{'unidad_nombre':'UCA Sur','titulo':'Reparar cubierta','fecha_programada':'2027-02-01'},user)
        try:
            repo.update_maintenance(1,row['id'],{'estado':'EJECUTADO','resultado':'Finalizado'},user,False)
            assert False, 'El cierre operativo no fue bloqueado'
        except PermissionError:
            pass
        closed=repo.update_maintenance(1,row['id'],{'estado':'EJECUTADO','resultado':'Validado'},user,True)
        assert closed['estado']=='EJECUTADO' and closed['validado_por']==2


def test_spa_y_registro_estan_conectados():
    root=Path(__file__).resolve().parents[2]
    html=(root/'frontend'/'index.html').read_text(encoding='utf-8')
    app=(root/'backend'/'app.py').read_text(encoding='utf-8')
    security=(root/'backend'/'modules'/'seguridad'/'services.py').read_text(encoding='utf-8')
    assert 'ambientes-protectores.js' in html and 'id="ambientes-protectores"' in html
    assert 'register_ambientes_protectores' in app
    assert '/api/ambientes-protectores' in security
