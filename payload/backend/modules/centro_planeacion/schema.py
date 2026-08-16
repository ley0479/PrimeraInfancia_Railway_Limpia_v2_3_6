"""Esquema del Centro Inteligente de Planeación y Calendario Operativo.

El calendario histórico conserva las fechas y estados básicos. Estas tablas
agregan metadatos, reglas, dependencias, documentos y trazabilidad sin copiar
los registros misionales de los módulos fuente.
"""
from __future__ import annotations

SCHEMA_VERSION = 1

SCHEMA_SQL = r"""
CREATE TABLE IF NOT EXISTS cpo_schema_version (
    id INTEGER PRIMARY KEY CHECK(id=1),
    version INTEGER NOT NULL,
    fecha_actualizacion TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS cpo_reglas_operativas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fundacion_id INTEGER NOT NULL,
    codigo TEXT NOT NULL,
    nombre TEXT NOT NULL,
    descripcion TEXT,
    componente TEXT,
    tipo_actividad TEXT,
    rol_responsable TEXT,
    dias_recordatorio_json TEXT DEFAULT '[7,2,0]',
    documentos_json TEXT DEFAULT '[]',
    evidencias_json TEXT DEFAULT '[]',
    condicion_cierre_json TEXT DEFAULT '{}',
    prioridad_base TEXT DEFAULT 'MEDIA',
    activa INTEGER DEFAULT 1,
    creada_por INTEGER,
    actualizada_por INTEGER,
    fecha_creacion TEXT NOT NULL,
    fecha_actualizacion TEXT NOT NULL,
    UNIQUE(fundacion_id,codigo)
);
CREATE INDEX IF NOT EXISTS idx_cpo_reglas_fund ON cpo_reglas_operativas(fundacion_id,activa,componente);

CREATE TABLE IF NOT EXISTS cpo_actividad_metadata (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fundacion_id INTEGER NOT NULL,
    entregable_id INTEGER NOT NULL,
    expediente_uca_id INTEGER,
    unidad_id INTEGER,
    unidad_nombre TEXT,
    unidad_clave TEXT,
    componente TEXT,
    tipo_actividad TEXT,
    fuente_modulo TEXT NOT NULL,
    fuente_tabla TEXT NOT NULL,
    fuente_id INTEGER,
    fuente_clave TEXT NOT NULL,
    rol_responsable TEXT,
    revisor_id INTEGER,
    revisor_nombre TEXT,
    aprobador_id INTEGER,
    aprobador_nombre TEXT,
    regla_id INTEGER,
    estado_flujo TEXT DEFAULT 'PROGRAMADA',
    porcentaje REAL DEFAULT 0,
    bloqueada INTEGER DEFAULT 0,
    motivo_bloqueo TEXT,
    requiere_agenda INTEGER DEFAULT 1,
    requiere_acta INTEGER DEFAULT 0,
    requiere_listado INTEGER DEFAULT 0,
    requiere_informe INTEGER DEFAULT 0,
    requiere_evidencias INTEGER DEFAULT 0,
    metadata_json TEXT DEFAULT '{}',
    activa INTEGER DEFAULT 1,
    creada_por INTEGER,
    actualizada_por INTEGER,
    fecha_creacion TEXT NOT NULL,
    fecha_actualizacion TEXT NOT NULL,
    UNIQUE(fundacion_id,entregable_id),
    UNIQUE(fundacion_id,fuente_tabla,fuente_clave),
    FOREIGN KEY(entregable_id) REFERENCES calendario_entregables(id),
    FOREIGN KEY(regla_id) REFERENCES cpo_reglas_operativas(id)
);
CREATE INDEX IF NOT EXISTS idx_cpo_meta_fund ON cpo_actividad_metadata(fundacion_id,activa,estado_flujo);
CREATE INDEX IF NOT EXISTS idx_cpo_meta_uca ON cpo_actividad_metadata(fundacion_id,unidad_clave,estado_flujo);
CREATE INDEX IF NOT EXISTS idx_cpo_meta_resp ON cpo_actividad_metadata(fundacion_id,rol_responsable,estado_flujo);

CREATE TABLE IF NOT EXISTS cpo_dependencias (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fundacion_id INTEGER NOT NULL,
    actividad_id INTEGER NOT NULL,
    depende_de_actividad_id INTEGER NOT NULL,
    obligatoria INTEGER DEFAULT 1,
    tipo TEXT DEFAULT 'FIN_A_INICIO',
    observaciones TEXT,
    creada_por INTEGER,
    fecha_creacion TEXT NOT NULL,
    UNIQUE(fundacion_id,actividad_id,depende_de_actividad_id),
    FOREIGN KEY(actividad_id) REFERENCES cpo_actividad_metadata(id),
    FOREIGN KEY(depende_de_actividad_id) REFERENCES cpo_actividad_metadata(id)
);
CREATE INDEX IF NOT EXISTS idx_cpo_dep_act ON cpo_dependencias(fundacion_id,actividad_id);

CREATE TABLE IF NOT EXISTS cpo_documentos_preparados (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fundacion_id INTEGER NOT NULL,
    actividad_id INTEGER NOT NULL,
    tipo_documento TEXT NOT NULL,
    nombre_archivo TEXT NOT NULL,
    ruta_archivo TEXT NOT NULL,
    mime_type TEXT,
    tamano_bytes INTEGER DEFAULT 0,
    sha256 TEXT NOT NULL,
    estado TEXT DEFAULT 'BORRADOR',
    plantilla_codigo TEXT,
    plantilla_version TEXT,
    generado_por INTEGER,
    revisado_por INTEGER,
    aprobado_por INTEGER,
    fecha_generacion TEXT NOT NULL,
    fecha_revision TEXT,
    fecha_aprobacion TEXT,
    UNIQUE(fundacion_id,actividad_id,tipo_documento,nombre_archivo),
    FOREIGN KEY(actividad_id) REFERENCES cpo_actividad_metadata(id)
);
CREATE INDEX IF NOT EXISTS idx_cpo_docs_fund ON cpo_documentos_preparados(fundacion_id,actividad_id,estado);

CREATE TABLE IF NOT EXISTS cpo_notificaciones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fundacion_id INTEGER NOT NULL,
    actividad_id INTEGER NOT NULL,
    destinatario_id INTEGER,
    destinatario_rol TEXT,
    nivel TEXT DEFAULT 'INFO',
    tipo TEXT DEFAULT 'VENCIMIENTO',
    titulo TEXT NOT NULL,
    mensaje TEXT NOT NULL,
    fecha_programada TEXT,
    estado TEXT DEFAULT 'PENDIENTE',
    leida INTEGER DEFAULT 0,
    fecha_lectura TEXT,
    fecha_creacion TEXT NOT NULL,
    UNIQUE(fundacion_id,actividad_id,destinatario_id,destinatario_rol,tipo,fecha_programada),
    FOREIGN KEY(actividad_id) REFERENCES cpo_actividad_metadata(id)
);
CREATE INDEX IF NOT EXISTS idx_cpo_notif_fund ON cpo_notificaciones(fundacion_id,estado,fecha_programada);

CREATE TABLE IF NOT EXISTS cpo_auditoria (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fundacion_id INTEGER NOT NULL,
    usuario_id INTEGER,
    usuario TEXT,
    accion TEXT NOT NULL,
    entidad TEXT NOT NULL,
    entidad_id INTEGER,
    detalle_json TEXT DEFAULT '{}',
    fecha TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_cpo_audit_fund ON cpo_auditoria(fundacion_id,fecha);
"""
