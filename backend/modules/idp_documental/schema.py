IDP_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS idp_documentos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fundacion_id INTEGER NOT NULL,
    nombre_original TEXT NOT NULL,
    nombre_guardado TEXT NOT NULL,
    ruta_privada TEXT NOT NULL,
    extension TEXT NOT NULL,
    mime_type TEXT,
    tamano_bytes BIGINT NOT NULL,
    sha256 TEXT NOT NULL,
    tipo_documento TEXT DEFAULT 'NO_CLASIFICADO',
    confianza_clasificacion REAL DEFAULT 0,
    estado TEXT NOT NULL DEFAULT 'RECIBIDO',
    etapa TEXT NOT NULL DEFAULT 'RECIBIDO',
    progreso INTEGER NOT NULL DEFAULT 0,
    motor_lectura TEXT,
    resultado_bruto_json TEXT,
    resultado_canonico_json TEXT,
    validaciones_json TEXT,
    error_codigo TEXT,
    error_mensaje TEXT,
    usuario_carga_id INTEGER,
    usuario_aprobador_id INTEGER,
    fecha_carga TEXT NOT NULL,
    fecha_actualizacion TEXT NOT NULL,
    fecha_aprobacion TEXT,
    UNIQUE(fundacion_id, sha256)
);

CREATE TABLE IF NOT EXISTS idp_campos_extraidos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    documento_id BIGINT NOT NULL,
    fundacion_id INTEGER NOT NULL,
    ruta_canonica TEXT NOT NULL,
    valor_interpretado TEXT,
    texto_original TEXT,
    confianza REAL DEFAULT 0,
    estado_revision TEXT DEFAULT 'PENDIENTE',
    evidencia_json TEXT,
    motor TEXT,
    regla TEXT,
    usuario_correccion_id INTEGER,
    fecha_actualizacion TEXT NOT NULL,
    FOREIGN KEY(documento_id) REFERENCES idp_documentos(id)
);

CREATE TABLE IF NOT EXISTS idp_ejecuciones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    documento_id BIGINT NOT NULL,
    fundacion_id INTEGER NOT NULL,
    intento INTEGER NOT NULL DEFAULT 1,
    etapa TEXT NOT NULL,
    estado TEXT NOT NULL,
    motor TEXT,
    inicio TEXT NOT NULL,
    fin TEXT,
    error_codigo TEXT,
    error_mensaje TEXT,
    FOREIGN KEY(documento_id) REFERENCES idp_documentos(id)
);

CREATE TABLE IF NOT EXISTS idp_correcciones_humanas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    documento_id BIGINT NOT NULL,
    campo_id BIGINT,
    fundacion_id INTEGER NOT NULL,
    valor_anterior TEXT,
    valor_nuevo TEXT,
    motivo TEXT,
    usuario_id INTEGER,
    fecha TEXT NOT NULL,
    FOREIGN KEY(documento_id) REFERENCES idp_documentos(id),
    FOREIGN KEY(campo_id) REFERENCES idp_campos_extraidos(id)
);

CREATE TABLE IF NOT EXISTS idp_eventos_auditoria (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    documento_id BIGINT,
    fundacion_id INTEGER NOT NULL,
    evento TEXT NOT NULL,
    etapa TEXT,
    estado TEXT,
    detalle_json TEXT,
    usuario_id INTEGER,
    fecha TEXT NOT NULL,
    FOREIGN KEY(documento_id) REFERENCES idp_documentos(id)
);

CREATE INDEX IF NOT EXISTS idx_idp_documentos_tenant_estado ON idp_documentos(fundacion_id, estado);
CREATE INDEX IF NOT EXISTS idx_idp_campos_documento ON idp_campos_extraidos(documento_id, fundacion_id);
CREATE INDEX IF NOT EXISTS idx_idp_eventos_documento ON idp_eventos_auditoria(documento_id, fundacion_id);
"""
