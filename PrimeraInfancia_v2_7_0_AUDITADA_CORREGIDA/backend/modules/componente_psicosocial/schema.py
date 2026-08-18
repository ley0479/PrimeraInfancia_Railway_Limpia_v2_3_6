"""Esquema especializado del componente psicosocial.

El módulo no replica participantes ni actividades. Enlaza expedientes familiares,
actividades, compromisos y alertas del componente Familia, Comunidad y Redes,
y agrega la caracterización y el plan profesional que no existían allí.
"""
from __future__ import annotations

SCHEMA_VERSION = 1

SCHEMA_SQL = r"""
CREATE TABLE IF NOT EXISTS ps_schema_version (
    id INTEGER PRIMARY KEY CHECK(id=1),
    version INTEGER NOT NULL,
    fecha_actualizacion TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ps_expedientes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fundacion_id INTEGER NOT NULL,
    fcr_expediente_familiar_id INTEGER NOT NULL,
    expediente_uca_id INTEGER,
    unidad_nombre TEXT,
    unidad_clave TEXT,
    participante_origen TEXT,
    participante_id INTEGER,
    profesional_referente_id INTEGER,
    profesional_referente_nombre TEXT,
    nivel_acceso TEXT DEFAULT 'RESTRINGIDO',
    estado TEXT DEFAULT 'ACTIVO',
    motivo_apertura TEXT,
    fecha_apertura TEXT NOT NULL,
    fecha_cierre TEXT,
    cierre_validado_por INTEGER,
    creado_por INTEGER,
    actualizado_por INTEGER,
    fecha_creacion TEXT NOT NULL,
    fecha_actualizacion TEXT NOT NULL,
    UNIQUE(fundacion_id,fcr_expediente_familiar_id),
    FOREIGN KEY(fcr_expediente_familiar_id) REFERENCES fcr_expedientes_familiares(id)
);
CREATE INDEX IF NOT EXISTS idx_ps_exp_fund ON ps_expedientes(fundacion_id,estado,unidad_clave);
CREATE INDEX IF NOT EXISTS idx_ps_exp_prof ON ps_expedientes(fundacion_id,profesional_referente_id,estado);

CREATE TABLE IF NOT EXISTS ps_caracterizaciones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fundacion_id INTEGER NOT NULL,
    expediente_id INTEGER NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    fecha_caracterizacion TEXT NOT NULL,
    tipo TEXT DEFAULT 'INICIAL',
    composicion_familiar_json TEXT DEFAULT '{}',
    dinamicas_cuidado_json TEXT DEFAULT '{}',
    factores_protectores_json TEXT DEFAULT '[]',
    situaciones_acompanar_json TEXT DEFAULT '[]',
    redes_presentes_json TEXT DEFAULT '[]',
    barreras_acceso_json TEXT DEFAULT '[]',
    enfoque_diferencial_json TEXT DEFAULT '{}',
    conclusion_profesional TEXT,
    recomendaciones TEXT,
    estado TEXT DEFAULT 'BORRADOR',
    activo INTEGER DEFAULT 1,
    elaborado_por INTEGER,
    revisado_por INTEGER,
    fecha_revision TEXT,
    fecha_creacion TEXT NOT NULL,
    fecha_actualizacion TEXT NOT NULL,
    UNIQUE(fundacion_id,expediente_id,version),
    FOREIGN KEY(expediente_id) REFERENCES ps_expedientes(id)
);
CREATE INDEX IF NOT EXISTS idx_ps_car_exp ON ps_caracterizaciones(fundacion_id,expediente_id,activo,version);

CREATE TABLE IF NOT EXISTS ps_planes_acompanamiento (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fundacion_id INTEGER NOT NULL,
    expediente_id INTEGER NOT NULL,
    caracterizacion_id INTEGER,
    nombre TEXT NOT NULL,
    objetivo_general TEXT NOT NULL,
    fecha_inicio TEXT NOT NULL,
    fecha_fin_estimada TEXT,
    estado TEXT DEFAULT 'BORRADOR',
    prioridad TEXT DEFAULT 'MEDIA',
    porcentaje REAL DEFAULT 0,
    resultado_final TEXT,
    fecha_cierre TEXT,
    cierre_validado_por INTEGER,
    creado_por INTEGER,
    actualizado_por INTEGER,
    fecha_creacion TEXT NOT NULL,
    fecha_actualizacion TEXT NOT NULL,
    FOREIGN KEY(expediente_id) REFERENCES ps_expedientes(id),
    FOREIGN KEY(caracterizacion_id) REFERENCES ps_caracterizaciones(id)
);
CREATE INDEX IF NOT EXISTS idx_ps_plan_exp ON ps_planes_acompanamiento(fundacion_id,expediente_id,estado);

CREATE TABLE IF NOT EXISTS ps_acciones_plan (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fundacion_id INTEGER NOT NULL,
    plan_id INTEGER NOT NULL,
    expediente_uca_id INTEGER,
    unidad_nombre TEXT,
    titulo TEXT NOT NULL,
    descripcion TEXT,
    tipo_accion TEXT DEFAULT 'ACOMPANAMIENTO',
    fecha_inicio TEXT,
    fecha_limite TEXT,
    responsable_id INTEGER,
    responsable_nombre TEXT,
    prioridad TEXT DEFAULT 'MEDIA',
    estado TEXT DEFAULT 'PENDIENTE',
    porcentaje REAL DEFAULT 0,
    requiere_evidencia INTEGER DEFAULT 0,
    evidencia_referencia TEXT,
    fcr_actividad_id INTEGER,
    fcr_compromiso_id INTEGER,
    resultado TEXT,
    completada_por INTEGER,
    validada_por INTEGER,
    fecha_completada TEXT,
    creado_por INTEGER,
    actualizado_por INTEGER,
    fecha_creacion TEXT NOT NULL,
    fecha_actualizacion TEXT NOT NULL,
    FOREIGN KEY(plan_id) REFERENCES ps_planes_acompanamiento(id),
    FOREIGN KEY(fcr_actividad_id) REFERENCES fcr_actividades(id),
    FOREIGN KEY(fcr_compromiso_id) REFERENCES fcr_compromisos(id)
);
CREATE INDEX IF NOT EXISTS idx_ps_acc_plan ON ps_acciones_plan(fundacion_id,plan_id,estado,fecha_limite);

CREATE TABLE IF NOT EXISTS ps_vinculos_actividad (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fundacion_id INTEGER NOT NULL,
    expediente_id INTEGER NOT NULL,
    fcr_actividad_id INTEGER NOT NULL,
    tipo_vinculo TEXT DEFAULT 'INTERVENCION',
    observaciones TEXT,
    creado_por INTEGER,
    fecha_creacion TEXT NOT NULL,
    UNIQUE(fundacion_id,expediente_id,fcr_actividad_id),
    FOREIGN KEY(expediente_id) REFERENCES ps_expedientes(id),
    FOREIGN KEY(fcr_actividad_id) REFERENCES fcr_actividades(id)
);

CREATE TABLE IF NOT EXISTS ps_seguimientos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fundacion_id INTEGER NOT NULL,
    expediente_id INTEGER NOT NULL,
    plan_id INTEGER,
    accion_id INTEGER,
    fecha TEXT NOT NULL,
    tipo TEXT DEFAULT 'SEGUIMIENTO',
    descripcion TEXT NOT NULL,
    resultado TEXT,
    proxima_accion TEXT,
    fecha_proximo_seguimiento TEXT,
    evidencia_referencia TEXT,
    creado_por INTEGER,
    fecha_creacion TEXT NOT NULL,
    FOREIGN KEY(expediente_id) REFERENCES ps_expedientes(id),
    FOREIGN KEY(plan_id) REFERENCES ps_planes_acompanamiento(id),
    FOREIGN KEY(accion_id) REFERENCES ps_acciones_plan(id)
);
CREATE INDEX IF NOT EXISTS idx_ps_seg_exp ON ps_seguimientos(fundacion_id,expediente_id,fecha);

CREATE TABLE IF NOT EXISTS ps_documentos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fundacion_id INTEGER NOT NULL,
    expediente_id INTEGER NOT NULL,
    plan_id INTEGER,
    tipo_documento TEXT NOT NULL,
    nombre_archivo TEXT NOT NULL,
    ruta_archivo TEXT NOT NULL,
    mime_type TEXT,
    tamano_bytes INTEGER DEFAULT 0,
    sha256 TEXT NOT NULL,
    estado TEXT DEFAULT 'BORRADOR',
    contiene_datos_restringidos INTEGER DEFAULT 1,
    generado_por INTEGER,
    revisado_por INTEGER,
    aprobado_por INTEGER,
    fecha_generacion TEXT NOT NULL,
    fecha_revision TEXT,
    fecha_aprobacion TEXT,
    FOREIGN KEY(expediente_id) REFERENCES ps_expedientes(id)
);
CREATE INDEX IF NOT EXISTS idx_ps_docs_exp ON ps_documentos(fundacion_id,expediente_id,estado);

CREATE TABLE IF NOT EXISTS ps_auditoria_accesos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fundacion_id INTEGER NOT NULL,
    expediente_id INTEGER,
    usuario_id INTEGER,
    usuario TEXT,
    rol TEXT,
    accion TEXT NOT NULL,
    detalle_json TEXT DEFAULT '{}',
    fecha TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_ps_audit_fund ON ps_auditoria_accesos(fundacion_id,expediente_id,fecha);
"""
