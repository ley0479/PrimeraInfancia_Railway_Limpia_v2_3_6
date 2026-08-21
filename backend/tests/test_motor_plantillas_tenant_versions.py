from __future__ import annotations

from pathlib import Path
import tempfile

from modules.motor_plantillas.repository import MotorPlantillasRepository
from modules.motor_plantillas.services import connect, init_schema


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    with tempfile.TemporaryDirectory() as temporary:
        root=Path(temporary); db=root/'plantillas.sqlite3'; init_schema(str(db)); repo=MotorPlantillasRepository(str(db))
        def template(foundation: int, name: str) -> int:
            return repo.create_template({'nombre':name,'tipo':'RAM','ruta_archivo':str(root/f'{name}.xlsx'),'fundacion_id':foundation,'usuario_creador_id':foundation})
        old_id=template(1,'RAM F1 anterior'); new_id=template(1,'RAM F1 nueva'); other_id=template(2,'RAM F2')
        old_version=repo.create_template_version_record(old_id,{'version':'1','estado':'vigente'},{'fundacion_id':1,'usuario_id':11})
        new_version=repo.create_template_version_record(new_id,{'version':'2','estado':'borrador'},{'fundacion_id':1,'usuario_id':11})
        other_version=repo.create_template_version_record(other_id,{'version':'9','estado':'vigente'},{'fundacion_id':2,'usuario_id':22})
        repo.mark_version_vigente(new_version,{'fundacion_id':1,'usuario_id':11})
        conn=connect(str(db)); states={row['id']:(row['fundacion_id'],row['estado']) for row in conn.execute('SELECT id,fundacion_id,estado FROM plantillas_oficiales_versiones').fetchall()}; conn.close()
        require(states[old_version]==(1,'historico') and states[new_version]==(1,'vigente'),'No versiono correctamente dentro de la fundacion')
        require(states[other_version]==(2,'vigente'),'La publicacion altero la plantilla de otra fundacion')
        require(repo.get_template(other_id,1) is None,'Expuso plantilla base de otra fundacion')
        require([v['id'] for v in repo.list_versions('RAM',2)]==[other_version],'Mezclo versiones entre fundaciones')
        blocked=False
        try: repo.mark_version_vigente(other_version,{'fundacion_id':1,'usuario_id':11})
        except ValueError: blocked=True
        require(blocked,'Permitio publicar una version de otra fundacion')
        print('PASS test_motor_plantillas_tenant_versions')


if __name__=='__main__':
    main()
