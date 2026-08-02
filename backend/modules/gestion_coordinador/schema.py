"""Esquema FASE 2: Gestión por Coordinador.

Todas las tablas nuevas usan prefijo gp_ y no reemplazan módulos existentes.
"""

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS gp_asignaciones_coordinador (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    coordinador_id INTEGER NOT NULL,
    tipo_talento TEXT NOT NULL,
    origen_tabla TEXT,
    origen_id INTEGER,
    nombre TEXT NOT NULL,
    documento TEXT,
    cargo TEXT,
    rol TEXT,
    unidad TEXT,
    telefono TEXT,
    email TEXT,
    estado TEXT DEFAULT 'ACTIVO',
    fecha_inicio TEXT,
    fecha_fin TEXT,
    observaciones TEXT,
    fundacion_id INTEGER,
    usuario_creador_id INTEGER,
    fecha_creacion TEXT NOT NULL,
    fecha_actualizacion TEXT,
    FOREIGN KEY (coordinador_id) REFERENCES gp_coordinadores(id)
);

CREATE TABLE IF NOT EXISTS gp_historial_asignaciones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asignacion_id INTEGER,
    coordinador_origen_id INTEGER,
    coordinador_destino_id INTEGER,
    accion TEXT NOT NULL,
    datos_anteriores TEXT,
    datos_nuevos TEXT,
    usuario TEXT,
    fundacion_id INTEGER,
    usuario_creador_id INTEGER,
    fecha_accion TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS gp_evidencias (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    actividad_id INTEGER,
    entregable_id INTEGER,
    coordinador_id INTEGER,
    docente_id INTEGER,
    unidad TEXT,
    tipo TEXT DEFAULT 'Evidencia',
    titulo TEXT,
    descripcion TEXT,
    ruta_archivo TEXT,
    nombre_original TEXT,
    nombre_guardado TEXT,
    estado TEXT DEFAULT 'CARGADA',
    observaciones TEXT,
    fundacion_id INTEGER,
    usuario_creador_id INTEGER,
    fecha_creacion TEXT NOT NULL,
    fecha_actualizacion TEXT
);

CREATE TABLE IF NOT EXISTS gp_estado_cumplimiento (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    coordinador_id INTEGER,
    periodo TEXT NOT NULL,
    total_actividades INTEGER DEFAULT 0,
    cumplidas INTEGER DEFAULT 0,
    pendientes INTEGER DEFAULT 0,
    vencidas INTEGER DEFAULT 0,
    anuladas INTEGER DEFAULT 0,
    porcentaje REAL DEFAULT 0,
    semaforo TEXT DEFAULT 'GRIS',
    observaciones TEXT,
    fundacion_id INTEGER,
    usuario_creador_id INTEGER,
    fecha_creacion TEXT NOT NULL,
    fecha_actualizacion TEXT,
    UNIQUE(coordinador_id, periodo, fundacion_id)
);

CREATE INDEX IF NOT EXISTS idx_gp_asig_coord ON gp_asignaciones_coordinador(coordinador_id, estado);
CREATE INDEX IF NOT EXISTS idx_gp_asig_fund ON gp_asignaciones_coordinador(fundacion_id);
CREATE INDEX IF NOT EXISTS idx_gp_evid_coord ON gp_evidencias(coordinador_id, fecha_creacion);
CREATE INDEX IF NOT EXISTS idx_gp_cumpl_coord ON gp_estado_cumplimiento(coordinador_id, periodo);
"""

EXISTING_GP_TABLES = [
    'gp_contratos', 'gp_coordinadores', 'gp_docentes', 'gp_equipos_interdisciplinarios',
    'gp_unidades_asignadas', 'gp_entregables', 'gp_documentos', 'gp_alertas',
    'gp_planeaciones', 'gp_actas', 'gp_encuentros_hogar', 'gp_encuentros_comunitarios',
    'gp_calendario_eventos', 'gp_observaciones', 'gp_historial_acciones',
    'gp_configuracion_entregables', 'gp_asignaciones_coordinador', 'gp_evidencias',
    'gp_estado_cumplimiento', 'gp_historial_asignaciones'
]

MULTITENANT_COLUMNS = {
    'fundacion_id': 'INTEGER',
    'usuario_creador_id': 'INTEGER',
    'fecha_actualizacion': 'TEXT'
}

CALENDAR_EXTRA_COLUMNS = {
    'unidad': 'TEXT',
    'docente_id': 'INTEGER',
    'docente_nombre': 'TEXT',
    'responsable': 'TEXT',
    'prioridad': "TEXT DEFAULT 'MEDIA'",
    'evidencia_requerida': 'INTEGER DEFAULT 0',
    'fecha_cumplimiento': 'TEXT',
    'reprogramado_de': 'TEXT',
    'usuario_responsable_id': 'INTEGER'
}

COORDINADOR_EXTRA_COLUMNS = {
    'usuario_id': 'INTEGER',
    'fundacion_id': 'INTEGER',
    'usuario_creador_id': 'INTEGER',
    'fecha_actualizacion': 'TEXT'
}
