from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

ACTIVITY_STATES = ['PROGRAMADO', 'PENDIENTE', 'CUMPLIDO', 'VENCIDO', 'REPROGRAMADO', 'ANULADO']
ACTIVITY_TYPES = [
    'Entrega de planeación', 'Informe pedagógico', 'Encuentro comunitario', 'Encuentro en el hogar',
    'Visita al hogar', 'Carga de evidencias', 'Cuenta de cobro', 'Seguimiento nutricional',
    'Reunión de equipo', 'Entregables ICBF'
]


def current_period() -> str:
    return datetime.now().strftime('%Y-%m')


def parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(str(value)[:10], '%Y-%m-%d').date()
    except Exception:
        return None


def activity_state_calculated(item: dict[str, Any], today: date | None = None) -> str:
    today = today or date.today()
    estado = str(item.get('estado') or 'PROGRAMADO').upper()
    if estado in {'CUMPLIDO', 'ANULADO', 'REPROGRAMADO'}:
        return estado
    fecha = parse_date(item.get('fecha') or item.get('fecha_limite'))
    if fecha and fecha < today:
        return 'VENCIDO'
    if estado in ACTIVITY_STATES:
        return estado
    return 'PROGRAMADO'


def build_activity_alert(item: dict[str, Any], today: date | None = None) -> dict[str, Any] | None:
    today = today or date.today()
    estado = activity_state_calculated(item, today)
    if estado in {'CUMPLIDO', 'ANULADO'}:
        return None
    fecha = parse_date(item.get('fecha') or item.get('fecha_limite'))
    titulo = item.get('titulo') or item.get('tipo') or 'Actividad'
    if not fecha:
        return {
            'nivel': 'AMARILLO', 'tipo': 'SIN_FECHA', 'mensaje': f'Actividad sin fecha: {titulo}',
            'coordinador_id': item.get('coordinador_id'), 'entidad_id': item.get('id'), 'entidad_tipo': 'actividad',
            'fecha_alerta': today.isoformat()
        }
    dias = (fecha - today).days
    if dias < 0:
        return {
            'nivel': 'ROJO', 'tipo': 'ACTIVIDAD_VENCIDA', 'mensaje': f'Actividad vencida hace {abs(dias)} día(s): {titulo}',
            'coordinador_id': item.get('coordinador_id'), 'entidad_id': item.get('id'), 'entidad_tipo': 'actividad',
            'fecha_alerta': today.isoformat()
        }
    if dias in {0, 1, 3, 5}:
        return {
            'nivel': 'ROJO' if dias == 0 else 'AMARILLO',
            'tipo': 'ACTIVIDAD_PROXIMA',
            'mensaje': f'Actividad {titulo} vence {"hoy" if dias == 0 else f"en {dias} día(s)"}.',
            'coordinador_id': item.get('coordinador_id'), 'entidad_id': item.get('id'), 'entidad_tipo': 'actividad',
            'fecha_alerta': today.isoformat()
        }
    if item.get('evidencia_requerida') and estado != 'CUMPLIDO':
        return {
            'nivel': 'AMARILLO', 'tipo': 'EVIDENCIA_FALTANTE', 'mensaje': f'Evidencia pendiente para: {titulo}',
            'coordinador_id': item.get('coordinador_id'), 'entidad_id': item.get('id'), 'entidad_tipo': 'actividad',
            'fecha_alerta': today.isoformat()
        }
    return None


def generate_alerts_for_activities(activities: list[dict[str, Any]]) -> list[dict[str, Any]]:
    today = date.today()
    alerts = []
    for item in activities:
        alert = build_activity_alert(item, today)
        if alert:
            alert['actividad'] = item
            alerts.append(alert)
    return alerts


def dashboard(repo, periodo: str | None = None) -> dict[str, Any]:
    periodo = periodo or current_period()
    coordinadores = repo.list_coordinators_summary(periodo)
    actividades = repo.list_activities({'periodo': periodo})
    alertas = generate_alerts_for_activities(actividades)
    total = len(actividades)
    estados = [activity_state_calculated(x) for x in actividades]
    cumplidas = estados.count('CUMPLIDO')
    vencidas = estados.count('VENCIDO')
    pendientes = sum(1 for e in estados if e in {'PENDIENTE', 'PROGRAMADO', 'REPROGRAMADO'})
    cumplimiento = round((cumplidas / total) * 100, 1) if total else 0
    return {
        'periodo': periodo,
        'total_coordinadores': len(coordinadores),
        'total_actividades': total,
        'actividades_pendientes': pendientes,
        'actividades_vencidas': vencidas,
        'cumplimiento_general': cumplimiento,
        'alertas': alertas[:25],
        'coordinadores': coordinadores,
        'resumen_estados': {estado: estados.count(estado) for estado in ACTIVITY_STATES},
    }


def monthly_report(repo, periodo: str | None = None) -> dict[str, Any]:
    periodo = periodo or current_period()
    data = dashboard(repo, periodo)
    actividades = repo.list_activities({'periodo': periodo})
    por_tipo = {}
    for item in actividades:
        tipo = item.get('tipo') or 'Sin tipo'
        por_tipo.setdefault(tipo, {'total': 0, 'cumplidas': 0, 'vencidas': 0, 'pendientes': 0})
        estado = activity_state_calculated(item)
        por_tipo[tipo]['total'] += 1
        if estado == 'CUMPLIDO':
            por_tipo[tipo]['cumplidas'] += 1
        elif estado == 'VENCIDO':
            por_tipo[tipo]['vencidas'] += 1
        else:
            por_tipo[tipo]['pendientes'] += 1
    data['por_tipo'] = por_tipo
    data['actividades_criticas'] = [x for x in actividades if activity_state_calculated(x) == 'VENCIDO'][:50]
    return data
