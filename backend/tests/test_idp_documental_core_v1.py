from __future__ import annotations

from pathlib import Path
import tempfile
from unittest.mock import patch

from openpyxl import Workbook
from PIL import Image

from modules.idp_documental.repository import IDPRepository
from modules.idp_documental.services import attendance_official_payload, canonicalize, classify_document, connect, read_document, read_document_ocr, sha256_file


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
        repo=IDPRepository(str(db))
        conn=connect(str(db))
        conn.execute("CREATE TABLE master_ninos(id INTEGER PRIMARY KEY,documento TEXT,nombre_completo TEXT,unidad_servicio TEXT,estado TEXT,activo INTEGER,fundacion_id INTEGER)")
        conn.execute("INSERT INTO master_ninos VALUES(1,'1001','ANA PEREZ','UCA 1','ACTIVO',1,1)")
        conn.execute("INSERT INTO master_ninos VALUES(2,'1002','LUIS DIAZ','UCA 1','ACTIVO',1,1)")
        conn.execute("INSERT INTO master_ninos VALUES(3,'1001','OTRA FUNDACION','UCA X','ACTIVO',1,2)")
        conn.commit(); conn.close()
        document_id,digest=create(repo,1,book)
        item=repo.get_document(document_id,1)
        require(item and item['tipo_documento']=='LISTADO_ASISTENCIA','No clasifico asistencia')
        require(item['estado']=='REQUIERE_REVISION','Estado incorrecto')
        require(len(item['resultado_canonico']['participantes'])==2,'No extrajo participantes')
        require(item['resultado_canonico']['participantes'][0]['documento']=='1001','Documento mal mapeado')
        require(item['validaciones']['semaforo']=='VERDE','La planilla valida no quedo en verde')
        require(item['validaciones']['coincidencias']==2,'No valido los participantes contra Base Maestra')
        generation_blocked=False
        try: attendance_official_payload(item)
        except ValueError: generation_blocked=True
        require(generation_blocked,'Permitio generar formato oficial sin aprobacion')
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
        official_users,official_metadata=attendance_official_payload(approved)
        require(len(official_users)==2 and official_users[0]['documento']=='1001','No preparo usuarios para el listado oficial')
        require(official_metadata['unidad']=='UCA 1','No preparo la UDS para el listado oficial')
        require(any(event['evento']=='CAMPO_CORREGIDO' for event in approved['eventos']),'No audito correccion')
        require(any(event['evento']=='DOCUMENTO_APROBADO' for event in approved['eventos']),'No audito aprobacion')
        imported=repo.import_attendance(document_id,1,10,'2026-08-20','Encuentro educativo')
        require(imported['total_registros']==2 and not imported['ya_importado'],'No importo el lote de asistencia')
        imported_again=repo.import_attendance(document_id,1,10,'2026-08-20','Encuentro educativo')
        require(imported_again['ya_importado'],'No hizo idempotente la segunda importacion')
        imported_doc=repo.get_document(document_id,1)
        require(imported_doc['estado']=='IMPORTADO','No actualizo el estado importado')
        conn=connect(str(db)); imported_rows=conn.execute('SELECT asistio FROM idp_asistencias_importadas WHERE documento_id=? AND fundacion_id=? ORDER BY indice_participante',(document_id,1)).fetchall(); attendance_count=len(imported_rows); other_tenant_count=conn.execute('SELECT COUNT(*) total FROM idp_asistencias_importadas WHERE documento_id=? AND fundacion_id=?',(document_id,2)).fetchone()['total']; conn.close()
        require(attendance_count==2 and other_tenant_count==0,'Fallo persistencia o aislamiento del lote importado')
        require([row['asistio'] for row in imported_rows]==[1,0],'Interpreto incorrectamente SI/NO al importar')
        require(any(event['evento']=='ASISTENCIA_IMPORTADA' for event in imported_doc['eventos']),'No audito la importacion')
        invalid_book=root/'LISTADO_ASISTENCIA_INVALIDO.xlsx'
        invalid_wb=Workbook(); invalid_ws=invalid_wb.active; invalid_ws.append(['LISTADO DE ASISTENCIA']); invalid_ws.append(['Nombre completo','Documento','UDS','Asistio']); invalid_ws.append(['PERSONA INEXISTENTE','9999','UCA 1','SI']); invalid_wb.save(invalid_book)
        invalid_id,_=create(repo,1,invalid_book)
        invalid_doc=repo.get_document(invalid_id,1)
        require(invalid_doc['validaciones']['semaforo']=='ROJO','No marco en rojo el documento inexistente')
        require(invalid_doc['validaciones']['errores_criticos']>0,'No genero error critico de Base Maestra')
        invalid_blocked=False
        try: repo.approve(invalid_id,1,10)
        except ValueError: invalid_blocked=True
        require(invalid_blocked,'Permitio aprobar inconsistencias criticas')
        image_path=root/'foto_asistencia.jpg'; Image.new('RGB',(1200,1600),'white').save(image_path)
        image_id,_=create(repo,1,image_path)
        image_doc=repo.get_document(image_id,1)
        require(image_doc['estado']=='REQUIERE_OCR','La imagen no quedo pendiente de OCR')
        blocked=False
        try: repo.approve(image_id,1,10)
        except ValueError: blocked=True
        require(blocked,'Permitio aprobar una imagen sin OCR')
        repo.restart_extraction(image_id,1,10)
        with patch('modules.idp_documental.services._ocr_image_text',return_value='LISTADO DE ASISTENCIA\nNombre Documento UDS Firma\nANA PEREZ  1001  UCA 1  SI'):
            ocr_raw=read_document_ocr(image_path)
        ocr_classification=classify_document(ocr_raw['texto'],image_path.name); ocr_canonical,ocr_fields=canonicalize(ocr_raw,ocr_classification[0]); ocr_canonical['fundacion']['id']=1
        repo.complete_extraction(image_id,1,ocr_raw,ocr_canonical,ocr_fields,ocr_classification,10)
        ocr_doc=repo.get_document(image_id,1)
        require(ocr_doc['estado']=='REQUIERE_REVISION' and ocr_doc['motor_lectura']=='TESSERACT_LOCAL','El reintento OCR no avanzo a revision')
        require(len(ocr_doc['resultado_canonico']['participantes'])==1,'El OCR no estructuro la fila del participante')
        require(ocr_doc['resultado_canonico']['participantes'][0]['documento']=='1001','El OCR no conservo el documento detectado')
        require(ocr_doc['validaciones']['coincidencias']==1,'El participante OCR no se valido contra Base Maestra')
        require(any(field['regla']=='fila_ocr_con_documento' for field in ocr_doc['campos']),'El OCR no guardo evidencia editable')
        require(any(event['evento']=='OCR_REINTENTADO' for event in ocr_doc['eventos']),'No audito el reintento OCR')
        print('IDP core PASS: clasificacion, canonico, tenant, Base Maestra, correccion y aprobacion')


if __name__=='__main__':
    main()
