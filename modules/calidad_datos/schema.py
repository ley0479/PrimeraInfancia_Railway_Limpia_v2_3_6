from __future__ import annotations

CALIDAD_DATOS_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS cd_analisis (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fundacion_id INTEGER DEFAULT 1,
    usuario_id INTEGER,
    usuario TEXT,
    tipo_fuente TEXT DEFAULT 'ARCHIVO',
    nombre_archivo TEXT,
    ruta_archivo TEXT,
    mes INTEGER,
    anio INTEGER,
    total_registros INTEGER DEFAULT 0,
    total_hallazgos INTEGER DEFAULT 0,
    hallazgos_criticos INTEGER DEFAULT 0,
    hallazgos_altos INTEGER DEFAULT 0,
    hallazgos_medios INTEGER DEFAULT 0,
    hallazgos_bajos INTEGER DEFAULT 0,
    estado TEXT DEFAULT 'GENERADO',
    resumen_json TEXT,
    errores_json TEXT,
    reporte_excel TEXT,
    reporte_pdf TEXT,
    fecha_analisis TEXT NOT NULL,
    fecha_actualizacion TEXT
);

CREATE TABLE IF NOT EXISTS cd_hallazgos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    analisis_id INTEGER NOT NULL,
    fundacion_id INTEGER DEFAULT 1,
    tipo TEXT NOT NULL,
    categoria TEXT,
    severidad TEXT DEFAULT 'MEDIA',
    documento TEXT,
    nombre TEXT,
    unidad TEXT,
    docente TEXT,
    campo TEXT,
    valor_actual TEXT,
    valor_esperado TEXT,
    descripcion TEXT,
    fila INTEGER,
    hoja TEXT,
    datos_json TEXT,
    estado TEXT DEFAULT 'ABIERTO',
    fecha_creacion TEXT NOT NULL,
    FOREIGN KEY (analisis_id) REFERENCES cd_analisis(id)
);

CREATE TABLE IF NOT EXISTS cd_auditoria (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    analisis_id INTEGER,
    accion TEXT NOT NULL,
    detalle TEXT,
    usuario_id INTEGER,
    usuario TEXT,
    fundacion_id INTEGER DEFAULT 1,
    fecha TEXT NOT NULL,
    ip TEXT
);

CREATE INDEX IF NOT EXISTS idx_cd_analisis_fundacion_fecha ON cd_analisis(fundacion_id, fecha_analisis);
CREATE INDEX IF NOT EXISTS idx_cd_hallazgos_analisis_tipo ON cd_hallazgos(analisis_id, tipo);
CREATE INDEX IF NOT EXISTS idx_cd_hallazgos_documento ON cd_hallazgos(documento);
CREATE INDEX IF NOT EXISTS idx_cd_hallazgos_unidad ON cd_hallazgos(unidad);
"""
