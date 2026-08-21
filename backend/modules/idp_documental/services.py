from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import unicodedata
import zipfile
from typing import Any

from modules.dbapi_compat import sqlite3

from .schema import IDP_SCHEMA_SQL


ALLOWED_EXTENSIONS = {'.xlsx', '.xlsm', '.docx', '.pptx', '.pdf', '.png', '.jpg', '.jpeg', '.bmp', '.tif', '.tiff', '.heif', '.heic'}
MAX_FILE_SIZE = 50 * 1024 * 1024
IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.bmp', '.tif', '.tiff', '.heif', '.heic'}


def now_iso() -> str:
    return datetime.now().isoformat(timespec='seconds')


def connect(database_path: str):
    conn = sqlite3.connect(database_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_schema(database_path: str) -> None:
    conn = connect(database_path)
    conn.executescript(IDP_SCHEMA_SQL)
    conn.commit()
    conn.close()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def validate_file_signature(path: Path) -> None:
    ext = path.suffix.lower()
    if ext in {'.xlsx', '.xlsm', '.docx', '.pptx'}:
        if not zipfile.is_zipfile(path):
            raise ValueError('El archivo Office no tiene una estructura válida.')
        return
    if ext == '.pdf':
        with path.open('rb') as stream:
            if stream.read(5) != b'%PDF-':
                raise ValueError('El archivo no contiene una firma PDF válida.')
        return
    if ext in IMAGE_EXTENSIONS:
        try:
            from PIL import Image
            with Image.open(path) as image:
                image.verify()
        except Exception as exc:
            raise ValueError('La imagen está dañada o no corresponde al formato indicado.') from exc


def normalize(value: Any) -> str:
    text = unicodedata.normalize('NFKD', str(value or '').strip().lower())
    text = ''.join(char for char in text if not unicodedata.combining(char))
    return ' '.join(re.sub(r'[^a-z0-9]+', ' ', text).split())


def classify_document(text: str, filename: str) -> tuple[str, float, str]:
    sample = normalize(f'{filename} {text[:15000]}')
    rules = [
        ('LISTADO_ASISTENCIA', ('listado de asistencia', 'firma del asistente', 'asistio', 'participantes'), 0.94),
        ('RAM', ('formato ram', 'registro de asistencia mensual', 'f27 mt1 pp'), 0.95),
        ('RPP', ('rpp', 'racion preparada', 'minuta patron'), 0.92),
        ('BIENESTARINA', ('bienestarina', 'entrega de alimento', 'lote'), 0.92),
        ('CRONOGRAMA', ('cronograma', 'fecha limite', 'responsable', 'actividad'), 0.88),
        ('PLANEACION_PEDAGOGICA', ('planeacion pedagogica', 'intencionalidad pedagogica', 'experiencia pedagogica'), 0.90),
        ('PESO_TALLA', ('peso kg', 'talla cm', 'valoracion nutricional', 'perimetro braquial'), 0.93),
        ('ACTA', ('acta', 'orden del dia', 'compromisos'), 0.86),
        ('INFORME', ('informe', 'objetivo', 'conclusiones'), 0.78),
    ]
    best = ('NO_CLASIFICADO', 0.0, 'sin coincidencias suficientes')
    for kind, tokens, base in rules:
        hits = sum(1 for token in tokens if token in sample)
        if hits:
            confidence = min(0.99, base - 0.14 + hits * 0.07)
            if confidence > best[1]:
                best = (kind, confidence, f'{hits} regla(s) semantica(s)')
    return best


def _read_excel(path: Path) -> dict:
    from openpyxl import load_workbook
    workbook = load_workbook(path, read_only=True, data_only=False, keep_vba=path.suffix.lower() == '.xlsm')
    sheets, fragments = [], []
    for sheet in workbook.worksheets:
        rows = []
        for row_number, row in enumerate(sheet.iter_rows(values_only=True), 1):
            values = [value.isoformat() if hasattr(value, 'isoformat') else value for value in row]
            if any(value not in (None, '') for value in values):
                rows.append({'fila': row_number, 'valores': values})
                fragments.extend(str(value) for value in values if value not in (None, ''))
            if len(rows) >= 5000:
                break
        sheets.append({'nombre': sheet.title, 'filas': rows, 'max_filas_leidas': len(rows)})
    workbook.close()
    return {'motor': 'OPENPYXL_NATIVE', 'texto': '\n'.join(fragments), 'hojas': sheets}


def _read_word(path: Path) -> dict:
    from docx import Document
    document = Document(str(path))
    paragraphs = [{'indice': index + 1, 'texto': p.text} for index, p in enumerate(document.paragraphs) if p.text.strip()]
    tables = []
    for table_index, table in enumerate(document.tables, 1):
        rows = [[cell.text for cell in row.cells] for row in table.rows]
        tables.append({'tabla': table_index, 'filas': rows})
    text = '\n'.join([item['texto'] for item in paragraphs] + [str(cell) for table in tables for row in table['filas'] for cell in row])
    return {'motor': 'PYTHON_DOCX_NATIVE', 'texto': text, 'parrafos': paragraphs, 'tablas': tables}


def _read_powerpoint(path: Path) -> dict:
    from pptx import Presentation
    presentation = Presentation(str(path))
    slides, fragments = [], []
    for slide_index, slide in enumerate(presentation.slides, 1):
        texts = []
        for shape in slide.shapes:
            if hasattr(shape, 'text') and str(shape.text).strip():
                texts.append(str(shape.text))
                fragments.append(str(shape.text))
        slides.append({'pagina': slide_index, 'textos': texts})
    return {'motor': 'PYTHON_PPTX_NATIVE', 'texto': '\n'.join(fragments), 'diapositivas': slides}


def _read_pdf(path: Path) -> dict:
    try:
        import fitz
    except Exception as exc:
        return {'motor': 'PDF_PENDIENTE', 'texto': '', 'paginas': [], 'requiere_ocr': True, 'advertencia': f'PyMuPDF no disponible: {exc}'}
    document = fitz.open(str(path))
    pages, fragments = [], []
    for index, page in enumerate(document, 1):
        text = page.get_text('text') or ''
        pages.append({'pagina': index, 'texto': text})
        fragments.append(text)
    document.close()
    combined = '\n'.join(fragments).strip()
    return {'motor': 'PYMUPDF_NATIVE', 'texto': combined, 'paginas': pages, 'requiere_ocr': len(combined) < 20}


def read_document(path: Path) -> dict:
    ext = path.suffix.lower()
    if ext in {'.xlsx', '.xlsm'}:
        return _read_excel(path)
    if ext == '.docx':
        return _read_word(path)
    if ext == '.pptx':
        return _read_powerpoint(path)
    if ext == '.pdf':
        return _read_pdf(path)
    if ext in IMAGE_EXTENSIONS:
        quality = {'legible': None, 'requiere_revision': True}
        try:
            from PIL import Image
            with Image.open(path) as image:
                quality.update({'ancho_px': image.width, 'alto_px': image.height, 'modo': image.mode, 'legible': min(image.size) >= 800})
        except Exception:
            pass
        return {'motor': 'IMAGEN_PENDIENTE_OCR', 'texto': '', 'requiere_ocr': True, 'calidad': quality}
    raise ValueError('Formato no soportado por el lector IDP.')


HEADER_ALIASES = {
    'documento': ('documento', 'identificacion', 'cedula', 'nui'),
    'nombre_completo': ('nombre', 'nombres y apellidos', 'participante', 'beneficiario'),
    'asistio': ('asistio', 'asistencia', 'presente'),
    'firma_presente': ('firma', 'firma del asistente'),
    'unidad': ('uds', 'uca', 'unidad', 'unidad de servicio'),
}


def _mapped_header(value: Any) -> str | None:
    text = normalize(value)
    for field, aliases in HEADER_ALIASES.items():
        if text in aliases or any(len(alias) >= 4 and alias in text for alias in aliases):
            return field
    return None


def canonicalize(raw: dict, document_type: str) -> tuple[dict, list[dict]]:
    canonical = {'tipo_documento': document_type, 'version_plantilla': None, 'periodo': {}, 'fundacion': {}, 'unidad_servicio': {}, 'actividad': {}, 'participantes': [], 'metadatos': {'motor': raw.get('motor'), 'requiere_ocr': bool(raw.get('requiere_ocr'))}}
    fields = []
    if document_type in {'LISTADO_ASISTENCIA', 'RAM'} and raw.get('hojas'):
        for sheet in raw['hojas']:
            rows = sheet.get('filas') or []
            for position, row in enumerate(rows):
                mapping = {field: col for col, value in enumerate(row['valores']) if (field := _mapped_header(value))}
                if len(mapping) < 2:
                    continue
                for data_row in rows[position + 1:]:
                    values = data_row['valores']
                    participant = {}
                    for field, col in mapping.items():
                        value = values[col] if col < len(values) else None
                        if field == 'unidad' and value and not canonical['unidad_servicio'].get('nombre'):
                            canonical['unidad_servicio']['nombre'] = str(value)
                        elif field not in {'unidad'}:
                            participant[field] = value
                            fields.append({'ruta': f'participantes.{len(canonical["participantes"])}.{field}', 'valor': value, 'texto_original': value, 'confianza': 0.98 if value not in (None, '') else 0.0, 'evidencia': {'hoja': sheet['nombre'], 'fila': data_row['fila'], 'columna': col + 1}, 'regla': 'encabezado_excel'})
                    if any(participant.get(key) not in (None, '') for key in ('documento', 'nombre_completo')):
                        canonical['participantes'].append(participant)
                break
    fields.append({'ruta': 'tipo_documento', 'valor': document_type, 'texto_original': document_type, 'confianza': 1.0, 'evidencia': {}, 'regla': 'clasificador_reglas'})
    return canonical, fields


def public_document(row: Any) -> dict:
    item = dict(row)
    for source, target, default in (
        ('resultado_canonico_json', 'resultado_canonico', {}),
        ('validaciones_json', 'validaciones', []),
    ):
        try:
            item[target] = json.loads(item.get(source) or json.dumps(default))
        except Exception:
            item[target] = default
        item.pop(source, None)
    item.pop('resultado_bruto_json', None)
    item.pop('ruta_privada', None)
    return item
