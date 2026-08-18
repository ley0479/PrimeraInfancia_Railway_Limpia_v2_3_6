"""
Servicios de Salud y Nutrición Inteligente.

Este módulo no reemplaza el módulo histórico de Nutrición y Talla. Agrega una capa
independiente para historia nutricional, diagnóstico, alertas, cruces de bases y
reportes ejecutivos.
"""
from __future__ import annotations

import calendar
import json
import math
import os
import re
from datetime import datetime, timedelta
from typing import Any

from services.uds_catalog import aliases_upper as catalog_aliases_upper, normalize_unit as catalog_normalize_unit

import pandas as pd


MESES_ES = {
    1: 'ENERO', 2: 'FEBRERO', 3: 'MARZO', 4: 'ABRIL',
    5: 'MAYO', 6: 'JUNIO', 7: 'JULIO', 8: 'AGOSTO',
    9: 'SEPTIEMBRE', 10: 'OCTUBRE', 11: 'NOVIEMBRE', 12: 'DICIEMBRE'
}

ALIAS_UNIDADES = catalog_aliases_upper()


def now_iso() -> str:
    return datetime.now().isoformat(timespec='seconds')


def limpiar_valor(valor: Any, default: str = '') -> str:
    if valor is None:
        return default
    try:
        if pd.isna(valor):
            return default
    except Exception:
        pass
    texto = str(valor).strip()
    if texto.lower() in {'nan', 'nat', 'none', 'null'}:
        return default
    return texto


def normalizar_texto(valor: Any) -> str:
    import unicodedata
    texto = limpiar_valor(valor).lower()
    texto = unicodedata.normalize('NFKD', texto)
    texto = ''.join(ch for ch in texto if not unicodedata.combining(ch))
    texto = re.sub(r'[^a-z0-9]+', ' ', texto)
    return ' '.join(texto.split())


def normalize_unidad(unidad: Any) -> str:
    return catalog_normalize_unit(unidad, preserve_unknown=True)


def parse_fecha(valor: Any) -> datetime | None:
    if valor is None:
        return None
    try:
        if pd.isna(valor):
            return None
    except Exception:
        pass
    if isinstance(valor, datetime):
        return valor
    texto = limpiar_valor(valor)
    if not texto:
        return None
    if re.fullmatch(r'\d+(\.\d+)?', texto):
        try:
            numero = float(texto)
            if numero > 20000:
                return pd.to_datetime(numero, unit='D', origin='1899-12-30').to_pydatetime()
        except Exception:
            pass
    for dayfirst in (True, False):
        try:
            fecha = pd.to_datetime(texto, errors='coerce', dayfirst=dayfirst)
            if pd.notna(fecha):
                return fecha.to_pydatetime()
        except Exception:
            continue
    return None


def fecha_iso(valor: Any) -> str:
    fecha = parse_fecha(valor)
    return fecha.date().isoformat() if fecha else limpiar_valor(valor)


def calcular_edad_meses(fecha_nacimiento: Any, referencia: datetime | None = None) -> int:
    fecha = parse_fecha(fecha_nacimiento)
    if not fecha:
        return 0
    hoy = referencia or datetime.now()
    meses = (hoy.year - fecha.year) * 12 + (hoy.month - fecha.month)
    if hoy.day < fecha.day:
        meses -= 1
    return max(0, meses)


def edad_texto(edad_meses: int) -> str:
    edad_meses = int(edad_meses or 0)
    anios = edad_meses // 12
    meses = edad_meses % 12
    partes = []
    if anios:
        partes.append(f"{anios} año" + ('' if anios == 1 else 's'))
    if meses or not partes:
        partes.append(f"{meses} mes" + ('' if meses == 1 else 'es'))
    return ' y '.join(partes)


def parse_numero(valor: Any) -> float | None:
    texto = limpiar_valor(valor)
    if not texto:
        return None
    texto = texto.replace(',', '.')
    texto = re.sub(r'[^0-9.\-]+', '', texto)
    if texto in {'', '.', '-'}:
        return None
    try:
        return float(texto)
    except Exception:
        return None


def periodo_desde_fecha(fecha_valoracion: str) -> str:
    fecha = parse_fecha(fecha_valoracion) or datetime.now()
    return f"{fecha.year}-{fecha.month:02d}"


def trimestre_desde_fecha(fecha_valoracion: str) -> str:
    fecha = parse_fecha(fecha_valoracion) or datetime.now()
    tri = ((fecha.month - 1) // 3) + 1
    return f"T{tri}-{fecha.year}"


def proximo_control(fecha_valoracion: str, dias: int = 90) -> str:
    fecha = parse_fecha(fecha_valoracion)
    if not fecha:
        return ''
    return (fecha + timedelta(days=dias)).date().isoformat()


def estado_control_trimestral(fecha_valoracion: str) -> str:
    fecha = parse_fecha(fecha_valoracion)
    if not fecha:
        return 'Pendiente'
    dias = (datetime.now() - fecha).days
    if dias <= 75:
        return 'Al día'
    if dias <= 90:
        return 'Próximo a vencer'
    return 'Vencido'


def clasificar_zscore(z: float | None, indicador: str = '') -> str:
    if z is None:
        return 'Pendiente'
    try:
        z = float(z)
    except Exception:
        return 'Pendiente'
    if z <= -3:
        return 'Desnutrición severa'
    if z <= -2:
        return 'Desnutrición moderada'
    if z < -1:
        return 'Riesgo de desnutrición'
    if z <= 1:
        return 'Adecuado'
    if z <= 2:
        return 'Riesgo de sobrepeso'
    if z <= 3:
        return 'Sobrepeso'
    return 'Obesidad'


def nivel_por_diagnostico(diagnostico: str) -> str:
    diag = normalizar_texto(diagnostico)
    if any(k in diag for k in ['severa', 'moderada', 'obesidad']):
        return 'ROJO'
    if any(k in diag for k in ['riesgo', 'sobrepeso', 'pendiente', 'faltante']):
        return 'AMARILLO'
    return 'VERDE'


def peor_diagnostico(diagnosticos: list[str]) -> str:
    prioridad = [
        'Desnutrición severa', 'Desnutrición moderada', 'Obesidad',
        'Riesgo de desnutrición', 'Sobrepeso', 'Riesgo de sobrepeso',
        'Pendiente', 'Adecuado'
    ]
    normalizados = {normalizar_texto(d): d for d in diagnosticos if d}
    for item in prioridad:
        clave = normalizar_texto(item)
        if any(clave in normalizar_texto(v) for v in diagnosticos):
            return item
    return 'Adecuado'


def diagnostico_braquial(perimetro: float | None) -> str:
    if perimetro is None:
        return 'Pendiente'
    # Umbrales de tamizaje usados comúnmente para perímetro braquial en primera infancia.
    if perimetro < 11.5:
        return 'Desnutrición severa'
    if perimetro < 12.5:
        return 'Desnutrición moderada'
    if perimetro < 13.5:
        return 'Riesgo de desnutrición'
    return 'Adecuado'


def diagnostico_fallback(edad_meses: int, sexo: str, peso: float | None, talla: float | None,
                         imc: float | None, braquial: float | None) -> dict[str, Any]:
    """Preclasificación cuando el archivo no trae z-scores ni tablas OMS cargadas.

    Este fallback no reemplaza las tablas OMS/ICBF. Permite generar alertas operativas
    y deja el módulo listo para usar z-scores o tablas oficiales cuando se carguen.
    """
    diag_peso_edad = 'Pendiente'
    diag_talla_edad = 'Pendiente'
    diag_peso_talla = 'Pendiente'
    diag_imc_edad = 'Pendiente'

    if peso is not None and edad_meses:
        if peso <= 0:
            diag_peso_edad = 'Pendiente'
        elif edad_meses < 6 and peso < 4.5:
            diag_peso_edad = 'Riesgo de desnutrición'
        elif edad_meses < 12 and peso < 6.5:
            diag_peso_edad = 'Riesgo de desnutrición'
        elif edad_meses < 24 and peso < 8.0:
            diag_peso_edad = 'Riesgo de desnutrición'
        elif edad_meses >= 24 and peso < 10.0:
            diag_peso_edad = 'Riesgo de desnutrición'
        else:
            diag_peso_edad = 'Adecuado'

    if talla is not None and edad_meses:
        if talla <= 0:
            diag_talla_edad = 'Pendiente'
        elif edad_meses < 12 and talla < 60:
            diag_talla_edad = 'Riesgo de desnutrición'
        elif edad_meses < 24 and talla < 72:
            diag_talla_edad = 'Riesgo de desnutrición'
        elif edad_meses >= 24 and talla < 82:
            diag_talla_edad = 'Riesgo de desnutrición'
        else:
            diag_talla_edad = 'Adecuado'

    if imc is not None:
        if imc < 13:
            diag_imc_edad = 'Desnutrición moderada'
        elif imc < 14:
            diag_imc_edad = 'Riesgo de desnutrición'
        elif imc <= 18:
            diag_imc_edad = 'Adecuado'
        elif imc <= 19.5:
            diag_imc_edad = 'Riesgo de sobrepeso'
        elif imc <= 21:
            diag_imc_edad = 'Sobrepeso'
        else:
            diag_imc_edad = 'Obesidad'
        diag_peso_talla = diag_imc_edad

    diag_braquial = diagnostico_braquial(braquial)
    global_diag = peor_diagnostico([
        diag_peso_edad, diag_talla_edad, diag_peso_talla, diag_imc_edad, diag_braquial
    ])
    return {
        'diag_peso_edad': diag_peso_edad,
        'diag_talla_edad': diag_talla_edad,
        'diag_peso_talla': diag_peso_talla,
        'diag_imc_edad': diag_imc_edad,
        'diag_braquial_edad': diag_braquial,
        'diagnostico_global': global_diag,
        'nivel_alerta': nivel_por_diagnostico(global_diag),
    }


def diagnostico_desde_datos(data: dict[str, Any]) -> dict[str, Any]:
    peso = data.get('peso_kg')
    talla = data.get('talla_cm')
    imc = None
    if peso is not None and talla:
        try:
            imc = round(float(peso) / ((float(talla) / 100) ** 2), 2)
        except Exception:
            imc = None

    data['imc'] = imc

    z_peso_edad = data.get('z_peso_edad')
    z_talla_edad = data.get('z_talla_edad')
    z_peso_talla = data.get('z_peso_talla')
    z_imc_edad = data.get('z_imc_edad')
    z_braquial_edad = data.get('z_braquial_edad')

    if any(z is not None for z in [z_peso_edad, z_talla_edad, z_peso_talla, z_imc_edad, z_braquial_edad]):
        diag = {
            'diag_peso_edad': clasificar_zscore(z_peso_edad, 'peso_edad'),
            'diag_talla_edad': clasificar_zscore(z_talla_edad, 'talla_edad'),
            'diag_peso_talla': clasificar_zscore(z_peso_talla, 'peso_talla'),
            'diag_imc_edad': clasificar_zscore(z_imc_edad, 'imc_edad'),
            'diag_braquial_edad': clasificar_zscore(z_braquial_edad, 'braquial_edad'),
        }
        diag['diagnostico_global'] = peor_diagnostico(list(diag.values()))
        diag['nivel_alerta'] = nivel_por_diagnostico(diag['diagnostico_global'])
        return {**data, **diag}

    fallback = diagnostico_fallback(
        int(data.get('edad_meses') or 0),
        data.get('sexo', ''),
        peso,
        talla,
        imc,
        data.get('perimetro_braquial_cm')
    )
    return {**data, **fallback}


def find_col(columns: list[str], aliases: list[str]) -> str | None:
    normalizadas = [(normalizar_texto(c), c) for c in columns]
    aliases_norm = [normalizar_texto(a) for a in aliases]
    for alias in aliases_norm:
        for norm, original in normalizadas:
            if norm == alias:
                return original
    for alias in aliases_norm:
        for norm, original in normalizadas:
            if alias and alias in norm:
                return original
    return None


def read_tabular_file(path: str) -> pd.DataFrame:
    ext = os.path.splitext(path.lower())[1]
    if ext in {'.xlsx', '.xls', '.xlsm'}:
        return pd.read_excel(path)
    if ext == '.csv':
        return pd.read_csv(path)
    if ext == '.txt':
        try:
            return pd.read_csv(path, sep=None, engine='python')
        except Exception:
            return pd.read_csv(path, sep='\t')
    raise ValueError('Formato no soportado para datos tabulares.')


def inferir_edad_desde_columna(valor: Any) -> int:
    texto = limpiar_valor(valor)
    if not texto:
        return 0
    nums = re.findall(r'\d+', texto)
    if not nums:
        return 0
    n = int(nums[0])
    norm = normalizar_texto(texto)
    if 'mes' in norm:
        return n
    if 'ano' in norm or 'anio' in norm or 'edad' in norm:
        return n * 12
    if 0 <= n <= 6:
        return n * 12
    return n


def normalizar_base_personas(df: pd.DataFrame) -> list[dict[str, Any]]:
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    cols = list(df.columns)

    def evitar_acudiente(col):
        if not col:
            return col
        norm_col = normalizar_texto(col)
        if 'acudiente' in norm_col or 'responsable' in norm_col:
            return None
        return col

    col_doc = evitar_acudiente(find_col(cols, ['documento del beneficiario', 'número de documento del beneficiario',
                              'numero de documento del beneficiario', 'nui', 'nuip', 'documento beneficiario',
                              'no documento participante', 'n doc ident', 'documento']))
    col_tipo_doc = evitar_acudiente(find_col(cols, ['tipo de documento del beneficiario', 'tipo documento beneficiario', 'tipo documento', 'tipo de documento']))
    col_nombre = evitar_acudiente(find_col(cols, ['nombre completo del beneficiario', 'nombre del beneficiario', 'nombres y apellidos del participante', 'nombres y apellidos beneficiario']))
    col_pn = evitar_acudiente(find_col(cols, ['primer nombre del beneficiario', 'primer nombre beneficiario', 'primer nombre']))
    col_sn = evitar_acudiente(find_col(cols, ['segundo nombre del beneficiario', 'segundo nombre beneficiario', 'segundo nombre']))
    col_pa = evitar_acudiente(find_col(cols, ['primer apellido del beneficiario', 'primer apellido beneficiario', 'primer apellido']))
    col_sa = evitar_acudiente(find_col(cols, ['segundo apellido del beneficiario', 'segundo apellido beneficiario', 'segundo apellido']))
    col_fecha_nac = evitar_acudiente(find_col(cols, ['fecha de nacimiento del beneficiario', 'fecha nacimiento beneficiario', 'fecha nacimiento', 'fecha de nacimiento']))
    col_edad = find_col(cols, ['edad', 'edad del beneficiario'])
    col_sexo = evitar_acudiente(find_col(cols, ['sexo del beneficiario', 'sexo']))
    col_unidad = find_col(cols, ['unidad', 'unidad de servicio', 'nombre de la unidad de servicio', 'uca'])
    col_docente = find_col(cols, ['docente', 'agente educativo', 'educador'])
    col_acudiente = find_col(cols, ['nombre completo acudiente', 'nombre acudiente', 'nombre completo del acudiente', 'nombre responsable'])
    col_acudiente_pn = find_col(cols, ['primer nombre del acudiente o responsable', 'primer nombre acudiente', 'primer nombre responsable'])
    col_acudiente_sn = find_col(cols, ['segundo nombre del acudiente o responsable', 'segundo nombre acudiente', 'segundo nombre responsable'])
    col_acudiente_pa = find_col(cols, ['primer apellido del acudiente o responsable', 'primer apellido acudiente', 'primer apellido responsable'])
    col_acudiente_sa = find_col(cols, ['segundo apellido del acudiente o responsable', 'segundo apellido acudiente', 'segundo apellido responsable'])
    col_tel = evitar_acudiente(find_col(cols, ['teléfono del beneficiario', 'telefono del beneficiario', 'celular del beneficiario', 'número de celular', 'numero de celular', 'telefono', 'teléfono', 'celular']))
    col_dir = evitar_acudiente(find_col(cols, ['direccion de residencia del beneficiario', 'dirección de residencia del beneficiario', 'direccion residencia beneficiario', 'direccion', 'dirección']))
    col_fecha_val = find_col(cols, ['fecha valoración', 'fecha valoracion', 'fecha medicion', 'fecha medición',
                                    'fecha toma', 'fecha control', 'fecha valoración nutricional'])
    col_peso = find_col(cols, ['peso', 'peso kg', 'peso en kg'])
    col_talla = find_col(cols, ['talla', 'talla cm', 'estatura', 'longitud'])
    col_braquial = find_col(cols, ['perimetro braquial', 'perímetro braquial', 'pb', 'muac'])
    col_cefalico = find_col(cols, ['perimetro cefalico', 'perímetro cefálico', 'pc'])
    col_z_pe = find_col(cols, ['z peso edad', 'zscore peso edad', 'z_peso_edad', 'p/e'])
    col_z_te = find_col(cols, ['z talla edad', 'zscore talla edad', 'z_talla_edad', 't/e'])
    col_z_pt = find_col(cols, ['z peso talla', 'zscore peso talla', 'z_peso_talla', 'p/t'])
    col_z_imc = find_col(cols, ['z imc edad', 'zscore imc edad', 'z_imc_edad', 'imc/e'])
    col_z_pb = find_col(cols, ['z braquial edad', 'z perimetro braquial', 'z_pb'])

    registros = []
    for _, row in df.iterrows():
        documento = limpiar_valor(row.get(col_doc)) if col_doc else ''
        if not documento:
            continue

        nombre_partes = ' '.join([
            limpiar_valor(row.get(col_pn)) if col_pn else '',
            limpiar_valor(row.get(col_sn)) if col_sn else '',
            limpiar_valor(row.get(col_pa)) if col_pa else '',
            limpiar_valor(row.get(col_sa)) if col_sa else '',
        ]).strip()
        nombre = nombre_partes or (limpiar_valor(row.get(col_nombre)) if col_nombre else '')
        nombre = re.sub(r'\s+', ' ', nombre).strip()

        fecha_nac = fecha_iso(row.get(col_fecha_nac)) if col_fecha_nac else ''
        edad_m = calcular_edad_meses(fecha_nac) if fecha_nac else 0
        if not edad_m and col_edad:
            edad_m = inferir_edad_desde_columna(row.get(col_edad))

        fecha_val = fecha_iso(row.get(col_fecha_val)) if col_fecha_val else datetime.now().date().isoformat()
        peso = parse_numero(row.get(col_peso)) if col_peso else None
        talla = parse_numero(row.get(col_talla)) if col_talla else None
        braquial = parse_numero(row.get(col_braquial)) if col_braquial else None
        cefalico = parse_numero(row.get(col_cefalico)) if col_cefalico else None

        acudiente = limpiar_valor(row.get(col_acudiente)).upper() if col_acudiente else ''
        if not acudiente:
            acudiente = ' '.join([
                limpiar_valor(row.get(col_acudiente_pn)).upper() if col_acudiente_pn else '',
                limpiar_valor(row.get(col_acudiente_sn)).upper() if col_acudiente_sn else '',
                limpiar_valor(row.get(col_acudiente_pa)).upper() if col_acudiente_pa else '',
                limpiar_valor(row.get(col_acudiente_sa)).upper() if col_acudiente_sa else '',
            ]).strip()
        acudiente = re.sub(r'\s+', ' ', acudiente).strip()

        data = {
            'tipo_documento': limpiar_valor(row.get(col_tipo_doc)) if col_tipo_doc else '',
            'documento': documento,
            'nui': documento,
            'nombre_completo': nombre.upper(),
            'fecha_nacimiento': fecha_nac,
            'edad_meses': edad_m,
            'edad_texto': edad_texto(edad_m),
            'sexo': limpiar_valor(row.get(col_sexo)).upper() if col_sexo else '',
            'unidad': normalize_unidad(row.get(col_unidad)) if col_unidad else '',
            'docente': limpiar_valor(row.get(col_docente)).upper() if col_docente else '',
            'acudiente': acudiente,
            'telefono': limpiar_valor(row.get(col_tel)) if col_tel else '',
            'direccion': limpiar_valor(row.get(col_dir)).upper() if col_dir else '',
            'fecha_valoracion': fecha_val,
            'peso_kg': peso,
            'talla_cm': talla,
            'perimetro_braquial_cm': braquial,
            'perimetro_cefalico_cm': cefalico,
            'z_peso_edad': parse_numero(row.get(col_z_pe)) if col_z_pe else None,
            'z_talla_edad': parse_numero(row.get(col_z_te)) if col_z_te else None,
            'z_peso_talla': parse_numero(row.get(col_z_pt)) if col_z_pt else None,
            'z_imc_edad': parse_numero(row.get(col_z_imc)) if col_z_imc else None,
            'z_braquial_edad': parse_numero(row.get(col_z_pb)) if col_z_pb else None,
        }
        data = diagnostico_desde_datos(data)
        data['periodo'] = periodo_desde_fecha(fecha_val)
        data['trimestre'] = trimestre_desde_fecha(fecha_val)
        data['estado_control'] = estado_control_trimestral(fecha_val)
        data['proximo_control'] = proximo_control(fecha_val)
        registros.append(data)
    return registros


def normalizar_base_comparacion(df: pd.DataFrame) -> dict[str, dict[str, Any]]:
    registros = normalizar_base_personas(df)
    return {
        str(r['documento']).strip(): {
            'documento': str(r['documento']).strip(),
            'nombre': r.get('nombre_completo', ''),
            'unidad': r.get('unidad', ''),
            'docente': r.get('docente', ''),
            'acudiente': r.get('acudiente', ''),
            'telefono': r.get('telefono', ''),
            'direccion': r.get('direccion', ''),
        }
        for r in registros
        if r.get('documento')
    }


def comparar_bases(anterior: dict[str, dict[str, Any]], actual: dict[str, dict[str, Any]]) -> dict[str, Any]:
    docs_ant = set(anterior)
    docs_act = set(actual)
    nuevos = sorted(docs_act - docs_ant)
    retirados = sorted(docs_ant - docs_act)
    comunes = sorted(docs_ant & docs_act)

    cambios = []
    trasladados = []
    campos = ['unidad', 'docente', 'acudiente', 'telefono', 'direccion']
    for doc in comunes:
        ant = anterior[doc]
        act = actual[doc]
        cambios_doc = {}
        for campo in campos:
            if normalizar_texto(ant.get(campo)) != normalizar_texto(act.get(campo)):
                cambios_doc[campo] = {'anterior': ant.get(campo, ''), 'actual': act.get(campo, '')}
        if cambios_doc:
            item = {
                'documento': doc,
                'nombre': act.get('nombre') or ant.get('nombre'),
                'cambios': cambios_doc
            }
            cambios.append(item)
            if 'unidad' in cambios_doc:
                trasladados.append(item)

    return {
        'nuevos': [actual[d] for d in nuevos],
        'retirados': [anterior[d] for d in retirados],
        'trasladados': trasladados,
        'cambios': cambios,
        'resumen': {
            'total_anterior': len(anterior),
            'total_actual': len(actual),
            'nuevos': len(nuevos),
            'retirados': len(retirados),
            'trasladados': len(trasladados),
            'cambios': len(cambios),
        }
    }


def calcular_alertas_valoracion(valoracion: dict[str, Any], anterior: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    alertas = []
    diag = valoracion.get('diagnostico_global', 'Pendiente')
    nivel = valoracion.get('nivel_alerta') or nivel_por_diagnostico(diag)
    doc = valoracion.get('documento')
    unidad = valoracion.get('unidad', '')
    nombre = valoracion.get('nombre_completo', '')

    if nivel == 'ROJO':
        alertas.append({'documento': doc, 'tipo': 'Diagnóstico crítico', 'nivel': 'ROJO',
                        'mensaje': f'{nombre}: {diag}', 'unidad': unidad})
    elif nivel == 'AMARILLO':
        alertas.append({'documento': doc, 'tipo': 'Riesgo nutricional', 'nivel': 'AMARILLO',
                        'mensaje': f'{nombre}: {diag}', 'unidad': unidad})

    if valoracion.get('peso_kg') is None or valoracion.get('talla_cm') is None:
        alertas.append({'documento': doc, 'tipo': 'Datos faltantes', 'nivel': 'AMARILLO',
                        'mensaje': f'{nombre}: faltan datos de peso o talla.', 'unidad': unidad})

    if valoracion.get('estado_control') == 'Vencido':
        alertas.append({'documento': doc, 'tipo': 'Control vencido', 'nivel': 'ROJO',
                        'mensaje': f'{nombre}: control nutricional trimestral vencido.', 'unidad': unidad})

    if valoracion.get('diag_braquial_edad') in {'Desnutrición severa', 'Desnutrición moderada', 'Riesgo de desnutrición'}:
        alertas.append({'documento': doc, 'tipo': 'Perímetro braquial', 'nivel': nivel_por_diagnostico(valoracion.get('diag_braquial_edad')),
                        'mensaje': f'{nombre}: {valoracion.get("diag_braquial_edad")} por perímetro braquial.', 'unidad': unidad})

    if anterior and anterior.get('peso_kg') is not None and valoracion.get('peso_kg') is not None:
        try:
            if float(valoracion['peso_kg']) < float(anterior['peso_kg']):
                alertas.append({'documento': doc, 'tipo': 'Disminución de peso', 'nivel': 'AMARILLO',
                                'mensaje': f'{nombre}: el peso disminuyó frente a la valoración anterior.', 'unidad': unidad})
        except Exception:
            pass

    return alertas


def latest_by_documento(valoraciones: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    latest = {}
    for row in valoraciones:
        doc = row.get('documento')
        if not doc:
            continue
        fecha = row.get('fecha_valoracion') or ''
        if doc not in latest or fecha > (latest[doc].get('fecha_valoracion') or ''):
            latest[doc] = row
    return latest
