from __future__ import annotations

SCHEMA_VERSION = 3

SCHEMA_SQL = r"""
CREATE TABLE IF NOT EXISTS giu_expedientes_uca (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fundacion_id INTEGER NOT NULL,
    unidad_id INTEGER,
    unidad_nombre TEXT NOT NULL,
    unidad_clave TEXT NOT NULL,
    codigo_unidad TEXT,
    contrato TEXT DEFAULT '',
    vigencia TEXT NOT NULL,
    servicio_modalidad TEXT,
    fase_actual TEXT DEFAULT 'PREPARATORIA',
    estado TEXT DEFAULT 'ACTIVO',
    coordinador_id INTEGER,
    coordinador_nombre TEXT,
    porcentaje_global REAL DEFAULT 0,
    semaforo TEXT DEFAULT 'ROJO',
    observaciones TEXT,
    creado_por INTEGER,
    actualizado_por INTEGER,
    fecha_creacion TEXT NOT NULL,
    fecha_actualizacion TEXT NOT NULL,
    UNIQUE(fundacion_id, unidad_clave, vigencia, contrato)
);

CREATE INDEX IF NOT EXISTS idx_giu_expediente_fundacion ON giu_expedientes_uca(fundacion_id, vigencia, estado);
CREATE INDEX IF NOT EXISTS idx_giu_expediente_unidad ON giu_expedientes_uca(fundacion_id, unidad_clave);

CREATE TABLE IF NOT EXISTS giu_ruta_catalogo (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo TEXT UNIQUE NOT NULL,
    fase TEXT NOT NULL,
    orden INTEGER NOT NULL,
    titulo TEXT NOT NULL,
    descripcion TEXT,
    componente TEXT,
    obligatoria INTEGER DEFAULT 1,
    requiere_evidencia INTEGER DEFAULT 1,
    roles_json TEXT,
    evidencias_json TEXT,
    activo INTEGER DEFAULT 1,
    hash_definicion TEXT,
    fecha_creacion TEXT NOT NULL,
    fecha_actualizacion TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_giu_catalogo_fase ON giu_ruta_catalogo(fase, orden, activo);

CREATE TABLE IF NOT EXISTS giu_ruta_instancias (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fundacion_id INTEGER NOT NULL,
    expediente_id INTEGER NOT NULL,
    catalogo_id INTEGER NOT NULL,
    actividad_codigo TEXT NOT NULL,
    estado TEXT DEFAULT 'PENDIENTE',
    responsable_id INTEGER,
    responsable_nombre TEXT,
    fecha_inicio TEXT,
    fecha_limite TEXT,
    fecha_finalizacion TEXT,
    porcentaje REAL DEFAULT 0,
    observaciones TEXT,
    justificacion_no_aplica TEXT,
    revisado_por INTEGER,
    aprobado_por INTEGER,
    creado_por INTEGER,
    actualizado_por INTEGER,
    fecha_creacion TEXT NOT NULL,
    fecha_actualizacion TEXT NOT NULL,
    UNIQUE(expediente_id, actividad_codigo),
    FOREIGN KEY(expediente_id) REFERENCES giu_expedientes_uca(id),
    FOREIGN KEY(catalogo_id) REFERENCES giu_ruta_catalogo(id)
);

CREATE INDEX IF NOT EXISTS idx_giu_instancia_expediente ON giu_ruta_instancias(fundacion_id, expediente_id, estado);
CREATE INDEX IF NOT EXISTS idx_giu_instancia_fecha ON giu_ruta_instancias(fundacion_id, fecha_limite, estado);

CREATE TABLE IF NOT EXISTS giu_ruta_evidencias (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fundacion_id INTEGER NOT NULL,
    expediente_id INTEGER NOT NULL,
    instancia_id INTEGER NOT NULL,
    nombre_original TEXT NOT NULL,
    nombre_guardado TEXT NOT NULL,
    ruta_archivo TEXT NOT NULL,
    mime_type TEXT,
    tamano_bytes INTEGER DEFAULT 0,
    sha256 TEXT NOT NULL,
    version INTEGER DEFAULT 1,
    activo INTEGER DEFAULT 1,
    observaciones TEXT,
    cargado_por INTEGER,
    fecha_carga TEXT NOT NULL,
    FOREIGN KEY(expediente_id) REFERENCES giu_expedientes_uca(id),
    FOREIGN KEY(instancia_id) REFERENCES giu_ruta_instancias(id)
);

CREATE INDEX IF NOT EXISTS idx_giu_evidencia_instancia ON giu_ruta_evidencias(fundacion_id, instancia_id, activo);
CREATE INDEX IF NOT EXISTS idx_giu_evidencia_sha ON giu_ruta_evidencias(fundacion_id, sha256);

CREATE TABLE IF NOT EXISTS giu_planes_uca (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fundacion_id INTEGER NOT NULL,
    expediente_id INTEGER NOT NULL,
    codigo TEXT NOT NULL,
    nombre TEXT NOT NULL,
    responsable_id INTEGER,
    responsable_nombre TEXT,
    estado TEXT DEFAULT 'BORRADOR',
    fecha_inicio TEXT,
    fecha_fin TEXT,
    progreso REAL DEFAULT 0,
    objetivos_json TEXT,
    actividades_json TEXT,
    indicadores_json TEXT,
    observaciones TEXT,
    creado_por INTEGER,
    actualizado_por INTEGER,
    fecha_creacion TEXT NOT NULL,
    fecha_actualizacion TEXT NOT NULL,
    UNIQUE(expediente_id, codigo),
    FOREIGN KEY(expediente_id) REFERENCES giu_expedientes_uca(id)
);

CREATE INDEX IF NOT EXISTS idx_giu_planes_expediente ON giu_planes_uca(fundacion_id, expediente_id, estado);

CREATE TABLE IF NOT EXISTS biblioteca_icbf_documentos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fundacion_id INTEGER NOT NULL,
    codigo TEXT NOT NULL,
    nombre TEXT NOT NULL,
    tipo_documento TEXT DEFAULT 'DOCUMENTO_TECNICO',
    modalidad TEXT,
    componente TEXT,
    descripcion TEXT,
    fuente_tipo TEXT DEFAULT 'MANUAL',
    fuente_url TEXT,
    verificacion_automatica INTEGER DEFAULT 0,
    activo INTEGER DEFAULT 1,
    creado_por INTEGER,
    actualizado_por INTEGER,
    fecha_creacion TEXT NOT NULL,
    fecha_actualizacion TEXT NOT NULL,
    UNIQUE(fundacion_id, codigo)
);

CREATE INDEX IF NOT EXISTS idx_biblioteca_documentos_fund ON biblioteca_icbf_documentos(fundacion_id, activo, componente);

CREATE TABLE IF NOT EXISTS biblioteca_icbf_versiones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fundacion_id INTEGER NOT NULL,
    documento_id INTEGER NOT NULL,
    version TEXT NOT NULL,
    fecha_documento TEXT,
    fecha_vigencia_desde TEXT,
    fecha_vigencia_hasta TEXT,
    estado TEXT DEFAULT 'BORRADOR',
    nombre_original TEXT,
    nombre_guardado TEXT,
    ruta_archivo TEXT,
    mime_type TEXT,
    tamano_bytes INTEGER DEFAULT 0,
    sha256 TEXT,
    fuente_url TEXT,
    notas_cambio TEXT,
    verificada INTEGER DEFAULT 0,
    aprobada_por INTEGER,
    fecha_aprobacion TEXT,
    fecha_ultima_verificacion TEXT,
    estado_ultima_verificacion TEXT,
    creado_por INTEGER,
    fecha_creacion TEXT NOT NULL,
    fecha_actualizacion TEXT NOT NULL,
    UNIQUE(fundacion_id, documento_id, version),
    FOREIGN KEY(documento_id) REFERENCES biblioteca_icbf_documentos(id)
);

CREATE INDEX IF NOT EXISTS idx_biblioteca_versiones_doc ON biblioteca_icbf_versiones(fundacion_id, documento_id, estado);

CREATE TABLE IF NOT EXISTS biblioteca_icbf_relaciones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fundacion_id INTEGER NOT NULL,
    documento_id INTEGER NOT NULL,
    version_id INTEGER,
    modulo TEXT NOT NULL,
    tipo_relacion TEXT DEFAULT 'REFERENCIA',
    obligatorio INTEGER DEFAULT 0,
    observaciones TEXT,
    creado_por INTEGER,
    fecha_creacion TEXT NOT NULL,
    UNIQUE(fundacion_id, documento_id, version_id, modulo, tipo_relacion),
    FOREIGN KEY(documento_id) REFERENCES biblioteca_icbf_documentos(id),
    FOREIGN KEY(version_id) REFERENCES biblioteca_icbf_versiones(id)
);

CREATE INDEX IF NOT EXISTS idx_biblioteca_relaciones_modulo ON biblioteca_icbf_relaciones(fundacion_id, modulo);


CREATE TABLE IF NOT EXISTS biblioteca_icbf_fuentes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fundacion_id INTEGER NOT NULL,
    codigo TEXT NOT NULL,
    nombre TEXT NOT NULL,
    tipo_fuente TEXT DEFAULT 'MANUAL',
    mecanismo TEXT DEFAULT 'MANUAL',
    url_base TEXT,
    dominio_permitido TEXT,
    autorizada INTEGER DEFAULT 0,
    habilitada INTEGER DEFAULT 0,
    intervalo_horas INTEGER DEFAULT 24,
    configuracion_json TEXT,
    ultimo_etag TEXT,
    ultima_modificacion TEXT,
    fecha_ultima_revision TEXT,
    estado_ultima_revision TEXT,
    detalle_ultima_revision TEXT,
    creado_por INTEGER,
    actualizado_por INTEGER,
    fecha_creacion TEXT NOT NULL,
    fecha_actualizacion TEXT NOT NULL,
    UNIQUE(fundacion_id, codigo)
);
CREATE INDEX IF NOT EXISTS idx_biblioteca_fuentes_fund ON biblioteca_icbf_fuentes(fundacion_id, habilitada, autorizada);

CREATE TABLE IF NOT EXISTS biblioteca_icbf_candidatos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fundacion_id INTEGER NOT NULL,
    fuente_id INTEGER,
    documento_id INTEGER,
    codigo_documento TEXT NOT NULL,
    nombre_documento TEXT,
    version_detectada TEXT NOT NULL,
    fecha_documento TEXT,
    fecha_vigencia_desde TEXT,
    fuente_url TEXT,
    sha256_esperado TEXT,
    etag TEXT,
    ultima_modificacion TEXT,
    candidato_hash TEXT NOT NULL,
    payload_json TEXT,
    estado TEXT DEFAULT 'DETECTADA',
    observaciones TEXT,
    detectado_por INTEGER,
    revisado_por INTEGER,
    aprobado_por INTEGER,
    fecha_deteccion TEXT NOT NULL,
    fecha_revision TEXT,
    fecha_aprobacion TEXT,
    fecha_aplicacion TEXT,
    UNIQUE(fundacion_id, candidato_hash),
    FOREIGN KEY(fuente_id) REFERENCES biblioteca_icbf_fuentes(id),
    FOREIGN KEY(documento_id) REFERENCES biblioteca_icbf_documentos(id)
);
CREATE INDEX IF NOT EXISTS idx_biblioteca_candidatos_fund ON biblioteca_icbf_candidatos(fundacion_id, estado, fecha_deteccion);

CREATE TABLE IF NOT EXISTS biblioteca_icbf_notificaciones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fundacion_id INTEGER NOT NULL,
    documento_id INTEGER,
    version_id INTEGER,
    candidato_id INTEGER,
    modulo TEXT,
    nivel TEXT DEFAULT 'INFO',
    titulo TEXT NOT NULL,
    mensaje TEXT NOT NULL,
    accion_url TEXT,
    leida INTEGER DEFAULT 0,
    fecha_lectura TEXT,
    creada_en TEXT NOT NULL,
    FOREIGN KEY(documento_id) REFERENCES biblioteca_icbf_documentos(id),
    FOREIGN KEY(version_id) REFERENCES biblioteca_icbf_versiones(id),
    FOREIGN KEY(candidato_id) REFERENCES biblioteca_icbf_candidatos(id)
);
CREATE INDEX IF NOT EXISTS idx_biblioteca_notificaciones_fund ON biblioteca_icbf_notificaciones(fundacion_id, leida, creada_en);

CREATE TABLE IF NOT EXISTS biblioteca_icbf_historial (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fundacion_id INTEGER NOT NULL,
    documento_id INTEGER,
    version_id INTEGER,
    candidato_id INTEGER,
    usuario_id INTEGER,
    usuario TEXT,
    accion TEXT NOT NULL,
    estado_anterior TEXT,
    estado_nuevo TEXT,
    detalle_json TEXT,
    fecha TEXT NOT NULL,
    FOREIGN KEY(documento_id) REFERENCES biblioteca_icbf_documentos(id),
    FOREIGN KEY(version_id) REFERENCES biblioteca_icbf_versiones(id),
    FOREIGN KEY(candidato_id) REFERENCES biblioteca_icbf_candidatos(id)
);
CREATE INDEX IF NOT EXISTS idx_biblioteca_historial_fund ON biblioteca_icbf_historial(fundacion_id, fecha, accion);

CREATE TABLE IF NOT EXISTS giu_auditoria (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fundacion_id INTEGER NOT NULL,
    usuario_id INTEGER,
    usuario TEXT,
    accion TEXT NOT NULL,
    entidad TEXT NOT NULL,
    entidad_id INTEGER,
    detalle_json TEXT,
    fecha TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_giu_auditoria_fund ON giu_auditoria(fundacion_id, fecha, accion);



CREATE TABLE IF NOT EXISTS giu_vinculos_documentales (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fundacion_id INTEGER NOT NULL,
    expediente_id INTEGER NOT NULL,
    source_module TEXT NOT NULL,
    source_table TEXT NOT NULL,
    source_id INTEGER NOT NULL,
    categoria TEXT,
    titulo TEXT NOT NULL,
    estado TEXT,
    fecha_documento TEXT,
    file_name TEXT,
    file_path TEXT,
    mime_type TEXT,
    sha256 TEXT,
    version TEXT,
    metadata_json TEXT,
    origen TEXT DEFAULT 'AUTOMATICO',
    activo INTEGER DEFAULT 1,
    fecha_sincronizacion TEXT NOT NULL,
    UNIQUE(fundacion_id, expediente_id, source_table, source_id),
    FOREIGN KEY(expediente_id) REFERENCES giu_expedientes_uca(id)
);

CREATE INDEX IF NOT EXISTS idx_giu_vinculos_exp ON giu_vinculos_documentales(fundacion_id, expediente_id, activo);
CREATE INDEX IF NOT EXISTS idx_giu_vinculos_fuente ON giu_vinculos_documentales(fundacion_id, source_table, source_id);

CREATE TABLE IF NOT EXISTS giu_paquetes_supervision (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fundacion_id INTEGER NOT NULL,
    expediente_id INTEGER NOT NULL,
    nombre_archivo TEXT NOT NULL,
    ruta_archivo TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    tamano_bytes INTEGER DEFAULT 0,
    resumen_json TEXT,
    generado_por INTEGER,
    fecha_generacion TEXT NOT NULL,
    FOREIGN KEY(expediente_id) REFERENCES giu_expedientes_uca(id)
);

CREATE INDEX IF NOT EXISTS idx_giu_paquetes_exp ON giu_paquetes_supervision(fundacion_id, expediente_id, fecha_generacion);

CREATE TABLE IF NOT EXISTS giu_schema_version (
    id INTEGER PRIMARY KEY CHECK(id=1),
    version INTEGER NOT NULL,
    catalogo_hash TEXT,
    fecha_actualizacion TEXT NOT NULL
);
"""

DEFAULT_PLANS = [
    ("ARTICULACION", "Plan de articulación interinstitucional y comunitaria"),
    ("FAMILIAS", "Plan de formación y acompañamiento a las familias"),
    ("PEDAGOGICO", "Proyecto pedagógico"),
    ("SANEAMIENTO", "Plan de saneamiento básico"),
    ("RIESGO_ACCIDENTES", "Plan de gestión de riesgos de accidentes"),
    ("RIESGO_DESASTRES", "Plan de gestión de riesgos de desastres"),
    ("CUALIFICACION_TH", "Plan de cualificación del talento humano intercultural"),
    ("CALIDAD_ATENCION", "Plan de gestión de calidad de la atención"),
]
