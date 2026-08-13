"""Esquema aditivo; supervisiones y planes permanecen en csc_* como fuente canónica."""

SCHEMA_VERSION = 1
SCHEMA_SQL = r"""
CREATE TABLE IF NOT EXISTS aep_activos (
 id INTEGER PRIMARY KEY AUTOINCREMENT, fundacion_id INTEGER NOT NULL,
 unidad_id INTEGER, unidad_nombre TEXT NOT NULL, unidad_clave TEXT NOT NULL,
 codigo TEXT NOT NULL, categoria TEXT NOT NULL, nombre TEXT NOT NULL,
 descripcion TEXT, cantidad INTEGER NOT NULL DEFAULT 1, estado TEXT NOT NULL DEFAULT 'BUENO',
 ubicacion TEXT, fecha_adquisicion TEXT, fecha_ultima_revision TEXT,
 fecha_proxima_revision TEXT, responsable_id INTEGER, responsable_nombre TEXT,
 activo INTEGER NOT NULL DEFAULT 1, creada_por INTEGER, actualizada_por INTEGER,
 fecha_creacion TEXT NOT NULL, fecha_actualizacion TEXT NOT NULL,
 UNIQUE(fundacion_id,codigo)
);
CREATE INDEX IF NOT EXISTS idx_aep_activos_uca ON aep_activos(fundacion_id,unidad_clave,activo,estado);
CREATE TABLE IF NOT EXISTS aep_mantenimientos (
 id INTEGER PRIMARY KEY AUTOINCREMENT, fundacion_id INTEGER NOT NULL,
 activo_id INTEGER, unidad_id INTEGER, unidad_nombre TEXT NOT NULL, unidad_clave TEXT NOT NULL,
 tipo TEXT NOT NULL, titulo TEXT NOT NULL, descripcion TEXT, fecha_programada TEXT NOT NULL,
 fecha_ejecucion TEXT, estado TEXT NOT NULL DEFAULT 'PROGRAMADO', prioridad TEXT DEFAULT 'MEDIA',
 responsable_id INTEGER, responsable_nombre TEXT, resultado TEXT,
 calendario_entregable_id INTEGER, csc_hallazgo_id INTEGER,
 validado_por INTEGER, fecha_validacion TEXT, creado_por INTEGER, actualizado_por INTEGER,
 fecha_creacion TEXT NOT NULL, fecha_actualizacion TEXT NOT NULL,
 FOREIGN KEY(activo_id) REFERENCES aep_activos(id),
 FOREIGN KEY(csc_hallazgo_id) REFERENCES csc_hallazgos(id)
);
CREATE INDEX IF NOT EXISTS idx_aep_mant_uca ON aep_mantenimientos(fundacion_id,unidad_clave,estado,fecha_programada);
CREATE TABLE IF NOT EXISTS aep_auditoria (
 id INTEGER PRIMARY KEY AUTOINCREMENT, fundacion_id INTEGER NOT NULL, usuario_id INTEGER,
 usuario TEXT, accion TEXT NOT NULL, entidad TEXT NOT NULL, entidad_id INTEGER,
 detalle_json TEXT, fecha TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS aep_schema_version (
 id INTEGER PRIMARY KEY CHECK(id=1), version INTEGER NOT NULL, fecha_actualizacion TEXT NOT NULL
);
"""
