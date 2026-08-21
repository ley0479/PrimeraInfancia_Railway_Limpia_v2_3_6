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

CREATE TABLE IF NOT EXISTS idp_resultados_validacion (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    documento_id BIGINT NOT NULL,
    fundacion_id INTEGER NOT NULL,
    ruta_canonica TEXT,
    regla TEXT NOT NULL,
    nivel TEXT NOT NULL,
    estado TEXT NOT NULL,
    mensaje TEXT NOT NULL,
    esperado_json TEXT,
    evidencia_json TEXT,
    resuelto INTEGER DEFAULT 0,
    fecha TEXT NOT NULL,
    FOREIGN KEY(documento_id) REFERENCES idp_documentos(id)
);

CREATE TABLE IF NOT EXISTS idp_lotes_importacion (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    documento_id BIGINT NOT NULL,
    fundacion_id INTEGER NOT NULL,
    tipo_documento TEXT NOT NULL,
    fecha_actividad TEXT NOT NULL,
    actividad TEXT,
    unidad_servicio TEXT,
    total_registros INTEGER NOT NULL DEFAULT 0,
    usuario_id INTEGER,
    fecha_importacion TEXT NOT NULL,
    UNIQUE(documento_id, fundacion_id),
    FOREIGN KEY(documento_id) REFERENCES idp_documentos(id)
);

CREATE TABLE IF NOT EXISTS idp_asistencias_importadas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lote_id BIGINT NOT NULL,
    documento_id BIGINT NOT NULL,
    fundacion_id INTEGER NOT NULL,
    indice_participante INTEGER NOT NULL,
    documento_participante TEXT NOT NULL,
    nombre_completo TEXT,
    unidad_servicio TEXT,
    fecha_actividad TEXT NOT NULL,
    actividad TEXT,
    asistio INTEGER,
    firma_presente INTEGER,
    evidencia_json TEXT,
    fecha_importacion TEXT NOT NULL,
    UNIQUE(documento_id, fundacion_id, indice_participante),
    FOREIGN KEY(lote_id) REFERENCES idp_lotes_importacion(id),
    FOREIGN KEY(documento_id) REFERENCES idp_documentos(id)
);

CREATE TABLE IF NOT EXISTS idp_trabajos_cola (
    id TEXT PRIMARY KEY,
    documento_id BIGINT NOT NULL,
    fundacion_id INTEGER NOT NULL,
    tipo_trabajo TEXT NOT NULL DEFAULT 'EXTRAER_DOCUMENTO',
    estado TEXT NOT NULL DEFAULT 'PENDIENTE',
    etapa TEXT NOT NULL DEFAULT 'EN_COLA',
    progreso INTEGER NOT NULL DEFAULT 0,
    intentos INTEGER NOT NULL DEFAULT 0,
    max_intentos INTEGER NOT NULL DEFAULT 3,
    disponible_desde TEXT NOT NULL,
    bloqueado_por TEXT,
    fecha_bloqueo TEXT,
    error_codigo TEXT,
    error_mensaje TEXT,
    fecha_creacion TEXT NOT NULL,
    fecha_actualizacion TEXT NOT NULL,
    fecha_fin TEXT,
    UNIQUE(documento_id, fundacion_id, tipo_trabajo),
    FOREIGN KEY(documento_id) REFERENCES idp_documentos(id)
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
CREATE INDEX IF NOT EXISTS idx_idp_validaciones_documento ON idp_resultados_validacion(documento_id, fundacion_id, nivel);
CREATE INDEX IF NOT EXISTS idx_idp_lotes_tenant_fecha ON idp_lotes_importacion(fundacion_id, fecha_actividad);
CREATE INDEX IF NOT EXISTS idx_idp_asistencias_tenant_doc ON idp_asistencias_importadas(fundacion_id, documento_participante, fecha_actividad);
CREATE INDEX IF NOT EXISTS idx_idp_cola_estado_disponible ON idp_trabajos_cola(estado, disponible_desde, fecha_creacion);
"""
