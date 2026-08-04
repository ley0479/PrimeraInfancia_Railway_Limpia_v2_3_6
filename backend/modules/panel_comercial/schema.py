from __future__ import annotations

PANEL_COMERCIAL_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS pc_tickets_soporte (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fundacion_id INTEGER,
    titulo TEXT NOT NULL,
    descripcion TEXT,
    categoria TEXT DEFAULT 'Soporte general',
    prioridad TEXT DEFAULT 'MEDIA',
    estado TEXT DEFAULT 'ABIERTO',
    modulo_origen TEXT,
    usuario_creador_id INTEGER,
    usuario_asignado_id INTEGER,
    fecha_creacion TEXT NOT NULL,
    fecha_actualizacion TEXT,
    fecha_cierre TEXT,
    observaciones TEXT,
    FOREIGN KEY(fundacion_id) REFERENCES fundaciones(id),
    FOREIGN KEY(usuario_creador_id) REFERENCES usuarios_app(id),
    FOREIGN KEY(usuario_asignado_id) REFERENCES usuarios_app(id)
);

CREATE TABLE IF NOT EXISTS pc_ticket_comentarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id INTEGER NOT NULL,
    fundacion_id INTEGER,
    usuario_id INTEGER,
    comentario TEXT NOT NULL,
    archivo_nombre TEXT,
    archivo_ruta TEXT,
    fecha_creacion TEXT NOT NULL,
    FOREIGN KEY(ticket_id) REFERENCES pc_tickets_soporte(id),
    FOREIGN KEY(usuario_id) REFERENCES usuarios_app(id)
);

CREATE TABLE IF NOT EXISTS pc_alertas_pago (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fundacion_id INTEGER,
    tipo TEXT NOT NULL,
    nivel TEXT DEFAULT 'AMARILLO',
    mensaje TEXT NOT NULL,
    estado TEXT DEFAULT 'ABIERTA',
    referencia_tipo TEXT,
    referencia_id TEXT,
    fecha_creacion TEXT NOT NULL,
    fecha_actualizacion TEXT,
    FOREIGN KEY(fundacion_id) REFERENCES fundaciones(id)
);

CREATE TABLE IF NOT EXISTS pc_auditoria (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id INTEGER,
    username TEXT,
    fundacion_id INTEGER,
    accion TEXT NOT NULL,
    tabla_afectada TEXT,
    registro_id INTEGER,
    datos_anteriores TEXT,
    datos_nuevos TEXT,
    ip TEXT,
    user_agent TEXT,
    fecha TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_pc_tickets_fundacion ON pc_tickets_soporte(fundacion_id);
CREATE INDEX IF NOT EXISTS idx_pc_tickets_estado ON pc_tickets_soporte(estado);
CREATE INDEX IF NOT EXISTS idx_pc_tickets_prioridad ON pc_tickets_soporte(prioridad);
CREATE INDEX IF NOT EXISTS idx_pc_ticket_comentarios_fundacion ON pc_ticket_comentarios(fundacion_id, ticket_id);
CREATE INDEX IF NOT EXISTS idx_pc_alertas_fundacion ON pc_alertas_pago(fundacion_id);
CREATE INDEX IF NOT EXISTS idx_pc_alertas_estado ON pc_alertas_pago(estado);
"""

TICKET_ESTADOS = ['ABIERTO', 'EN_PROCESO', 'RESUELTO', 'CERRADO', 'ANULADO']
TICKET_PRIORIDADES = ['BAJA', 'MEDIA', 'ALTA', 'CRITICA']
TICKET_CATEGORIAS = ['Soporte general', 'Pago y suscripción', 'Créditos', 'Error técnico', 'Capacitación', 'Solicitud comercial', 'Mejora']
