from __future__ import annotations

BACKUPS_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS backups_sistema (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    archivo TEXT NOT NULL,
    ruta_archivo TEXT NOT NULL,
    motivo TEXT NOT NULL,
    descripcion TEXT,
    sha256 TEXT NOT NULL,
    tamano_bytes INTEGER DEFAULT 0,
    estado TEXT DEFAULT 'VALIDO',
    integridad TEXT DEFAULT 'PENDIENTE',
    creado_por_id INTEGER,
    creado_por TEXT,
    fundacion_id INTEGER DEFAULT 1,
    fecha_creacion TEXT NOT NULL,
    fecha_validacion TEXT
);

CREATE TABLE IF NOT EXISTS backups_auditoria (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    backup_id INTEGER,
    accion TEXT NOT NULL,
    detalle TEXT,
    usuario_id INTEGER,
    username TEXT,
    fundacion_id INTEGER DEFAULT 1,
    fecha TEXT NOT NULL,
    ip TEXT,
    FOREIGN KEY (backup_id) REFERENCES backups_sistema(id)
);

CREATE INDEX IF NOT EXISTS idx_backups_sistema_fecha ON backups_sistema(fecha_creacion);
CREATE INDEX IF NOT EXISTS idx_backups_sistema_motivo ON backups_sistema(motivo);
CREATE INDEX IF NOT EXISTS idx_backups_sistema_estado ON backups_sistema(estado);
"""
