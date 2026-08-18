"""Esquema aislado para cruce mensual de bases Cuéntame.

Todas las tablas usan prefijo cb_ para no interferir con módulos existentes.
"""

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS cb_cruces (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fundacion_id INTEGER DEFAULT 1,
    usuario_id INTEGER,
    usuario TEXT,
    mes INTEGER,
    anio INTEGER,
    periodo TEXT,
    archivo_anterior TEXT,
    archivo_actual TEXT,
    ruta_anterior TEXT,
    ruta_actual TEXT,
    total_anterior INTEGER DEFAULT 0,
    total_actual INTEGER DEFAULT 0,
    nuevos INTEGER DEFAULT 0,
    retirados INTEGER DEFAULT 0,
    reemplazados INTEGER DEFAULT 0,
    trasladados INTEGER DEFAULT 0,
    cambios_unidad INTEGER DEFAULT 0,
    cambios_docente INTEGER DEFAULT 0,
    cambios_acudiente INTEGER DEFAULT 0,
    cambios_telefono INTEGER DEFAULT 0,
    cambios_direccion INTEGER DEFAULT 0,
    cambios_total INTEGER DEFAULT 0,
    resultado_json TEXT,
    errores_json TEXT,
    reporte_excel TEXT,
    reporte_pdf TEXT,
    fecha_cruce TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_cb_cruces_fundacion ON cb_cruces(fundacion_id);
CREATE INDEX IF NOT EXISTS idx_cb_cruces_periodo ON cb_cruces(periodo);
CREATE INDEX IF NOT EXISTS idx_cb_cruces_fecha ON cb_cruces(fecha_cruce);

CREATE TABLE IF NOT EXISTS cb_detalles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cruce_id INTEGER NOT NULL,
    fundacion_id INTEGER DEFAULT 1,
    tipo TEXT NOT NULL,
    documento TEXT,
    nombre TEXT,
    unidad_anterior TEXT,
    unidad_actual TEXT,
    docente_anterior TEXT,
    docente_actual TEXT,
    datos_json TEXT,
    fecha_creacion TEXT NOT NULL,
    FOREIGN KEY (cruce_id) REFERENCES cb_cruces(id)
);

CREATE INDEX IF NOT EXISTS idx_cb_detalles_cruce_tipo ON cb_detalles(cruce_id, tipo);
CREATE INDEX IF NOT EXISTS idx_cb_detalles_documento ON cb_detalles(documento);

CREATE TABLE IF NOT EXISTS cb_auditoria (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cruce_id INTEGER,
    fundacion_id INTEGER DEFAULT 1,
    usuario_id INTEGER,
    usuario TEXT,
    accion TEXT NOT NULL,
    detalle TEXT,
    fecha TEXT NOT NULL
);
"""
