"""
Servicios de negocio del módulo Gestión Pedagógica.
"""
from __future__ import annotations

from datetime import datetime, date, timedelta
import calendar
from typing import Any

ESTADOS_ENTREGABLE = [
    'Pendiente',
    'En proceso',
    'Cargado',
    'En revisión',
    'Aprobado',
    'Devuelto',
    'Vencido',
    'Cumplido fuera de fecha',
]

ESTADOS_CERRADOS = {'Aprobado', 'Cumplido fuera de fecha'}


def periodo_actual() -> str:
    return datetime.now().strftime('%Y-%m')




def calendario_operativo_default(periodo: str) -> list[dict[str, str]]:
    """Calendario base mensual de operación.

    Usa los mismos conceptos del comunicado mensual y cambia automáticamente el mes/año.
    Las fechas pueden editarse después desde el calendario.
    """
    try:
        anio, mes = [int(x) for x in periodo.split('-')[:2]]
    except Exception:
        hoy = datetime.now()
        anio, mes = hoy.year, hoy.month
    ultimo = calendar.monthrange(anio, mes)[1]

    def fecha(dia: int) -> str:
        return f"{anio}-{mes:02d}-{min(max(1, dia), ultimo):02d}"

    return [
        {
            'tipo': 'Cambios de beneficiarios',
            'titulo': 'Cambios de beneficiarios',
            'fecha': fecha(1),
            'hora': '',
            'descripcion': f'Periodo de cambios del 1 al {min(4, ultimo)} del mes. Revisar novedades, ingresos, retiros y traslados.',
            'color': 'amarillo',
            'prioridad': 'alta',
            'responsable': 'Coordinación operativa'
        },
        {
            'tipo': 'Cuenta de cobro',
            'titulo': 'Entrega de cuentas de cobro',
            'fecha': fecha(9),
            'hora': '',
            'descripcion': 'Recepción de cuentas de cobro del talento humano correspondiente al mes.',
            'color': 'verde',
            'prioridad': 'alta',
            'responsable': 'Talento humano'
        },
        {
            'tipo': 'Documentos nuevos y MG',
            'titulo': 'Entrega de escáner de documentos niños, niñas nuevos y madres gestantes',
            'fecha': fecha(15),
            'hora': '',
            'descripcion': 'Entrega de soportes documentales escaneados de usuarios nuevos y madres gestantes.',
            'color': 'morado',
            'prioridad': 'media',
            'responsable': 'Coordinadores'
        },
        {
            'tipo': 'Capacitación talento humano',
            'titulo': 'Capacitación para el talento humano',
            'fecha': fecha(17),
            'hora': '14:00',
            'descripcion': f'Capacitación programada para los días {min(17, ultimo)}, {min(18, ultimo)} y {min(19, ultimo)}. Hora sugerida: 2:00 p.m. a 5:00 p.m.',
            'color': 'rosa',
            'prioridad': 'media',
            'responsable': 'Gerencia / Coordinación'
        },
        {
            'tipo': 'Informe mensual',
            'titulo': 'Entrega de informe mensual',
            'fecha': fecha(23),
            'hora': '',
            'descripcion': 'Entrega del informe mensual de actividades, evidencias, cumplimiento y novedades.',
            'color': 'azul',
            'prioridad': 'alta',
            'responsable': 'Coordinadores'
        },
    ]


def parse_fecha(valor: str | None) -> date | None:
    if not valor:
        return None
    try:
        return datetime.strptime(str(valor)[:10], '%Y-%m-%d').date()
    except Exception:
        return None


def estado_calculado(entregable: dict[str, Any], hoy: date | None = None) -> str:
    estado = str(entregable.get('estado') or 'Pendiente')
    if estado in ESTADOS_CERRADOS or estado in {'Devuelto'}:
        return estado
    limite = parse_fecha(entregable.get('fecha_limite'))
    hoy = hoy or date.today()
    if limite and limite < hoy and estado not in {'Aprobado', 'Cumplido fuera de fecha'}:
        return 'Vencido'
    return estado


def alerta_por_entregable(entregable: dict[str, Any], hoy: date | None = None) -> dict[str, Any] | None:
    hoy = hoy or date.today()
    estado = estado_calculado(entregable, hoy)
    limite = parse_fecha(entregable.get('fecha_limite'))

    if estado in ESTADOS_CERRADOS:
        return None

    if not limite:
        return {
            'nivel': 'AMARILLO',
            'tipo': 'SIN_FECHA_LIMITE',
            'mensaje': f"Entregable sin fecha límite: {entregable.get('titulo') or entregable.get('tipo')}",
            'entregable_id': entregable.get('id'),
            'coordinador_id': entregable.get('coordinador_id'),
            'fecha_alerta': hoy.isoformat(),
        }

    dias = (limite - hoy).days
    if dias < 0:
        return {
            'nivel': 'ROJO',
            'tipo': 'VENCIDO',
            'mensaje': f"Entregable vencido hace {abs(dias)} día(s): {entregable.get('titulo') or entregable.get('tipo')}",
            'entregable_id': entregable.get('id'),
            'coordinador_id': entregable.get('coordinador_id'),
            'fecha_alerta': hoy.isoformat(),
        }
    if dias in {0, 1, 3, 5}:
        return {
            'nivel': 'AMARILLO' if dias > 0 else 'ROJO',
            'tipo': f'VENCE_EN_{dias}_DIAS',
            'mensaje': f"Entregable {entregable.get('titulo') or entregable.get('tipo')} vence {'hoy' if dias == 0 else f'en {dias} día(s)'}",
            'entregable_id': entregable.get('id'),
            'coordinador_id': entregable.get('coordinador_id'),
            'fecha_alerta': hoy.isoformat(),
        }
    return None


def generar_alertas(entregables: list[dict[str, Any]]) -> list[dict[str, Any]]:
    hoy = date.today()
    alertas = []
    for entregable in entregables:
        alerta = alerta_por_entregable(entregable, hoy)
        if alerta:
            alerta['entregable'] = entregable
            alertas.append(alerta)
    return alertas


def dashboard_pedagogico(repo, periodo: str | None = None) -> dict[str, Any]:
    periodo = periodo or periodo_actual()
    coordinadores = repo.listar_coordinadores()
    entregables = repo.listar_entregables(periodo=periodo)
    documentos = repo.fetch_all("SELECT * FROM gp_documentos WHERE activo = 1 ORDER BY fecha_carga DESC")
    alertas = generar_alertas(entregables)

    total_entregables = len(entregables)
    entregables_estado = [estado_calculado(item) for item in entregables]
    pendientes = sum(1 for estado in entregables_estado if estado in {'Pendiente', 'En proceso'})
    vencidos = sum(1 for estado in entregables_estado if estado == 'Vencido')
    aprobados = sum(1 for estado in entregables_estado if estado == 'Aprobado')
    por_revisar = sum(1 for doc in documentos if str(doc.get('estado') or '').lower() in {'cargado', 'en revisión', 'en revision'})
    cumplimiento = round((aprobados / total_entregables) * 100, 1) if total_entregables else 0

    return {
        'periodo': periodo,
        'total_coordinadores': len(coordinadores),
        'total_entregables_mes': total_entregables,
        'entregables_pendientes': pendientes,
        'entregables_vencidos': vencidos,
        'documentos_por_revisar': por_revisar,
        'cumplimiento_general': cumplimiento,
        'alertas_criticas': sum(1 for a in alertas if a.get('nivel') == 'ROJO'),
        'alertas': alertas[:15],
        'resumen_estados': {
            'Pendiente': entregables_estado.count('Pendiente'),
            'En proceso': entregables_estado.count('En proceso'),
            'Cargado': entregables_estado.count('Cargado'),
            'En revisión': entregables_estado.count('En revisión'),
            'Aprobado': entregables_estado.count('Aprobado'),
            'Devuelto': entregables_estado.count('Devuelto'),
            'Vencido': vencidos,
            'Cumplido fuera de fecha': entregables_estado.count('Cumplido fuera de fecha'),
        }
    }


def reporte_mensual(repo, periodo: str | None = None) -> dict[str, Any]:
    periodo = periodo or periodo_actual()
    coordinadores = repo.listar_coordinadores()
    entregables = repo.listar_entregables(periodo=periodo)
    documentos = repo.fetch_all(
        """
        SELECT d.*, c.nombre AS coordinador_nombre, e.titulo AS entregable_titulo
        FROM gp_documentos d
        LEFT JOIN gp_coordinadores c ON c.id = d.coordinador_id
        LEFT JOIN gp_entregables e ON e.id = d.entregable_id
        WHERE d.activo = 1 AND substr(d.fecha_carga, 1, 7) = ?
        ORDER BY d.fecha_carga DESC
        """,
        (periodo,),
    )
    alertas = generar_alertas(entregables)

    por_coordinador = []
    for coord in coordinadores:
        cid = coord.get('id')
        e_coord = [e for e in entregables if e.get('coordinador_id') == cid]
        estados = [estado_calculado(e) for e in e_coord]
        total = len(e_coord)
        aprobados = estados.count('Aprobado')
        por_coordinador.append({
            'coordinador_id': cid,
            'coordinador': coord.get('nombre'),
            'total_entregables': total,
            'aprobados': aprobados,
            'pendientes': sum(1 for e in estados if e in {'Pendiente', 'En proceso'}),
            'vencidos': estados.count('Vencido'),
            'cumplimiento': round((aprobados / total) * 100, 1) if total else 0,
        })

    resumen_tipos = {}
    for e in entregables:
        tipo = e.get('tipo') or 'Sin tipo'
        estado = estado_calculado(e)
        if tipo not in resumen_tipos:
            resumen_tipos[tipo] = {'tipo': tipo, 'total': 0, 'aprobados': 0, 'pendientes': 0, 'vencidos': 0, 'devueltos': 0, 'cargados_revision': 0}
        item = resumen_tipos[tipo]
        item['total'] += 1
        if estado == 'Aprobado':
            item['aprobados'] += 1
        elif estado == 'Vencido':
            item['vencidos'] += 1
        elif estado == 'Devuelto':
            item['devueltos'] += 1
        elif estado in {'Cargado', 'En revisión'}:
            item['cargados_revision'] += 1
        else:
            item['pendientes'] += 1

    entregables_detalle = []
    for e in entregables:
        entregables_detalle.append({**e, 'estado_calculado': estado_calculado(e)})

    return {
        'periodo': periodo,
        'dashboard': dashboard_pedagogico(repo, periodo),
        'por_coordinador': por_coordinador,
        'por_tipo': sorted(resumen_tipos.values(), key=lambda x: x['tipo']),
        'entregables': entregables_detalle,
        'entregables_vencidos': [e for e in entregables_detalle if e.get('estado_calculado') == 'Vencido'],
        'documentos_aprobados': [d for d in documentos if str(d.get('estado')).lower() == 'aprobado'],
        'documentos_devueltos': [d for d in documentos if str(d.get('estado')).lower() == 'devuelto'],
        'alertas': alertas,
    }
