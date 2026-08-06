"""Esquema del Motor Inteligente de Gestión del Proyecto.

El motor mantiene referencias a los módulos fuente; no replica información
misional ni sustituye las aprobaciones profesionales.
"""
from __future__ import annotations

SCHEMA_VERSION = 1

SCHEMA_SQL = r"""
CREATE TABLE IF NOT EXISTS mgp_reglas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fundacion_id INTEGER NOT NULL,
    codigo TEXT NOT NULL,
    nombre TEXT NOT NULL,
    descripcion TEXT,
    tipo_regla TEXT DEFAULT 'PRIORIZACION',
    modulo_origen TEXT,
    condicion_json TEXT,
    accion_json TEXT,
    prioridad_base INTEGER DEFAULT 10,
    activa INTEGER DEFAULT 1,
    orden INTEGER DEFAULT 100,
    creada_por INTEGER,
    actualizada_por INTEGER,
    fecha_creacion TEXT NOT NULL,
    fecha_actualizacion TEXT NOT NULL,
    UNIQUE(fundacion_id, codigo)
);
CREATE INDEX IF NOT EXISTS idx_mgp_reglas_fund ON mgp_reglas(fundacion_id, activa, orden);

CREATE TABLE IF NOT EXISTS mgp_tareas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fundacion_id INTEGER NOT NULL,
    expediente_id INTEGER,
    unidad_id INTEGER,
    unidad_nombre TEXT,
    unidad_clave TEXT,
    fuente_modulo TEXT NOT NULL,
    fuente_tabla TEXT NOT NULL,
    fuente_id INTEGER,
    fuente_clave TEXT NOT NULL,
    tipo_tarea TEXT DEFAULT 'ENTREGABLE',
    componente TEXT,
    titulo TEXT NOT NULL,
    descripcion TEXT,
    fecha_inicio TEXT,
    fecha_limite TEXT,
    fecha_finalizacion TEXT,
    estado TEXT DEFAULT 'PENDIENTE',
    prioridad TEXT DEFAULT 'MEDIA',
    puntaje_prioridad INTEGER DEFAULT 0,
    responsable_id INTEGER,
    responsable_nombre TEXT,
    revisor_id INTEGER,
    revisor_nombre TEXT,
    aprobador_id INTEGER,
    aprobador_nombre TEXT,
    requiere_evidencia INTEGER DEFAULT 0,
    evidencias_total INTEGER DEFAULT 0,
    bloqueada INTEGER DEFAULT 0,
    motivo_bloqueo TEXT,
    regla_id INTEGER,
    metadata_json TEXT,
    activa INTEGER DEFAULT 1,
    creada_por INTEGER,
    actualizada_por INTEGER,
    fecha_creacion TEXT NOT NULL,
    fecha_actualizacion TEXT NOT NULL,
    UNIQUE(fundacion_id, fuente_tabla, fuente_clave),
    FOREIGN KEY(expediente_id) REFERENCES giu_expedientes_uca(id),
    FOREIGN KEY(regla_id) REFERENCES mgp_reglas(id)
);
CREATE INDEX IF NOT EXISTS idx_mgp_tareas_fund ON mgp_tareas(fundacion_id, activa, estado, fecha_limite);
CREATE INDEX IF NOT EXISTS idx_mgp_tareas_exp ON mgp_tareas(fundacion_id, expediente_id, estado);
CREATE INDEX IF NOT EXISTS idx_mgp_tareas_resp ON mgp_tareas(fundacion_id, responsable_id, estado);
CREATE INDEX IF NOT EXISTS idx_mgp_tareas_unidad ON mgp_tareas(fundacion_id, unidad_clave, estado);

CREATE TABLE IF NOT EXISTS mgp_dependencias (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fundacion_id INTEGER NOT NULL,
    tarea_id INTEGER NOT NULL,
    depende_de_tarea_id INTEGER NOT NULL,
    tipo TEXT DEFAULT 'FIN_A_INICIO',
    obligatoria INTEGER DEFAULT 1,
    observaciones TEXT,
    creada_por INTEGER,
    fecha_creacion TEXT NOT NULL,
    UNIQUE(fundacion_id, tarea_id, depende_de_tarea_id),
    FOREIGN KEY(tarea_id) REFERENCES mgp_tareas(id),
    FOREIGN KEY(depende_de_tarea_id) REFERENCES mgp_tareas(id)
);
CREATE INDEX IF NOT EXISTS idx_mgp_dep_tarea ON mgp_dependencias(fundacion_id, tarea_id);

CREATE TABLE IF NOT EXISTS mgp_recordatorios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fundacion_id INTEGER NOT NULL,
    tarea_id INTEGER NOT NULL,
    tipo TEXT DEFAULT 'VENCIMIENTO',
    nivel TEXT DEFAULT 'INFO',
    titulo TEXT NOT NULL,
    mensaje TEXT NOT NULL,
    fecha_programada TEXT,
    estado TEXT DEFAULT 'PENDIENTE',
    destinatario_id INTEGER,
    destinatario_nombre TEXT,
    leido INTEGER DEFAULT 0,
    fecha_lectura TEXT,
    creado_en TEXT NOT NULL,
    actualizado_en TEXT NOT NULL,
    UNIQUE(fundacion_id, tarea_id, tipo, fecha_programada),
    FOREIGN KEY(tarea_id) REFERENCES mgp_tareas(id)
);
CREATE INDEX IF NOT EXISTS idx_mgp_recordatorios_fund ON mgp_recordatorios(fundacion_id, estado, fecha_programada);

CREATE TABLE IF NOT EXISTS mgp_productos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fundacion_id INTEGER NOT NULL,
    expediente_id INTEGER,
    periodo TEXT NOT NULL,
    tipo_producto TEXT NOT NULL,
    nombre_archivo TEXT NOT NULL,
    ruta_archivo TEXT NOT NULL,
    mime_type TEXT,
    tamano_bytes INTEGER DEFAULT 0,
    sha256 TEXT NOT NULL,
    estado TEXT DEFAULT 'BORRADOR',
    requiere_revision INTEGER DEFAULT 1,
    plantilla_documento_id INTEGER,
    plantilla_version_id INTEGER,
    resumen_json TEXT,
    generado_por INTEGER,
    revisado_por INTEGER,
    aprobado_por INTEGER,
    fecha_generacion TEXT NOT NULL,
    fecha_revision TEXT,
    fecha_aprobacion TEXT,
    FOREIGN KEY(expediente_id) REFERENCES giu_expedientes_uca(id)
);
CREATE INDEX IF NOT EXISTS idx_mgp_productos_fund ON mgp_productos(fundacion_id, periodo, estado);
CREATE INDEX IF NOT EXISTS idx_mgp_productos_exp ON mgp_productos(fundacion_id, expediente_id, periodo);

CREATE TABLE IF NOT EXISTS mgp_cierres_mensuales (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fundacion_id INTEGER NOT NULL,
    expediente_id INTEGER,
    periodo TEXT NOT NULL,
    estado TEXT DEFAULT 'BORRADOR',
    tareas_total INTEGER DEFAULT 0,
    tareas_completas INTEGER DEFAULT 0,
    tareas_pendientes INTEGER DEFAULT 0,
    tareas_vencidas INTEGER DEFAULT 0,
    alertas_total INTEGER DEFAULT 0,
    productos_total INTEGER DEFAULT 0,
    porcentaje_cumplimiento REAL DEFAULT 0,
    observaciones TEXT,
    preparado_por INTEGER,
    revisado_por INTEGER,
    aprobado_por INTEGER,
    fecha_preparacion TEXT NOT NULL,
    fecha_revision TEXT,
    fecha_aprobacion TEXT,
    fecha_cierre TEXT,
    UNIQUE(fundacion_id, expediente_id, periodo),
    FOREIGN KEY(expediente_id) REFERENCES giu_expedientes_uca(id)
);
CREATE INDEX IF NOT EXISTS idx_mgp_cierres_fund ON mgp_cierres_mensuales(fundacion_id, periodo, estado);

CREATE TABLE IF NOT EXISTS mgp_auditoria (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fundacion_id INTEGER NOT NULL,
    usuario_id INTEGER,
    usuario TEXT,
    accion TEXT NOT NULL,
    entidad TEXT NOT NULL,
    entidad_id INTEGER,
    detalle_json TEXT,
    fecha TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_mgp_auditoria_fund ON mgp_auditoria(fundacion_id, fecha, accion);

CREATE TABLE IF NOT EXISTS mgp_schema_version (
    id INTEGER PRIMARY KEY CHECK(id=1),
    version INTEGER NOT NULL,
    fecha_actualizacion TEXT NOT NULL
);
"""

DEFAULT_RULES = [
    {
        "codigo": "VENCIDA_CRITICA",
        "nombre": "Tarea vencida",
        "descripcion": "Eleva a crítica una tarea abierta con fecha vencida.",
        "tipo_regla": "PRIORIZACION",
        "prioridad_base": 75,
        "orden": 10,
        "condicion": {"vencida": True},
        "accion": {"prioridad": "CRITICA", "recordatorio": True},
    },
    {
        "codigo": "PROXIMA_48H",
        "nombre": "Vence en 48 horas",
        "descripcion": "Prioriza entregables próximos a vencer.",
        "tipo_regla": "PRIORIZACION",
        "prioridad_base": 45,
        "orden": 20,
        "condicion": {"dias_restantes_max": 2},
        "accion": {"prioridad": "ALTA", "recordatorio": True},
    },
    {
        "codigo": "PROXIMA_7_DIAS",
        "nombre": "Vence durante la semana",
        "descripcion": "Advierte tareas con vencimiento dentro de siete días.",
        "tipo_regla": "PRIORIZACION",
        "prioridad_base": 25,
        "orden": 30,
        "condicion": {"dias_restantes_max": 7},
        "accion": {"prioridad": "MEDIA", "recordatorio": True},
    },
    {
        "codigo": "EVIDENCIA_FALTANTE",
        "nombre": "Evidencia obligatoria faltante",
        "descripcion": "Aumenta prioridad si una actividad requiere evidencia y todavía no la tiene.",
        "tipo_regla": "CUMPLIMIENTO",
        "prioridad_base": 20,
        "orden": 40,
        "condicion": {"requiere_evidencia": True, "evidencias_total": 0},
        "accion": {"recordatorio": True},
    },
    {
        "codigo": "DEVUELTA_AJUSTES",
        "nombre": "Devuelta para ajustes",
        "descripcion": "Eleva prioridad cuando un producto o tarea fue devuelto.",
        "tipo_regla": "CUMPLIMIENTO",
        "prioridad_base": 35,
        "orden": 50,
        "condicion": {"estado": "DEVUELTA"},
        "accion": {"prioridad": "ALTA", "recordatorio": True},
    },
    {
        "codigo": "DEPENDENCIA_BLOQUEADA",
        "nombre": "Dependencia pendiente",
        "descripcion": "Marca la tarea como bloqueada cuando una dependencia obligatoria sigue abierta.",
        "tipo_regla": "DEPENDENCIA",
        "prioridad_base": 25,
        "orden": 60,
        "condicion": {"dependencia_abierta": True},
        "accion": {"bloquear": True, "recordatorio": True},
    },
]
