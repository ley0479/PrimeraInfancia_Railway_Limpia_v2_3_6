"""Esquema del módulo Reportes Gerenciales Profesionales.

Tablas con prefijo rg_ para no interferir con módulos previos.
"""

RG_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS rg_reportes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fundacion_id INTEGER DEFAULT 1,
    usuario_id INTEGER,
    periodo TEXT NOT NULL,
    mes INTEGER NOT NULL,
    anio INTEGER NOT NULL,
    tipo TEXT DEFAULT 'MENSUAL',
    titulo TEXT,
    estado TEXT DEFAULT 'GENERADO',
    resumen_ejecutivo TEXT,
    indicadores_json TEXT,
    hallazgos_json TEXT,
    alertas_json TEXT,
    recomendaciones_json TEXT,
    pendientes_json TEXT,
    responsables_json TEXT,
    conclusion TEXT,
    ruta_pdf TEXT,
    ruta_excel TEXT,
    nombre_pdf TEXT,
    nombre_excel TEXT,
    total_indicadores INTEGER DEFAULT 0,
    total_hallazgos INTEGER DEFAULT 0,
    total_alertas INTEGER DEFAULT 0,
    total_pendientes INTEGER DEFAULT 0,
    fecha_generacion TEXT NOT NULL,
    fecha_actualizacion TEXT
);

CREATE TABLE IF NOT EXISTS rg_auditoria (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    reporte_id INTEGER,
    fundacion_id INTEGER DEFAULT 1,
    usuario_id INTEGER,
    accion TEXT NOT NULL,
    detalle TEXT,
    datos_json TEXT,
    fecha TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS rg_configuracion (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fundacion_id INTEGER DEFAULT 1,
    clave TEXT NOT NULL,
    valor TEXT,
    fecha_creacion TEXT NOT NULL,
    fecha_actualizacion TEXT,
    UNIQUE(fundacion_id, clave)
);
"""
