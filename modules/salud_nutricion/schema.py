"""
Esquema aislado del módulo Salud y Nutrición Inteligente.

Todas las tablas usan prefijo sn_ para evitar conflictos con las tablas existentes.
Fase 2C.8 formaliza historial nutricional, BOA, diagnósticos, alertas,
seguimientos trimestrales y calendario nutricional.
"""

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS sn_valoraciones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fundacion_id INTEGER DEFAULT 1,
    usuario_creador_id INTEGER,
    tipo_documento TEXT,
    documento TEXT NOT NULL,
    nui TEXT,
    nombre_completo TEXT,
    fecha_nacimiento TEXT,
    edad_meses INTEGER DEFAULT 0,
    edad_texto TEXT,
    sexo TEXT,
    unidad TEXT,
    docente TEXT,
    acudiente TEXT,
    telefono TEXT,
    direccion TEXT,
    fecha_valoracion TEXT,
    peso_kg REAL,
    talla_cm REAL,
    imc REAL,
    perimetro_braquial_cm REAL,
    perimetro_cefalico_cm REAL,
    z_peso_edad REAL,
    z_talla_edad REAL,
    z_peso_talla REAL,
    z_imc_edad REAL,
    z_braquial_edad REAL,
    diag_peso_edad TEXT,
    diag_talla_edad TEXT,
    diag_peso_talla TEXT,
    diag_imc_edad TEXT,
    diag_braquial_edad TEXT,
    diagnostico_global TEXT,
    nivel_alerta TEXT DEFAULT 'VERDE',
    estado_control TEXT,
    trimestre TEXT,
    periodo TEXT,
    proximo_control TEXT,
    fuente_archivo TEXT,
    observaciones TEXT,
    activo INTEGER DEFAULT 1,
    fecha_carga TEXT NOT NULL,
    fecha_actualizacion TEXT,
    usuario_carga TEXT DEFAULT 'sistema'
);

CREATE INDEX IF NOT EXISTS idx_sn_valoraciones_documento ON sn_valoraciones(documento);
CREATE INDEX IF NOT EXISTS idx_sn_valoraciones_periodo ON sn_valoraciones(periodo);
CREATE INDEX IF NOT EXISTS idx_sn_valoraciones_unidad ON sn_valoraciones(unidad);
CREATE INDEX IF NOT EXISTS idx_sn_valoraciones_diagnostico ON sn_valoraciones(diagnostico_global);
CREATE INDEX IF NOT EXISTS idx_sn_valoraciones_fundacion ON sn_valoraciones(fundacion_id);

CREATE TABLE IF NOT EXISTS sn_alertas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fundacion_id INTEGER DEFAULT 1,
    usuario_creador_id INTEGER,
    documento TEXT,
    valoracion_id INTEGER,
    tipo TEXT NOT NULL,
    nivel TEXT DEFAULT 'AMARILLO',
    mensaje TEXT NOT NULL,
    unidad TEXT,
    fecha_alerta TEXT NOT NULL,
    atendida INTEGER DEFAULT 0,
    observaciones TEXT,
    fecha_creacion TEXT NOT NULL,
    fecha_actualizacion TEXT,
    FOREIGN KEY (valoracion_id) REFERENCES sn_valoraciones(id)
);

CREATE INDEX IF NOT EXISTS idx_sn_alertas_documento ON sn_alertas(documento);
CREATE INDEX IF NOT EXISTS idx_sn_alertas_nivel ON sn_alertas(nivel);
CREATE INDEX IF NOT EXISTS idx_sn_alertas_fundacion ON sn_alertas(fundacion_id);

CREATE TABLE IF NOT EXISTS sn_cargas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fundacion_id INTEGER DEFAULT 1,
    usuario_creador_id INTEGER,
    tipo TEXT NOT NULL,
    archivo_original TEXT,
    archivo_guardado TEXT,
    total_registros INTEGER DEFAULT 0,
    registros_validos INTEGER DEFAULT 0,
    registros_con_alerta INTEGER DEFAULT 0,
    errores_json TEXT,
    fecha_carga TEXT NOT NULL,
    fecha_actualizacion TEXT,
    usuario TEXT DEFAULT 'sistema'
);

CREATE TABLE IF NOT EXISTS sn_comparaciones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fundacion_id INTEGER DEFAULT 1,
    usuario_creador_id INTEGER,
    archivo_anterior TEXT,
    archivo_actual TEXT,
    total_anterior INTEGER DEFAULT 0,
    total_actual INTEGER DEFAULT 0,
    nuevos INTEGER DEFAULT 0,
    retirados INTEGER DEFAULT 0,
    trasladados INTEGER DEFAULT 0,
    cambios INTEGER DEFAULT 0,
    resumen_json TEXT,
    reporte_excel TEXT,
    reporte_pdf TEXT,
    fecha_comparacion TEXT NOT NULL,
    fecha_actualizacion TEXT,
    usuario TEXT DEFAULT 'sistema'
);

CREATE TABLE IF NOT EXISTS sn_calendario (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fundacion_id INTEGER DEFAULT 1,
    usuario_creador_id INTEGER,
    documento TEXT,
    valoracion_id INTEGER,
    tipo_evento TEXT NOT NULL,
    fecha_programada TEXT NOT NULL,
    estado TEXT DEFAULT 'PROGRAMADO',
    nivel TEXT DEFAULT 'VERDE',
    unidad TEXT,
    responsable TEXT,
    descripcion TEXT,
    fecha_creacion TEXT NOT NULL,
    fecha_actualizacion TEXT,
    FOREIGN KEY (valoracion_id) REFERENCES sn_valoraciones(id)
);

CREATE INDEX IF NOT EXISTS idx_sn_calendario_fecha ON sn_calendario(fecha_programada);
CREATE INDEX IF NOT EXISTS idx_sn_calendario_documento ON sn_calendario(documento);
CREATE INDEX IF NOT EXISTS idx_sn_calendario_fundacion ON sn_calendario(fundacion_id);

CREATE TABLE IF NOT EXISTS sn_adjuntos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fundacion_id INTEGER DEFAULT 1,
    usuario_creador_id INTEGER,
    documento TEXT,
    valoracion_id INTEGER,
    nombre_original TEXT,
    nombre_guardado TEXT,
    ruta_archivo TEXT,
    tipo TEXT,
    estado TEXT DEFAULT 'ACTIVO',
    fecha_carga TEXT NOT NULL,
    fecha_actualizacion TEXT,
    FOREIGN KEY (valoracion_id) REFERENCES sn_valoraciones(id)
);

CREATE TABLE IF NOT EXISTS sn_historial_acciones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fundacion_id INTEGER DEFAULT 1,
    usuario_creador_id INTEGER,
    usuario TEXT,
    accion TEXT NOT NULL,
    entidad_tipo TEXT,
    entidad_id INTEGER,
    documento TEXT,
    datos_anteriores TEXT,
    datos_nuevos TEXT,
    fecha_accion TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sn_referencias_oms (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fundacion_id INTEGER DEFAULT 1,
    indicador TEXT NOT NULL,
    sexo TEXT,
    edad_meses INTEGER,
    talla_cm REAL,
    medida REAL,
    sd3neg REAL,
    sd2neg REAL,
    sd1neg REAL,
    mediana REAL,
    sd1 REAL,
    sd2 REAL,
    sd3 REAL,
    fuente TEXT,
    fecha_carga TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_sn_referencias_indicador ON sn_referencias_oms(indicador, sexo, edad_meses);
"""
