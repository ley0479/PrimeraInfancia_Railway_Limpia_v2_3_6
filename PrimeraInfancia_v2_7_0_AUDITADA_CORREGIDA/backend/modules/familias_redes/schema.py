from __future__ import annotations

SCHEMA_VERSION = 1

SCHEMA_SQL = r"""
CREATE TABLE IF NOT EXISTS fcr_schema_version (
    id INTEGER PRIMARY KEY CHECK(id=1),
    version INTEGER NOT NULL,
    fecha_actualizacion TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS fcr_expedientes_familiares (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fundacion_id INTEGER NOT NULL,
    expediente_uca_id INTEGER,
    unidad_id INTEGER,
    unidad_nombre TEXT,
    unidad_clave TEXT,
    participante_origen TEXT NOT NULL DEFAULT 'master_ninos',
    participante_id INTEGER NOT NULL,
    cuidador_principal TEXT,
    parentesco TEXT,
    telefono_principal TEXT,
    correo TEXT,
    direccion TEXT,
    contacto_alterno_nombre TEXT,
    contacto_alterno_parentesco TEXT,
    contacto_alterno_telefono TEXT,
    autoridad_tradicional TEXT,
    autoridad_tradicional_telefono TEXT,
    caracterizacion_json TEXT,
    nivel_acceso TEXT DEFAULT 'RESTRINGIDO',
    estado TEXT DEFAULT 'ACTIVO',
    observaciones TEXT,
    creado_por INTEGER,
    actualizado_por INTEGER,
    fecha_creacion TEXT NOT NULL,
    fecha_actualizacion TEXT NOT NULL,
    UNIQUE(fundacion_id,participante_origen,participante_id)
);
CREATE INDEX IF NOT EXISTS idx_fcr_expedientes_fund ON fcr_expedientes_familiares(fundacion_id,estado,unidad_clave);

CREATE TABLE IF NOT EXISTS fcr_actividades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fundacion_id INTEGER NOT NULL,
    expediente_uca_id INTEGER,
    unidad_id INTEGER,
    unidad_nombre TEXT,
    unidad_clave TEXT,
    tipo TEXT NOT NULL,
    titulo TEXT NOT NULL,
    objetivo TEXT,
    metodologia TEXT,
    lugar TEXT,
    fecha_programada TEXT,
    fecha_ejecucion TEXT,
    fecha_limite_cierre TEXT,
    estado TEXT DEFAULT 'BORRADOR',
    profesional_id INTEGER,
    profesional_nombre TEXT,
    participantes_esperados INTEGER DEFAULT 0,
    participantes_asistentes INTEGER DEFAULT 0,
    resultados TEXT,
    conclusiones_profesionales TEXT,
    compromisos_generales TEXT,
    observaciones TEXT,
    creado_por INTEGER,
    actualizado_por INTEGER,
    fecha_creacion TEXT NOT NULL,
    fecha_actualizacion TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_fcr_actividades_fund ON fcr_actividades(fundacion_id,estado,fecha_programada);
CREATE INDEX IF NOT EXISTS idx_fcr_actividades_uca ON fcr_actividades(fundacion_id,unidad_clave,tipo);

CREATE TABLE IF NOT EXISTS fcr_asistencias (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fundacion_id INTEGER NOT NULL,
    actividad_id INTEGER NOT NULL,
    expediente_familiar_id INTEGER,
    nombre_asistente TEXT,
    tipo_asistente TEXT DEFAULT 'FAMILIA',
    documento_referencia TEXT,
    telefono TEXT,
    asistio INTEGER DEFAULT 0,
    firma_referencia TEXT,
    observaciones TEXT,
    registrado_por INTEGER,
    fecha_registro TEXT NOT NULL,
    UNIQUE(fundacion_id,actividad_id,expediente_familiar_id,nombre_asistente),
    FOREIGN KEY(actividad_id) REFERENCES fcr_actividades(id),
    FOREIGN KEY(expediente_familiar_id) REFERENCES fcr_expedientes_familiares(id)
);
CREATE INDEX IF NOT EXISTS idx_fcr_asistencias_act ON fcr_asistencias(fundacion_id,actividad_id,asistio);

CREATE TABLE IF NOT EXISTS fcr_compromisos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fundacion_id INTEGER NOT NULL,
    actividad_id INTEGER,
    expediente_familiar_id INTEGER,
    expediente_uca_id INTEGER,
    unidad_nombre TEXT,
    unidad_clave TEXT,
    titulo TEXT NOT NULL,
    descripcion TEXT,
    responsable_id INTEGER,
    responsable_nombre TEXT,
    fecha_compromiso TEXT NOT NULL,
    fecha_limite TEXT,
    estado TEXT DEFAULT 'PENDIENTE',
    prioridad TEXT DEFAULT 'MEDIA',
    porcentaje REAL DEFAULT 0,
    fecha_cierre TEXT,
    cierre_validado_por INTEGER,
    observaciones_cierre TEXT,
    creado_por INTEGER,
    actualizado_por INTEGER,
    fecha_creacion TEXT NOT NULL,
    fecha_actualizacion TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_fcr_compromisos_fund ON fcr_compromisos(fundacion_id,estado,fecha_limite);
CREATE INDEX IF NOT EXISTS idx_fcr_compromisos_uca ON fcr_compromisos(fundacion_id,unidad_clave,estado);

CREATE TABLE IF NOT EXISTS fcr_seguimientos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fundacion_id INTEGER NOT NULL,
    compromiso_id INTEGER NOT NULL,
    expediente_familiar_id INTEGER,
    fecha TEXT NOT NULL,
    resultado TEXT NOT NULL,
    porcentaje_reportado REAL DEFAULT 0,
    proxima_accion TEXT,
    fecha_proximo_seguimiento TEXT,
    evidencia_referencia TEXT,
    creado_por INTEGER,
    fecha_creacion TEXT NOT NULL,
    FOREIGN KEY(compromiso_id) REFERENCES fcr_compromisos(id)
);
CREATE INDEX IF NOT EXISTS idx_fcr_seguimientos_comp ON fcr_seguimientos(fundacion_id,compromiso_id,fecha);

CREATE TABLE IF NOT EXISTS fcr_redes_apoyo (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fundacion_id INTEGER NOT NULL,
    nombre TEXT NOT NULL,
    tipo_actor TEXT NOT NULL,
    territorio TEXT,
    municipio TEXT,
    direccion TEXT,
    contacto_nombre TEXT,
    telefono TEXT,
    correo TEXT,
    servicios_json TEXT,
    rutas_json TEXT,
    horario TEXT,
    observaciones TEXT,
    activo INTEGER DEFAULT 1,
    verificado_por INTEGER,
    fecha_verificacion TEXT,
    creado_por INTEGER,
    actualizado_por INTEGER,
    fecha_creacion TEXT NOT NULL,
    fecha_actualizacion TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_fcr_redes_fund ON fcr_redes_apoyo(fundacion_id,activo,tipo_actor);

CREATE TABLE IF NOT EXISTS fcr_alertas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fundacion_id INTEGER NOT NULL,
    expediente_familiar_id INTEGER,
    actividad_id INTEGER,
    expediente_uca_id INTEGER,
    unidad_nombre TEXT,
    unidad_clave TEXT,
    tipo TEXT NOT NULL,
    nivel TEXT DEFAULT 'MEDIO',
    descripcion TEXT NOT NULL,
    estado TEXT DEFAULT 'ABIERTA',
    entidad_ruta_id INTEGER,
    fecha_identificacion TEXT NOT NULL,
    fecha_activacion_ruta TEXT,
    fecha_proximo_seguimiento TEXT,
    responsable_id INTEGER,
    responsable_nombre TEXT,
    fecha_cierre TEXT,
    cerrado_por INTEGER,
    resultado_cierre TEXT,
    evidencia_cierre TEXT,
    creado_por INTEGER,
    actualizado_por INTEGER,
    fecha_creacion TEXT NOT NULL,
    fecha_actualizacion TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_fcr_alertas_fund ON fcr_alertas(fundacion_id,estado,nivel,fecha_proximo_seguimiento);

CREATE TABLE IF NOT EXISTS fcr_evidencias (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fundacion_id INTEGER NOT NULL,
    actividad_id INTEGER,
    compromiso_id INTEGER,
    alerta_id INTEGER,
    expediente_familiar_id INTEGER,
    tipo TEXT,
    titulo TEXT,
    nombre_original TEXT NOT NULL,
    nombre_guardado TEXT NOT NULL,
    ruta_archivo TEXT NOT NULL,
    mime_type TEXT,
    tamano_bytes INTEGER DEFAULT 0,
    sha256 TEXT NOT NULL,
    version INTEGER DEFAULT 1,
    activo INTEGER DEFAULT 1,
    cargado_por INTEGER,
    fecha_carga TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_fcr_evidencias_fund ON fcr_evidencias(fundacion_id,actividad_id,compromiso_id,alerta_id,activo);

CREATE TABLE IF NOT EXISTS fcr_documentos_generados (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fundacion_id INTEGER NOT NULL,
    actividad_id INTEGER,
    expediente_familiar_id INTEGER,
    tipo_documento TEXT NOT NULL,
    nombre_archivo TEXT NOT NULL,
    ruta_archivo TEXT NOT NULL,
    mime_type TEXT,
    tamano_bytes INTEGER DEFAULT 0,
    sha256 TEXT NOT NULL,
    estado TEXT DEFAULT 'BORRADOR',
    version_plantilla TEXT,
    generado_por INTEGER,
    revisado_por INTEGER,
    aprobado_por INTEGER,
    fecha_generacion TEXT NOT NULL,
    fecha_revision TEXT,
    fecha_aprobacion TEXT
);
CREATE INDEX IF NOT EXISTS idx_fcr_documentos_fund ON fcr_documentos_generados(fundacion_id,estado,fecha_generacion);

CREATE TABLE IF NOT EXISTS fcr_auditoria (
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
CREATE INDEX IF NOT EXISTS idx_fcr_auditoria_fund ON fcr_auditoria(fundacion_id,fecha);
"""
