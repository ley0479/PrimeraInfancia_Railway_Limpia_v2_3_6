from __future__ import annotations

import json
import sqlite3
import tempfile
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / 'backend'
sys.path.insert(0, str(BACKEND))

from openpyxl import load_workbook

from modules.plantillas_oficiales import generar_desde_plantilla_oficial, iter_plantillas_oficiales_para_generacion
from services.ram_v3_service import generate_ram_v3, sha256_file

TEMPLATE = BACKEND / 'templates_originales' / 'oficiales' / 'plantilla_ram_oficial_v3.xlsx'
DB = BACKEND / 'database.sqlite3'
EXPECTED_HASH = 'a6b4c9412f7c72a19b9d5e842fa5ffd4b876c7d0f0c3d5c8e140b5287d700753'


def provider(user):
    return {'lunes', 'viernes'}


def user(index: int, **overrides):
    data = {
        'id': index,
        'tipo_documento': 'RC',
        'documento': f'{index:08d}',
        'primer_nombre': f'NOMBRE{index}',
        'segundo_nombre': '',
        'primer_apellido': f'APELLIDO{index}',
        'segundo_apellido': '',
        'fecha_nacimiento': '2025-08-15',
        'tipo_beneficiario': 'NIÑO O NIÑA ENTRE 6 MESES Y 5 AÑOS Y 11 MESES',
        'fecha_ingreso': '2026-08-01',
        'fecha_retiro': '',
        'motivo_retiro': '',
    }
    data.update(overrides)
    return data


def metadata():
    return {
        'eas_pds': 'FUNDACIÓN PACÍFICO VIVE',
        'nit': '901.234.567-8',
        'contrato': 'C-2026-01',
        'regional': 'CHOCÓ',
        'centro_zonal': 'CZ Ciudad de prueba',
        'municipio': 'Ciudad de prueba',
        'mes_nombre': 'AGOSTO',
        'anio': 2026,
        'agente_educativo': 'AGENTE PRUEBA',
        'documento_agente': '123456',
        'modalidad': 'PROPIA E INTERCULTURAL',
        'codigo_uds': 'UDS-001',
        'unidad': 'UNIDAD PRUEBA',
        'servicio_atencion': 'ATENCIÓN INTEGRAL',
        'direccion_uds': 'DIRECCIÓN PRUEBA',
        'telefono_uds': '3000000000',
    }


def instruction_signature(ws):
    cells = []
    for row in ws.iter_rows():
        for cell in row:
            if cell.value not in (None, ''):
                cells.append((cell.coordinate, cell.value, tuple(cell._style) if cell.has_style else None))
    dimensions = {
        key: (dim.width, dim.hidden, dim.outlineLevel)
        for key, dim in ws.column_dimensions.items()
    }
    rows = {
        key: (dim.height, dim.hidden, dim.outlineLevel)
        for key, dim in ws.row_dimensions.items()
        if dim.height is not None or dim.hidden or dim.outlineLevel
    }
    return {
        'cells': cells,
        'merges': sorted(str(x) for x in ws.merged_cells.ranges),
        'columns': dimensions,
        'rows': rows,
        'print_area': str(ws.print_area),
        'orientation': ws.page_setup.orientation,
        'scale': ws.page_setup.scale,
        'images': len(getattr(ws, '_images', [])),
    }


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def run():
    results = []
    assert_true(sha256_file(TEMPLATE) == EXPECTED_HASH, 'Hash oficial RAM V3 incorrecto antes de pruebas')
    results.append('Hash de plantilla maestra verificado')

    july = iter_plantillas_oficiales_para_generacion(BACKEND / 'templates_originales', mes=7, anio=2026)
    august = iter_plantillas_oficiales_para_generacion(BACKEND / 'templates_originales', mes=8, anio=2026)
    assert_true(not any(x.get('tipo') == 'ram' for x in july), 'RAM V3 no debe aplicar a julio de 2026')
    ram_aug = [x for x in august if x.get('tipo') == 'ram']
    assert_true(len(ram_aug) == 1 and str(ram_aug[0].get('version')) == '3', 'RAM V3 debe aplicar desde agosto de 2026')
    results.append('Selección por vigencia julio/agosto verificada')

    with tempfile.TemporaryDirectory() as temp_period:
        try:
            generar_desde_plantilla_oficial(
                'ram',
                {'metadata': {'anio': 2026, 'mes_numero': 7}, 'usuarios': [user(1)]},
                Path(temp_period) / 'ram_julio_no_valido.xlsx',
                BACKEND / 'templates_originales',
            )
        except ValueError as exc:
            assert_true('todavía no aplica' in str(exc), 'La protección de vigencia directa devolvió un error inesperado')
        else:
            raise AssertionError('El generador directo permitió RAM V3 antes de su vigencia')
    results.append('Protección de vigencia en generador directo verificada')

    source_wb = load_workbook(TEMPLATE, data_only=False)
    source_instruction = instruction_signature(source_wb['INSTRUCCIONES DILIGENCIAMIENTO'])
    source_format = source_wb['FORMATO RAM']
    source_format_signature = {
        'merges': sorted(str(x) for x in source_format.merged_cells.ranges),
        'orientation': source_format.page_setup.orientation,
        'scale': source_format.page_setup.scale,
        'print_area': str(source_format.print_area),
        'images': len(getattr(source_format, '_images', [])),
    }
    source_wb.close()

    with tempfile.TemporaryDirectory() as temp:
        temp = Path(temp)
        for count in (1, 20, 21):
            users = [user(i) for i in range(1, count + 1)]
            if count == 21:
                users[0]['fecha_ingreso'] = '2026-08-10'
                users[1]['fecha_retiro'] = '2026-08-20'
                users[1]['motivo_retiro'] = 'Retiro voluntario'
            out = temp / f'ram_{count}.xlsx'
            report = generate_ram_v3(
                TEMPLATE, out, users, 2026, 8,
                metadata=metadata(), attendance_provider=provider,
                non_service_dates={'2026-08-07'}, expected_sha256=EXPECTED_HASH,
            )
            expected_pages = 1 if count <= 20 else 2
            assert_true(report['paginas_ram'] == expected_pages, f'Paginación incorrecta para {count}')
            wb = load_workbook(out, data_only=False)
            expected_names = ['FORMATO RAM'] + (["FORMATO RAM 2"] if count == 21 else []) + ['INSTRUCCIONES DILIGENCIAMIENTO']
            assert_true(wb.sheetnames == expected_names, f'Orden de hojas incorrecto para {count}: {wb.sheetnames}')
            for page_no, ws in enumerate([x for x in wb.worksheets if x.title.startswith('FORMATO RAM')], start=1):
                sig = {
                    'merges': sorted(str(x) for x in ws.merged_cells.ranges),
                    'orientation': ws.page_setup.orientation,
                    'scale': ws.page_setup.scale,
                    'print_area': str(ws.print_area),
                    'images': len(getattr(ws, '_images', [])),
                }
                assert_true(sig['merges'] == source_format_signature['merges'], 'Se alteraron celdas combinadas')
                assert_true(sig['orientation'] == source_format_signature['orientation'], 'Se alteró orientación')
                assert_true(sig['scale'] == source_format_signature['scale'], 'Se alteró escala')
                assert_true(sig['images'] == source_format_signature['images'], 'Se perdió el logo en una página')
                assert_true(ws['AG4'].value == f'Hoja {page_no} de {expected_pages}', 'Hoja X de Y incorrecta')
                assert_true(ws['X2'].value == 'Página 1 de 2', 'Se alteró el control documental Página 1 de 2')
            assert_true(instruction_signature(wb['INSTRUCCIONES DILIGENCIAMIENTO']) == source_instruction, 'La hoja de instrucciones fue alterada')
            assert_true(wb['FORMATO RAM']['A5'].value == 'NIT: 9000000001', 'NIT no fue normalizado')
            assert_true(wb['FORMATO RAM']['H15'].value == 0 and wb['FORMATO RAM']['I15'].value == 11, 'Edad al primer día del mes incorrecta')
            if count == 21:
                assert_true(wb['FORMATO RAM 2']['A15'].value == 21, 'La numeración no continúa en la segunda página')
                # Agosto 3 de 2026 es lunes, anterior al ingreso del primer usuario del caso.
                assert_true(wb['FORMATO RAM']['J15'].value in (None, ''), 'Se marcó asistencia antes del ingreso')
                # Fecha de retiro 20/08/2026: jueves de la tercera semana = W.
                assert_true(wb['FORMATO RAM']['W16'].value == '/', 'No se marcó / desde la fecha de retiro')
                # Viernes 7/08/2026: primera semana, columna N. Debe quedar vacía y gris.
                assert_true(wb['FORMATO RAM']['N15'].value in (None, ''), 'Día no atención no quedó vacío')
                assert_true(wb['FORMATO RAM']['N15'].fill.fill_type == 'solid', 'Día no atención no quedó sombreado')
            wb.close()
        invalid_user = user(99, NUI='', Documento='REGISTRO CIVIL', numero_documento='1077000099')
        invalid_out = temp / 'ram_documento_validado.xlsx'
        invalid_report = generate_ram_v3(
            TEMPLATE, invalid_out, [invalid_user], 2026, 8,
            metadata=metadata(), attendance_provider=provider,
            expected_sha256=EXPECTED_HASH,
        )
        invalid_wb = load_workbook(invalid_out, data_only=False)
        assert_true(invalid_wb['FORMATO RAM']['C15'].value == '1077000099', 'No se priorizó el número de documento específico')
        invalid_wb.close()
        assert_true(not any('tipo de documento, no al número' in x for x in invalid_report['warnings']), 'Se rechazó un número de documento válido')

        type_only_user = user(100, NUI='', Documento='REGISTRO CIVIL', documento='REGISTRO CIVIL')
        type_only_out = temp / 'ram_documento_tipo.xlsx'
        type_only_report = generate_ram_v3(
            TEMPLATE, type_only_out, [type_only_user], 2026, 8,
            metadata=metadata(), attendance_provider=provider,
            expected_sha256=EXPECTED_HASH,
        )
        type_only_wb = load_workbook(type_only_out, data_only=False)
        assert_true(type_only_wb['FORMATO RAM']['C15'].value in (None, ''), 'Se escribió el tipo documental como número')
        type_only_wb.close()
        assert_true(any('tipo de documento, no al número' in x for x in type_only_report['warnings']), 'No se informó el documento histórico inválido')

        results.append('Generación 1/20/21 participantes verificada')
        results.append('Validación contra tipo documental usado como número verificada')
        results.append('Paginación, numeración, edad, ingreso, retiro y no atención verificados')
        results.append('Hoja de instrucciones, logo, merges e impresión preservados')

    assert_true(sha256_file(TEMPLATE) == EXPECTED_HASH, 'La plantilla maestra cambió después de las pruebas')
    results.append('Plantilla maestra intacta después de generar')

    conn = sqlite3.connect(DB)
    integrity = conn.execute('PRAGMA integrity_check').fetchone()[0]
    version = conn.execute("SELECT version,fecha_vigencia,estado,hash_sha256 FROM plantillas_oficiales_versiones WHERE tipo_formato='RAM' ORDER BY id DESC LIMIT 1").fetchone()
    usuarios_cols = {row[1] for row in conn.execute('PRAGMA table_info(usuarios)').fetchall()}
    beneficiarios_cols = {row[1] for row in conn.execute('PRAGMA table_info(beneficiarios)').fetchall()}
    data_counts = {
        'usuarios': conn.execute('SELECT COUNT(*) FROM usuarios').fetchone()[0],
        'beneficiarios': conn.execute('SELECT COUNT(*) FROM beneficiarios').fetchone()[0],
    }
    conn.close()
    assert_true(integrity == 'ok', f'Integridad SQLite: {integrity}')
    assert_true(version and version[0] == '3' and version[1] == '2026-08-01' and version[3] == EXPECTED_HASH, 'Registro RAM V3 incompleto')
    for field in ('nit_eas', 'servicio_atencion', 'fecha_ingreso'):
        assert_true(field in usuarios_cols, f'Falta usuarios.{field}')
        assert_true(field in beneficiarios_cols, f'Falta beneficiarios.{field}')
    assert_true(data_counts == {'usuarios': 1125, 'beneficiarios': 741}, f'Conteos de datos alterados: {data_counts}')
    results.append('Integridad SQLite, columnas RAM V3 y registro de versión verificados')

    print(json.dumps({'ok': True, 'tests': results}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    run()
