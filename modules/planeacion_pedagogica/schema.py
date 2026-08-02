"""Esquema aislado FASE 3: Planeación Pedagógica.

Todas las tablas nuevas usan prefijo pp_ para evitar conflictos con módulos existentes.
No modifica formatos ICBF ni reemplaza tablas gp_, sn_ o tablas base.
"""

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS pp_planeaciones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fundacion_id INTEGER,
    usuario_creador_id INTEGER,
    coordinador_id INTEGER,
    docente_id INTEGER,
    unidad TEXT,
    periodo TEXT NOT NULL,
    mes INTEGER,
    anio INTEGER,
    tema TEXT,
    objetivo TEXT,
    actividad TEXT,
    fecha_programada TEXT,
    poblacion_objetivo TEXT,
    evidencia_requerida TEXT,
    tipo_encuentro TEXT,
    observaciones TEXT,
    estado TEXT DEFAULT 'BORRADOR',
    ruta_archivo TEXT,
    nombre_original TEXT,
    nombre_guardado TEXT,
    texto_extraido TEXT,
    validacion_json TEXT,
    activo INTEGER DEFAULT 1,
    fecha_carga TEXT,
    fecha_creacion TEXT NOT NULL,
    fecha_actualizacion TEXT
);

CREATE TABLE IF NOT EXISTS pp_actividades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    planeacion_id INTEGER NOT NULL,
    fundacion_id INTEGER,
    usuario_creador_id INTEGER,
    coordinador_id INTEGER,
    docente_id INTEGER,
    unidad TEXT,
    tipo_actividad TEXT NOT NULL,
    titulo TEXT,
    tema TEXT,
    objetivo TEXT,
    actividad TEXT,
    fecha_programada TEXT,
    poblacion_objetivo TEXT,
    evidencia_requerida TEXT,
    estado TEXT DEFAULT 'PENDIENTE',
    calendario_evento_id INTEGER,
    entregable_id INTEGER,
    activo INTEGER DEFAULT 1,
    fecha_creacion TEXT NOT NULL,
    fecha_actualizacion TEXT,
    FOREIGN KEY (planeacion_id) REFERENCES pp_planeaciones(id)
);

CREATE TABLE IF NOT EXISTS pp_tipos_actividad (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo TEXT UNIQUE NOT NULL,
    nombre TEXT NOT NULL,
    descripcion TEXT,
    activo INTEGER DEFAULT 1,
    fecha_creacion TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS pp_plantillas_documento (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fundacion_id INTEGER,
    usuario_creador_id INTEGER,
    nombre TEXT NOT NULL,
    tipo_documento TEXT NOT NULL,
    campos_dinamicos TEXT,
    formato_base TEXT,
    nombre_original TEXT,
    nombre_guardado TEXT,
    ruta_archivo TEXT,
    version TEXT DEFAULT '1.0',
    estado TEXT DEFAULT 'ACTIVA',
    activo INTEGER DEFAULT 1,
    fecha_creacion TEXT NOT NULL,
    fecha_actualizacion TEXT
);

CREATE TABLE IF NOT EXISTS pp_documentos_generados (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fundacion_id INTEGER,
    usuario_creador_id INTEGER,
    planeacion_id INTEGER,
    actividad_id INTEGER,
    plantilla_id INTEGER,
    tipo_documento TEXT NOT NULL,
    nombre TEXT NOT NULL,
    nombre_guardado TEXT NOT NULL,
    ruta_archivo TEXT NOT NULL,
    formato TEXT DEFAULT 'docx',
    estado TEXT DEFAULT 'GENERADO',
    observaciones TEXT,
    fecha_generacion TEXT NOT NULL,
    FOREIGN KEY (planeacion_id) REFERENCES pp_planeaciones(id),
    FOREIGN KEY (actividad_id) REFERENCES pp_actividades(id),
    FOREIGN KEY (plantilla_id) REFERENCES pp_plantillas_documento(id)
);

CREATE TABLE IF NOT EXISTS pp_evidencias_planeacion (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fundacion_id INTEGER,
    usuario_creador_id INTEGER,
    planeacion_id INTEGER,
    actividad_id INTEGER,
    tipo TEXT DEFAULT 'EVIDENCIA',
    titulo TEXT,
    descripcion TEXT,
    ruta_archivo TEXT,
    nombre_original TEXT,
    nombre_guardado TEXT,
    estado TEXT DEFAULT 'CARGADA',
    observaciones TEXT,
    activo INTEGER DEFAULT 1,
    fecha_creacion TEXT NOT NULL,
    fecha_actualizacion TEXT,
    FOREIGN KEY (planeacion_id) REFERENCES pp_planeaciones(id),
    FOREIGN KEY (actividad_id) REFERENCES pp_actividades(id)
);

CREATE TABLE IF NOT EXISTS pp_aprobaciones_planeacion (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fundacion_id INTEGER,
    usuario_creador_id INTEGER,
    planeacion_id INTEGER NOT NULL,
    accion TEXT NOT NULL,
    estado_anterior TEXT,
    estado_nuevo TEXT,
    observacion TEXT,
    usuario_aprueba TEXT,
    fecha_accion TEXT NOT NULL,
    FOREIGN KEY (planeacion_id) REFERENCES pp_planeaciones(id)
);

CREATE TABLE IF NOT EXISTS pp_historial_planeacion (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fundacion_id INTEGER,
    usuario_creador_id INTEGER,
    planeacion_id INTEGER,
    entidad_tipo TEXT,
    entidad_id INTEGER,
    accion TEXT NOT NULL,
    datos_anteriores TEXT,
    datos_nuevos TEXT,
    usuario TEXT,
    fecha_accion TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_pp_planeaciones_periodo ON pp_planeaciones(periodo, estado);
CREATE INDEX IF NOT EXISTS idx_pp_planeaciones_fundacion ON pp_planeaciones(fundacion_id, periodo);
CREATE INDEX IF NOT EXISTS idx_pp_actividades_planeacion ON pp_actividades(planeacion_id, estado);
CREATE INDEX IF NOT EXISTS idx_pp_actividades_fecha ON pp_actividades(fecha_programada, estado);
CREATE INDEX IF NOT EXISTS idx_pp_documentos_planeacion ON pp_documentos_generados(planeacion_id, tipo_documento);
CREATE INDEX IF NOT EXISTS idx_pp_evidencias_planeacion ON pp_evidencias_planeacion(planeacion_id, actividad_id);
"""

TIPOS_ACTIVIDAD_DEFAULT = [
    ('ENCUENTRO_COMUNITARIO', 'Encuentro comunitario'),
    ('ENCUENTRO_HOGAR', 'Encuentro en el hogar'),
    ('ENCUENTRO_HOGAR_COMUNITARIO', 'Encuentro en hogar comunitario'),
    ('VISITA_HOGAR', 'Visita al hogar'),
    ('ACTIVIDAD_PEDAGOGICA', 'Actividad pedagógica'),
    ('SEGUIMIENTO_FAMILIAR', 'Seguimiento familiar'),
    ('REUNION_EQUIPO', 'Reunión de equipo'),
    ('ENTREGA_EVIDENCIA', 'Entrega de evidencia'),
]

ESTADOS_PLANEACION = ['BORRADOR', 'CARGADA', 'VALIDADA', 'RECHAZADA', 'APROBADA', 'ANULADA']

TIPOS_DOCUMENTO_GENERABLES = [
    'Informe pedagógico mensual',
    'Acta de encuentro comunitario',
    'Formato de encuentro en el hogar',
    'Formato de encuentro en hogar comunitario',
    'Formato de visita al hogar',
    'Cronograma mensual',
    'Listado de evidencias pendientes',
    'Reporte de cumplimiento',
]
