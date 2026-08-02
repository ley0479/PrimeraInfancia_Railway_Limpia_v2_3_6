"""
Esquema aislado del módulo Gestión Pedagógica.

Todas las tablas usan prefijo gp_ para no interferir con las tablas existentes.
"""

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS gp_contratos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT,
    numero_contrato TEXT,
    entidad TEXT,
    regional TEXT,
    municipio TEXT,
    centro_zonal TEXT,
    estado TEXT DEFAULT 'activo',
    fecha_creacion TEXT NOT NULL,
    fecha_actualizacion TEXT
);

CREATE TABLE IF NOT EXISTS gp_coordinadores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    contrato_id INTEGER,
    contrato TEXT,
    nombre TEXT NOT NULL,
    documento TEXT,
    telefono TEXT,
    email TEXT,
    cargo TEXT DEFAULT 'COORDINADOR',
    zona TEXT,
    unidades_json TEXT,
    observaciones TEXT,
    activo INTEGER DEFAULT 1,
    fecha_creacion TEXT NOT NULL,
    fecha_actualizacion TEXT,
    FOREIGN KEY (contrato_id) REFERENCES gp_contratos(id)
);

CREATE TABLE IF NOT EXISTS gp_docentes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    coordinador_id INTEGER,
    nombre TEXT NOT NULL,
    documento TEXT,
    unidad TEXT,
    telefono TEXT,
    email TEXT,
    cargo TEXT DEFAULT 'DOCENTE',
    activo INTEGER DEFAULT 1,
    fecha_creacion TEXT NOT NULL,
    fecha_actualizacion TEXT,
    FOREIGN KEY (coordinador_id) REFERENCES gp_coordinadores(id)
);

CREATE TABLE IF NOT EXISTS gp_equipos_interdisciplinarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    coordinador_id INTEGER,
    nombre TEXT NOT NULL,
    documento TEXT,
    rol TEXT NOT NULL,
    profesion TEXT,
    telefono TEXT,
    email TEXT,
    activo INTEGER DEFAULT 1,
    fecha_creacion TEXT NOT NULL,
    fecha_actualizacion TEXT,
    FOREIGN KEY (coordinador_id) REFERENCES gp_coordinadores(id)
);

CREATE TABLE IF NOT EXISTS gp_unidades_asignadas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    coordinador_id INTEGER NOT NULL,
    unidad TEXT NOT NULL,
    estado TEXT DEFAULT 'activo',
    fecha_creacion TEXT NOT NULL,
    FOREIGN KEY (coordinador_id) REFERENCES gp_coordinadores(id)
);

CREATE TABLE IF NOT EXISTS gp_entregables (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    coordinador_id INTEGER,
    unidad TEXT,
    tipo TEXT NOT NULL,
    titulo TEXT NOT NULL,
    descripcion TEXT,
    periodo TEXT NOT NULL,
    fecha_limite TEXT,
    prioridad TEXT DEFAULT 'media',
    estado TEXT DEFAULT 'Pendiente',
    responsable TEXT,
    documento_id INTEGER,
    observaciones TEXT,
    activo INTEGER DEFAULT 1,
    fecha_creacion TEXT NOT NULL,
    fecha_actualizacion TEXT,
    fecha_carga TEXT,
    FOREIGN KEY (coordinador_id) REFERENCES gp_coordinadores(id)
);

CREATE TABLE IF NOT EXISTS gp_documentos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entregable_id INTEGER,
    coordinador_id INTEGER,
    nombre_original TEXT NOT NULL,
    nombre_guardado TEXT NOT NULL,
    ruta_archivo TEXT NOT NULL,
    version TEXT DEFAULT '1.0',
    estado TEXT DEFAULT 'Cargado',
    observaciones TEXT,
    usuario_carga TEXT,
    fecha_carga TEXT NOT NULL,
    fecha_revision TEXT,
    usuario_revision TEXT,
    activo INTEGER DEFAULT 1,
    FOREIGN KEY (entregable_id) REFERENCES gp_entregables(id),
    FOREIGN KEY (coordinador_id) REFERENCES gp_coordinadores(id)
);

CREATE TABLE IF NOT EXISTS gp_documento_versiones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    documento_id INTEGER NOT NULL,
    version TEXT NOT NULL,
    ruta_archivo TEXT NOT NULL,
    estado TEXT DEFAULT 'Cargado',
    usuario_carga TEXT,
    fecha_carga TEXT NOT NULL,
    observaciones TEXT,
    FOREIGN KEY (documento_id) REFERENCES gp_documentos(id)
);

CREATE TABLE IF NOT EXISTS gp_alertas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entidad_tipo TEXT,
    entidad_id INTEGER,
    coordinador_id INTEGER,
    nivel TEXT DEFAULT 'AMARILLO',
    tipo TEXT NOT NULL,
    mensaje TEXT NOT NULL,
    fecha_alerta TEXT NOT NULL,
    leida INTEGER DEFAULT 0,
    fecha_creacion TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS gp_planeaciones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    coordinador_id INTEGER,
    docente_id INTEGER,
    periodo TEXT NOT NULL,
    tema TEXT,
    objetivo TEXT,
    actividad TEXT,
    recursos TEXT,
    evidencias TEXT,
    ruta_archivo TEXT,
    estado TEXT DEFAULT 'Borrador',
    fecha_creacion TEXT NOT NULL,
    fecha_actualizacion TEXT,
    FOREIGN KEY (coordinador_id) REFERENCES gp_coordinadores(id),
    FOREIGN KEY (docente_id) REFERENCES gp_docentes(id)
);

CREATE TABLE IF NOT EXISTS gp_actas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    planeacion_id INTEGER,
    numero_acta TEXT,
    fecha TEXT,
    lugar TEXT,
    coordinador_id INTEGER,
    docente_id INTEGER,
    tema TEXT,
    objetivo TEXT,
    desarrollo TEXT,
    compromisos TEXT,
    responsables TEXT,
    observaciones TEXT,
    estado TEXT DEFAULT 'Borrador',
    fecha_creacion TEXT NOT NULL,
    fecha_actualizacion TEXT,
    FOREIGN KEY (planeacion_id) REFERENCES gp_planeaciones(id)
);

CREATE TABLE IF NOT EXISTS gp_encuentros_hogar (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    coordinador_id INTEGER,
    docente_id INTEGER,
    beneficiario_documento TEXT,
    familia TEXT,
    tema TEXT,
    fecha TEXT,
    evidencia_documento_id INTEGER,
    observaciones TEXT,
    estado TEXT DEFAULT 'Programado',
    fecha_creacion TEXT NOT NULL,
    fecha_actualizacion TEXT
);

CREATE TABLE IF NOT EXISTS gp_encuentros_comunitarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    coordinador_id INTEGER,
    tema TEXT,
    fecha TEXT,
    responsables TEXT,
    evidencia_documento_id INTEGER,
    acta_documento_id INTEGER,
    observaciones TEXT,
    estado TEXT DEFAULT 'Programado',
    fecha_creacion TEXT NOT NULL,
    fecha_actualizacion TEXT
);

CREATE TABLE IF NOT EXISTS gp_calendario_eventos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    coordinador_id INTEGER,
    entregable_id INTEGER,
    titulo TEXT NOT NULL,
    tipo TEXT DEFAULT 'Evento',
    fecha TEXT NOT NULL,
    hora TEXT,
    estado TEXT DEFAULT 'Pendiente',
    descripcion TEXT,
    color TEXT,
    fecha_creacion TEXT NOT NULL,
    fecha_actualizacion TEXT,
    FOREIGN KEY (coordinador_id) REFERENCES gp_coordinadores(id),
    FOREIGN KEY (entregable_id) REFERENCES gp_entregables(id)
);

CREATE TABLE IF NOT EXISTS gp_observaciones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entidad_tipo TEXT NOT NULL,
    entidad_id INTEGER NOT NULL,
    observacion TEXT NOT NULL,
    usuario TEXT,
    fecha_creacion TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS gp_historial_acciones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario TEXT,
    accion TEXT NOT NULL,
    entidad_tipo TEXT,
    entidad_id INTEGER,
    datos_anteriores TEXT,
    datos_nuevos TEXT,
    fecha_accion TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS gp_configuracion_entregables (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tipo TEXT UNIQUE NOT NULL,
    categoria TEXT,
    dias_limite INTEGER DEFAULT 25,
    prioridad TEXT DEFAULT 'media',
    activo INTEGER DEFAULT 1,
    fecha_creacion TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_gp_entregables_periodo ON gp_entregables(periodo);
CREATE INDEX IF NOT EXISTS idx_gp_entregables_estado ON gp_entregables(estado);
CREATE INDEX IF NOT EXISTS idx_gp_documentos_estado ON gp_documentos(estado);
CREATE INDEX IF NOT EXISTS idx_gp_calendario_fecha ON gp_calendario_eventos(fecha);
"""

DEFAULT_ENTREGABLES = [
    ('Planeación mensual', 'Proceso Pedagógico', 5, 'alta'),
    ('Encuentro en el hogar', 'Familia y Comunidad', 20, 'media'),
    ('Encuentro comunitario', 'Familia y Comunidad', 22, 'media'),
    ('Acta grupal', 'Familia y Comunidad', 25, 'media'),
    ('Lista de chequeo mensual', 'Administrativo', 25, 'alta'),
    ('Evidencias fotográficas', 'Evidencias', 25, 'media'),
    ('Informe mensual', 'Gerencial', 28, 'alta'),
    ('RAM / Asistencia mensual', 'Formatos ICBF', 28, 'alta'),
    ('RPP / RAN', 'Formatos ICBF', 28, 'alta'),
]
