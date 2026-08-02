from __future__ import annotations

GERENCIA_GENERAL_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS gg_auditoria (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fundacion_id INTEGER,
    usuario_id INTEGER,
    accion TEXT NOT NULL,
    detalle TEXT,
    datos TEXT,
    ip TEXT,
    user_agent TEXT,
    fecha TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS gg_configuracion (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fundacion_id INTEGER,
    clave TEXT NOT NULL,
    valor TEXT,
    fecha_creacion TEXT NOT NULL,
    fecha_actualizacion TEXT,
    UNIQUE(fundacion_id, clave)
);

CREATE INDEX IF NOT EXISTS idx_gg_auditoria_fundacion ON gg_auditoria(fundacion_id);
CREATE INDEX IF NOT EXISTS idx_gg_auditoria_fecha ON gg_auditoria(fecha);
CREATE INDEX IF NOT EXISTS idx_gg_config_fundacion ON gg_configuracion(fundacion_id);
"""
