SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS ayuda_progreso_usuario (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fundacion_id INTEGER NOT NULL,
    usuario_id INTEGER NOT NULL,
    modulo TEXT NOT NULL,
    recorrido_completado INTEGER DEFAULT 0,
    recorrido_omitido INTEGER DEFAULT 0,
    veces_abierto INTEGER DEFAULT 0,
    ultima_apertura TEXT,
    fecha_creacion TEXT NOT NULL,
    fecha_actualizacion TEXT,
    UNIQUE (fundacion_id, usuario_id, modulo)
);
CREATE INDEX IF NOT EXISTS idx_ayuda_progreso_usuario
ON ayuda_progreso_usuario(fundacion_id, usuario_id, modulo);
"""
