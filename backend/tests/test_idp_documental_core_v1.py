from __future__ import annotations

from pathlib import Path
import tempfile

from openpyxl import Workbook
from PIL import Image

from modules.idp_documental.repository import IDPRepository
from modules.idp_documental.services import canonicalize, classify_document, read_document, sha256_file


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def create(repo, tenant, path, user=10):
    digest=sha256_file(path)
    document_id=repo.create_document({'fundacion_id':tenant,'nombre_original':path.name,'nombre_guardado':path.name,'ruta_privada':str(path),'extension':path.suffix,'mime_type':'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet','tamano_bytes':path.stat().st_size,'sha256':digest,'usuario_id':user})
    raw=read_document(path); classification=classify_document(raw.get('texto') or '',path.name); canonical,fields=canonicalize(raw,classification[0])
    canonical['fundacion']['id']=tenant
    repo.complete_extraction(document_id,tenant,raw,canonical,fields,classification,user)
    return document_id,digest


def main():
    with tempfile.TemporaryDirectory() as temporary:
        root=Path(temporary); db=root/'idp.sqlite3'; book=root/'LISTADO_ASISTENCIA.xlsx'
        wb=Workbook(); ws=wb.active; ws.title='ASISTENCIA'; ws.append(['LISTADO DE ASISTENCIA']); ws.append(['Nombre completo','Documento','UDS','Asistió','Firma']); ws.append(['ANA PEREZ','1001','UCA 1','SI','X']); ws.append(['LUIS DIAZ','1002','UCA 1','NO','']); wb.save(book)
        repo=IDPRepository(str(db)); document_id,digest=create(repo,1,book)
        item=repo.get_document(document_id,1)
        require(item and item['tipo_documento']=='LISTADO_ASISTENCIA','No clasifico asistencia')
        require(item['estado']=='REQUIERE_REVISION','Estado incorrecto')
        require(len(item['resultado_canonico']['participantes'])==2,'No extrajo participantes')
        require(item['resultado_canonico']['participantes'][0]['documento']=='1001','Documento mal mapeado')
        require(repo.get_document(document_id,2) is None,'Fallo aislamiento por fundacion')
        require(repo.find_duplicate(1,digest)['id']==document_id,'No detecto duplicado del tenant')
        require(repo.find_duplicate(2,digest) is None,'Bloqueo incorrectamente el mismo archivo en otro tenant')
        name_field=next(field for field in item['campos'] if field['ruta_canonica']=='participantes.0.nombre_completo')
        repo.correct_field(document_id,name_field['id'],1,'ANA MARIA PEREZ',10,'Correccion contra original')
        corrected=repo.get_document(document_id,1)
        require(corrected['resultado_canonico']['participantes'][0]['nombre_completo']=='ANA MARIA PEREZ','Correccion no actualizo canonico')
        repo.approve(document_id,1,10)
        approved=repo.get_document(document_id,1)
        require(approved['estado']=='APROBADO' and approved['progreso']==100,'No aprobo documento revisado')
        require(any(event['evento']=='CAMPO_CORREGIDO' for event in approved['eventos']),'No audito correccion')
        require(any(event['evento']=='DOCUMENTO_APROBADO' for event in approved['eventos']),'No audito aprobacion')
        image_path=root/'foto_asistencia.jpg'; Image.new('RGB',(1200,1600),'white').save(image_path)
        image_id,_=create(repo,1,image_path)
        image_doc=repo.get_document(image_id,1)
        require(image_doc['estado']=='REQUIERE_OCR','La imagen no quedo pendiente de OCR')
        blocked=False
        try: repo.approve(image_id,1,10)
        except ValueError: blocked=True
        require(blocked,'Permitio aprobar una imagen sin OCR')
        print('IDP core PASS: clasificacion, canonico, tenant, duplicado, correccion y aprobacion')


if __name__=='__main__':
    main()
