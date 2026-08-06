from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import date, datetime
from typing import Any, Iterable

PHASES = (
    ("PREPARATORIA", "Fase I · Preparatoria", 1),
    ("IMPLEMENTACION", "Fase II · Implementación", 2),
    ("CIERRE", "Fase III · Cierre", 3),
    ("TRANSVERSAL", "Gestión transversal", 4),
)

ROUTE_CATALOG = [
    {
        "codigo": "P1_CONCERTACION",
        "fase": "PREPARATORIA",
        "orden": 10,
        "titulo": "Concertación con comunidades",
        "descripcion": "Registrar acuerdos, sesiones, actores y evidencias del diálogo intercultural cuando aplique.",
        "componente": "Familia, Comunidad y Redes Sociales",
        "obligatoria": 0,
        "requiere_evidencia": 1,
        "roles": ["SUPERADMIN", "GERENTE", "COORDINADOR", "PSICOSOCIAL"],
        "evidencias": ["Acta de concertación", "Listado de asistencia", "Acuerdos"],
    },
    {
        "codigo": "P1_TALENTO_INDUCCION",
        "fase": "PREPARATORIA",
        "orden": 20,
        "titulo": "Conformación e inducción del talento humano intercultural",
        "descripcion": "Verificar perfiles, soportes, aprobación, contratación, inducción y reinducción.",
        "componente": "Talento Humano",
        "obligatoria": 1,
        "requiere_evidencia": 1,
        "roles": ["SUPERADMIN", "GERENTE", "COORDINADOR", "AUXILIAR_ADMINISTRATIVO"],
        "evidencias": ["Relación de personal", "Acta de inducción", "Listado de asistencia"],
    },
    {
        "codigo": "P1_ARTICULACION",
        "fase": "PREPARATORIA",
        "orden": 30,
        "titulo": "Gestión y articulación interinstitucional",
        "descripcion": "Identificar actores del territorio, rutas, acuerdos y compromisos intersectoriales.",
        "componente": "Administrativo y de Gestión",
        "obligatoria": 1,
        "requiere_evidencia": 1,
        "roles": ["SUPERADMIN", "GERENTE", "COORDINADOR", "PSICOSOCIAL"],
        "evidencias": ["Directorio territorial", "Acta", "Plan de articulación"],
    },
    {
        "codigo": "P1_ESPACIOS_DOTACION",
        "fase": "PREPARATORIA",
        "orden": 40,
        "titulo": "Gestión de espacios físicos y dotación",
        "descripcion": "Comprobar infraestructura, accesibilidad, seguridad, dotación y condiciones de operación.",
        "componente": "Ambientes Educativos y Protectores",
        "obligatoria": 1,
        "requiere_evidencia": 1,
        "roles": ["SUPERADMIN", "GERENTE", "COORDINADOR", "AUXILIAR_ADMINISTRATIVO"],
        "evidencias": ["Lista de chequeo", "Registro fotográfico", "Inventario"],
    },
    {
        "codigo": "P1_FORMALIZACION_POBLACION",
        "fase": "PREPARATORIA",
        "orden": 50,
        "titulo": "Formalización de la población a atender",
        "descripcion": "Controlar focalización, preinscripción, cupos, inscripción, documentos y novedades.",
        "componente": "Administrativo y de Gestión",
        "obligatoria": 1,
        "requiere_evidencia": 1,
        "roles": ["SUPERADMIN", "GERENTE", "COORDINADOR", "AUXILIAR_ADMINISTRATIVO"],
        "evidencias": ["Listado de participantes", "Matriz documental", "Novedades"],
    },
    {
        "codigo": "P1_PRESUPUESTO",
        "fase": "PREPARATORIA",
        "orden": 60,
        "titulo": "Elaboración y presentación del presupuesto",
        "descripcion": "Relacionar presupuesto, canasta, aprobación y observaciones del comité cuando aplique.",
        "componente": "Administrativo y de Gestión",
        "obligatoria": 0,
        "requiere_evidencia": 1,
        "roles": ["SUPERADMIN", "GERENTE", "AUXILIAR_ADMINISTRATIVO"],
        "evidencias": ["Presupuesto", "Acta de aprobación"],
    },
    {
        "codigo": "P1_PROVEEDORES_ALIMENTOS",
        "fase": "PREPARATORIA",
        "orden": 70,
        "titulo": "Selección de proveedores de alimentos",
        "descripcion": "Controlar selección, requisitos, compras locales y actualización de proveedores.",
        "componente": "Salud y Nutrición",
        "obligatoria": 0,
        "requiere_evidencia": 1,
        "roles": ["SUPERADMIN", "GERENTE", "NUTRICIONISTA", "AUXILIAR_ADMINISTRATIVO"],
        "evidencias": ["Listado de proveedores", "RUT", "Soportes sanitarios"],
    },
    {
        "codigo": "P1_CONTRAPARTIDA",
        "fase": "PREPARATORIA",
        "orden": 80,
        "titulo": "Plan de contrapartida o valor técnico agregado",
        "descripcion": "Registrar el plan, actividades, recursos, responsables y aprobación cuando aplique.",
        "componente": "Administrativo y de Gestión",
        "obligatoria": 0,
        "requiere_evidencia": 1,
        "roles": ["SUPERADMIN", "GERENTE", "AUXILIAR_ADMINISTRATIVO"],
        "evidencias": ["Plan de contrapartida", "Acta de aprobación"],
    },
    {
        "codigo": "P2_SOCIALIZACION",
        "fase": "IMPLEMENTACION",
        "orden": 110,
        "titulo": "Jornada de socialización y control social",
        "descripcion": "Registrar la jornada, participantes, derechos, deberes, comité de control social y compromisos.",
        "componente": "Familia, Comunidad y Redes Sociales",
        "obligatoria": 1,
        "requiere_evidencia": 1,
        "roles": ["SUPERADMIN", "GERENTE", "COORDINADOR", "PSICOSOCIAL", "DOCENTE"],
        "evidencias": ["Acta", "Listado de asistencia", "Registro fotográfico"],
    },
    {
        "codigo": "P2_CARACTERIZACION",
        "fase": "IMPLEMENTACION",
        "orden": 120,
        "titulo": "Proceso de caracterización",
        "descripcion": "Consolidar y analizar la caracterización de participantes, familias, comunidad y territorio.",
        "componente": "Familia, Comunidad y Redes Sociales",
        "obligatoria": 1,
        "requiere_evidencia": 1,
        "roles": ["SUPERADMIN", "GERENTE", "COORDINADOR", "PSICOSOCIAL", "DOCENTE", "NUTRICIONISTA"],
        "evidencias": ["Ficha de caracterización", "Informe de análisis"],
    },
    {
        "codigo": "P2_OCHO_PLANES",
        "fase": "IMPLEMENTACION",
        "orden": 130,
        "titulo": "Planeación integrada de los ocho planes",
        "descripcion": "Controlar responsables, metas, cronogramas, indicadores y evidencias de los ocho planes operativos.",
        "componente": "Administrativo y de Gestión",
        "obligatoria": 1,
        "requiere_evidencia": 1,
        "roles": ["SUPERADMIN", "GERENTE", "COORDINADOR", "DOCENTE", "NUTRICIONISTA", "PSICOSOCIAL", "AUXILIAR_ADMINISTRATIVO"],
        "evidencias": ["Planes aprobados", "Cronograma", "Matriz de responsables"],
    },
    {
        "codigo": "P2_BITACORA_MENSUAL",
        "fase": "IMPLEMENTACION",
        "orden": 140,
        "titulo": "Bitácora mensual por UCA",
        "descripcion": "Organizar estrategias, tiempos, responsables, novedades y evidencias de la atención mensual.",
        "componente": "Proceso Pedagógico",
        "obligatoria": 1,
        "requiere_evidencia": 1,
        "roles": ["SUPERADMIN", "GERENTE", "COORDINADOR", "DOCENTE"],
        "evidencias": ["Bitácora mensual", "Aprobación"],
    },
    {
        "codigo": "P2_EJECUCION_COMPONENTES",
        "fase": "IMPLEMENTACION",
        "orden": 150,
        "titulo": "Ejecución de los seis componentes de calidad",
        "descripcion": "Consolidar avances, productos, evidencias, alertas y cumplimiento por componente.",
        "componente": "Transversal",
        "obligatoria": 1,
        "requiere_evidencia": 1,
        "roles": ["SUPERADMIN", "GERENTE", "COORDINADOR", "DOCENTE", "NUTRICIONISTA", "PSICOSOCIAL", "AUXILIAR_ADMINISTRATIVO"],
        "evidencias": ["Informe de ejecución", "Matriz de componentes"],
    },
    {
        "codigo": "P2_SEGUIMIENTO",
        "fase": "IMPLEMENTACION",
        "orden": 160,
        "titulo": "Seguimiento, alertas y planes de mejora",
        "descripcion": "Registrar verificaciones, hallazgos, alertas, acciones correctivas y seguimiento de compromisos.",
        "componente": "Administrativo y de Gestión",
        "obligatoria": 1,
        "requiere_evidencia": 1,
        "roles": ["SUPERADMIN", "GERENTE", "COORDINADOR"],
        "evidencias": ["Informe de seguimiento", "Plan de mejora", "Acta de comité"],
    },
    {
        "codigo": "P3_CIERRE_DOCUMENTAL",
        "fase": "CIERRE",
        "orden": 210,
        "titulo": "Cierre documental y expediente de la vigencia",
        "descripcion": "Verificar entregables, índices, expedientes, planes, soportes y reportes de la vigencia.",
        "componente": "Administrativo y de Gestión",
        "obligatoria": 1,
        "requiere_evidencia": 1,
        "roles": ["SUPERADMIN", "GERENTE", "COORDINADOR", "AUXILIAR_ADMINISTRATIVO"],
        "evidencias": ["Checklist de cierre", "Índice documental", "Acta"],
    },
    {
        "codigo": "P3_TRANSFERENCIA_CUSTODIA",
        "fase": "CIERRE",
        "orden": 220,
        "titulo": "Transferencia y custodia de información",
        "descripcion": "Registrar la entrega inventariada, custodios, receptor, integridad y continuidad de la atención.",
        "componente": "Administrativo y de Gestión",
        "obligatoria": 1,
        "requiere_evidencia": 1,
        "roles": ["SUPERADMIN", "GERENTE", "COORDINADOR", "AUXILIAR_ADMINISTRATIVO"],
        "evidencias": ["Acta de entrega", "Inventario documental", "Manifiesto de integridad"],
    },
    {
        "codigo": "P3_INVENTARIO_DOTACION",
        "fase": "CIERRE",
        "orden": 230,
        "titulo": "Inventario, limpieza y disposición de dotación",
        "descripcion": "Consolidar inventario, estado, limpieza, desinfección, control de plagas y disposición.",
        "componente": "Ambientes Educativos y Protectores",
        "obligatoria": 1,
        "requiere_evidencia": 1,
        "roles": ["SUPERADMIN", "GERENTE", "COORDINADOR", "AUXILIAR_ADMINISTRATIVO"],
        "evidencias": ["Inventario", "Registro de limpieza", "Acta de entrega"],
    },
    {
        "codigo": "P3_CIERRE_UCA",
        "fase": "CIERRE",
        "orden": 240,
        "titulo": "Cierre o continuidad de la UCA",
        "descripcion": "Registrar escenario de cierre, continuidad, cambio de operador o acto administrativo aplicable.",
        "componente": "Administrativo y de Gestión",
        "obligatoria": 1,
        "requiere_evidencia": 1,
        "roles": ["SUPERADMIN", "GERENTE", "COORDINADOR"],
        "evidencias": ["Acto o acta de cierre", "Decisión de continuidad"],
    },
    {
        "codigo": "T_FLEXIBILIZACION_EMERGENCIA",
        "fase": "TRANSVERSAL",
        "orden": 310,
        "titulo": "Flexibilización por emergencia o desastre",
        "descripcion": "Gestionar propuesta, comité extraordinario, aprobación, vigencia, ejecución y retorno a la operación normal.",
        "componente": "Transversal",
        "obligatoria": 0,
        "requiere_evidencia": 1,
        "roles": ["SUPERADMIN", "GERENTE", "COORDINADOR"],
        "evidencias": ["Propuesta de flexibilización", "Acta de comité", "Aprobación"],
    },
]

VALID_STATES = {
    "PENDIENTE",
    "EN_PROCESO",
    "PENDIENTE_EVIDENCIA",
    "PENDIENTE_REVISION",
    "DEVUELTA",
    "APROBADA",
    "CERRADA",
    "NO_APLICA",
    "VENCIDA",
}
COMPLETED_STATES = {"APROBADA", "CERRADA", "NO_APLICA"}

MODULE_LINKS = {
    "base_maestra": {"seccion": "base-maestra", "titulo": "Base Maestra"},
    "pedagogico": {"seccion": "gestion-pedagogica", "titulo": "Gestión Pedagógica"},
    "salud_nutricion": {"seccion": "salud-nutricion", "titulo": "Salud y Nutrición"},
    "ram_rpp_bienestarina": {"seccion": "formatos", "titulo": "RAM, RPP y Bienestarina"},
    "talento_humano": {"seccion": "talento", "titulo": "Talento Humano"},
    "calendario": {"seccion": "calendario-inteligente", "titulo": "Calendario Inteligente"},
    "documentos_evidencias": {"seccion": "expediente-operativo-uca", "titulo": "Documentos y Evidencias"},
    "cronograma": {"seccion": "calendario-inteligente", "titulo": "Cronograma y Calendario"},
    "reportes_indicadores": {"seccion": "reportes-gerenciales", "titulo": "Reportes e Indicadores"},
    "reportes": {"seccion": "reportes-gerenciales", "titulo": "Reportes Gerenciales"},
    "manual": {"seccion": "manual-operativo", "titulo": "Manual Operativo"},
}


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def normalize_text(value: Any) -> str:
    text = str(value or "").strip()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^A-Za-z0-9]+", " ", text).strip().upper()
    return " ".join(text.split())


def unit_key(value: Any) -> str:
    normalized = normalize_text(value)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:24] if normalized else ""


def parse_json(value: Any, fallback: Any = None) -> Any:
    if value in (None, ""):
        return fallback
    if isinstance(value, (dict, list, tuple, int, float, bool)):
        return value
    try:
        return json.loads(str(value))
    except Exception:
        return fallback


def json_dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def valid_date(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def safe_state(value: Any) -> str:
    state = normalize_text(value).replace(" ", "_") or "PENDIENTE"
    return state if state in VALID_STATES else "PENDIENTE"


def completion_percentage(rows: Iterable[dict[str, Any]]) -> float:
    items = [dict(row) for row in rows]
    required = [row for row in items if int(row.get("obligatoria") or 0) == 1]
    base = required or items
    if not base:
        return 0.0
    completed = sum(1 for row in base if safe_state(row.get("estado")) in COMPLETED_STATES)
    return round((completed / len(base)) * 100.0, 2)


def semaphore(progress: float, overdue: int = 0, blocked: int = 0) -> str:
    if blocked or overdue:
        return "ROJO"
    if progress >= 85:
        return "VERDE"
    if progress >= 50:
        return "AMARILLO"
    return "ROJO"


def route_catalog_hash() -> str:
    payload = json.dumps(ROUTE_CATALOG, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def file_sha256(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
