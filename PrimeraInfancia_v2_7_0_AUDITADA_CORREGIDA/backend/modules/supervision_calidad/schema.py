"""Esquema no destructivo del Centro Inteligente de Supervisión, Auditoría y Calidad."""
from __future__ import annotations

SCHEMA_VERSION = 1

SCHEMA_SQL = r"""
CREATE TABLE IF NOT EXISTS csc_checklist_catalogo (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fundacion_id INTEGER NOT NULL,
    codigo TEXT NOT NULL,
    componente TEXT NOT NULL,
    categoria TEXT NOT NULL,
    criterio TEXT NOT NULL,
    descripcion TEXT,
    evidencia_sugerida TEXT,
    nivel_riesgo TEXT DEFAULT 'MEDIO',
    obligatoria INTEGER DEFAULT 1,
    activa INTEGER DEFAULT 1,
    orden INTEGER DEFAULT 100,
    creada_por INTEGER,
    fecha_creacion TEXT NOT NULL,
    fecha_actualizacion TEXT NOT NULL,
    UNIQUE(fundacion_id, codigo)
);
CREATE INDEX IF NOT EXISTS idx_csc_catalogo_fund ON csc_checklist_catalogo(fundacion_id, activa, componente, orden);

CREATE TABLE IF NOT EXISTS csc_supervisiones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fundacion_id INTEGER NOT NULL,
    expediente_id INTEGER,
    unidad_id INTEGER,
    unidad_nombre TEXT NOT NULL,
    unidad_clave TEXT NOT NULL,
    contrato TEXT,
    vigencia TEXT,
    coordinador_nombre TEXT,
    tipo TEXT DEFAULT 'SEGUIMIENTO_INTERNO',
    modalidad TEXT DEFAULT 'REMOTA',
    titulo TEXT NOT NULL,
    objetivo TEXT,
    alcance TEXT,
    fecha_programada TEXT,
    fecha_inicio TEXT,
    fecha_fin TEXT,
    estado TEXT DEFAULT 'BORRADOR',
    porcentaje_cumplimiento REAL DEFAULT 0,
    resultado_general TEXT,
    supervisor_id INTEGER,
    supervisor_nombre TEXT,
    revisado_por INTEGER,
    aprobado_por INTEGER,
    fecha_revision TEXT,
    fecha_aprobacion TEXT,
    metadata_json TEXT,
    activa INTEGER DEFAULT 1,
    creada_por INTEGER,
    actualizada_por INTEGER,
    fecha_creacion TEXT NOT NULL,
    fecha_actualizacion TEXT NOT NULL,
    FOREIGN KEY(expediente_id) REFERENCES giu_expedientes_uca(id)
);
CREATE INDEX IF NOT EXISTS idx_csc_supervision_fund ON csc_supervisiones(fundacion_id, activa, estado, fecha_programada);
CREATE INDEX IF NOT EXISTS idx_csc_supervision_uca ON csc_supervisiones(fundacion_id, unidad_clave, vigencia);

CREATE TABLE IF NOT EXISTS csc_verificaciones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fundacion_id INTEGER NOT NULL,
    supervision_id INTEGER NOT NULL,
    criterio_id INTEGER,
    codigo_criterio TEXT NOT NULL,
    componente TEXT NOT NULL,
    categoria TEXT NOT NULL,
    criterio TEXT NOT NULL,
    resultado TEXT DEFAULT 'PENDIENTE',
    nivel_riesgo TEXT DEFAULT 'MEDIO',
    observaciones TEXT,
    evidencia_requerida INTEGER DEFAULT 0,
    evidencias_total INTEGER DEFAULT 0,
    requiere_hallazgo INTEGER DEFAULT 0,
    evaluado_por INTEGER,
    evaluado_por_nombre TEXT,
    fecha_evaluacion TEXT,
    fecha_creacion TEXT NOT NULL,
    fecha_actualizacion TEXT NOT NULL,
    UNIQUE(fundacion_id, supervision_id, codigo_criterio),
    FOREIGN KEY(supervision_id) REFERENCES csc_supervisiones(id),
    FOREIGN KEY(criterio_id) REFERENCES csc_checklist_catalogo(id)
);
CREATE INDEX IF NOT EXISTS idx_csc_verif_sup ON csc_verificaciones(fundacion_id, supervision_id, resultado);

CREATE TABLE IF NOT EXISTS csc_hallazgos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fundacion_id INTEGER NOT NULL,
    supervision_id INTEGER,
    verificacion_id INTEGER,
    expediente_id INTEGER,
    unidad_nombre TEXT,
    unidad_clave TEXT,
    componente TEXT NOT NULL,
    categoria TEXT,
    codigo TEXT NOT NULL,
    titulo TEXT NOT NULL,
    descripcion TEXT NOT NULL,
    criterio_afectado TEXT,
    nivel_riesgo TEXT DEFAULT 'MEDIO',
    tipo TEXT DEFAULT 'NO_CONFORMIDAD',
    estado TEXT DEFAULT 'ABIERTO',
    fecha_deteccion TEXT NOT NULL,
    fecha_limite TEXT,
    responsable_id INTEGER,
    responsable_nombre TEXT,
    requiere_plan INTEGER DEFAULT 1,
    origen_modulo TEXT DEFAULT 'SUPERVISION',
    origen_id INTEGER,
    resolucion_propuesta TEXT,
    resolucion_validada TEXT,
    validado_por INTEGER,
    fecha_validacion TEXT,
    cerrado_por INTEGER,
    fecha_cierre TEXT,
    motivo_cierre TEXT,
    activa INTEGER DEFAULT 1,
    creada_por INTEGER,
    actualizada_por INTEGER,
    fecha_creacion TEXT NOT NULL,
    fecha_actualizacion TEXT NOT NULL,
    UNIQUE(fundacion_id, codigo),
    FOREIGN KEY(supervision_id) REFERENCES csc_supervisiones(id),
    FOREIGN KEY(verificacion_id) REFERENCES csc_verificaciones(id),
    FOREIGN KEY(expediente_id) REFERENCES giu_expedientes_uca(id)
);
CREATE INDEX IF NOT EXISTS idx_csc_hallazgo_fund ON csc_hallazgos(fundacion_id, activa, estado, nivel_riesgo);
CREATE INDEX IF NOT EXISTS idx_csc_hallazgo_uca ON csc_hallazgos(fundacion_id, unidad_clave, estado);

CREATE TABLE IF NOT EXISTS csc_planes_mejora (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fundacion_id INTEGER NOT NULL,
    hallazgo_id INTEGER,
    expediente_id INTEGER,
    unidad_nombre TEXT,
    unidad_clave TEXT,
    codigo TEXT NOT NULL,
    nombre TEXT NOT NULL,
    objetivo TEXT NOT NULL,
    alcance TEXT,
    responsable_id INTEGER,
    responsable_nombre TEXT,
    fecha_inicio TEXT,
    fecha_limite TEXT,
    estado TEXT DEFAULT 'BORRADOR',
    progreso REAL DEFAULT 0,
    indicador_resultado TEXT,
    meta TEXT,
    observaciones TEXT,
    revisado_por INTEGER,
    aprobado_por INTEGER,
    fecha_revision TEXT,
    fecha_aprobacion TEXT,
    cerrado_por INTEGER,
    fecha_cierre TEXT,
    activa INTEGER DEFAULT 1,
    creada_por INTEGER,
    actualizada_por INTEGER,
    fecha_creacion TEXT NOT NULL,
    fecha_actualizacion TEXT NOT NULL,
    UNIQUE(fundacion_id, codigo),
    FOREIGN KEY(hallazgo_id) REFERENCES csc_hallazgos(id),
    FOREIGN KEY(expediente_id) REFERENCES giu_expedientes_uca(id)
);
CREATE INDEX IF NOT EXISTS idx_csc_plan_fund ON csc_planes_mejora(fundacion_id, activa, estado, fecha_limite);

CREATE TABLE IF NOT EXISTS csc_acciones_mejora (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fundacion_id INTEGER NOT NULL,
    plan_id INTEGER NOT NULL,
    titulo TEXT NOT NULL,
    descripcion TEXT,
    responsable_id INTEGER,
    responsable_nombre TEXT,
    fecha_inicio TEXT,
    fecha_limite TEXT,
    estado TEXT DEFAULT 'PENDIENTE',
    progreso REAL DEFAULT 0,
    evidencia_requerida INTEGER DEFAULT 1,
    evidencias_total INTEGER DEFAULT 0,
    resultado TEXT,
    validado_por INTEGER,
    fecha_validacion TEXT,
    creada_por INTEGER,
    actualizada_por INTEGER,
    fecha_creacion TEXT NOT NULL,
    fecha_actualizacion TEXT NOT NULL,
    FOREIGN KEY(plan_id) REFERENCES csc_planes_mejora(id)
);
CREATE INDEX IF NOT EXISTS idx_csc_accion_plan ON csc_acciones_mejora(fundacion_id, plan_id, estado, fecha_limite);

CREATE TABLE IF NOT EXISTS csc_seguimientos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fundacion_id INTEGER NOT NULL,
    entidad_tipo TEXT NOT NULL,
    entidad_id INTEGER NOT NULL,
    tipo TEXT DEFAULT 'SEGUIMIENTO',
    fecha TEXT NOT NULL,
    descripcion TEXT NOT NULL,
    resultado TEXT,
    proxima_fecha TEXT,
    estado TEXT DEFAULT 'REGISTRADO',
    usuario_id INTEGER,
    usuario_nombre TEXT,
    fecha_creacion TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_csc_seg_entidad ON csc_seguimientos(fundacion_id, entidad_tipo, entidad_id, fecha);

CREATE TABLE IF NOT EXISTS csc_evidencias (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fundacion_id INTEGER NOT NULL,
    entidad_tipo TEXT NOT NULL,
    entidad_id INTEGER NOT NULL,
    nombre_original TEXT NOT NULL,
    nombre_guardado TEXT NOT NULL,
    ruta_archivo TEXT NOT NULL,
    mime_type TEXT,
    tamano_bytes INTEGER DEFAULT 0,
    sha256 TEXT NOT NULL,
    version INTEGER DEFAULT 1,
    descripcion TEXT,
    cargada_por INTEGER,
    cargada_por_nombre TEXT,
    fecha_carga TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_csc_evidencia_ent ON csc_evidencias(fundacion_id, entidad_tipo, entidad_id, fecha_carga);

CREATE TABLE IF NOT EXISTS csc_productos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fundacion_id INTEGER NOT NULL,
    supervision_id INTEGER,
    expediente_id INTEGER,
    tipo_producto TEXT NOT NULL,
    nombre_archivo TEXT NOT NULL,
    ruta_archivo TEXT NOT NULL,
    mime_type TEXT,
    tamano_bytes INTEGER DEFAULT 0,
    sha256 TEXT NOT NULL,
    estado TEXT DEFAULT 'BORRADOR',
    generado_por INTEGER,
    fecha_generacion TEXT NOT NULL,
    metadata_json TEXT,
    FOREIGN KEY(supervision_id) REFERENCES csc_supervisiones(id),
    FOREIGN KEY(expediente_id) REFERENCES giu_expedientes_uca(id)
);
CREATE INDEX IF NOT EXISTS idx_csc_producto_fund ON csc_productos(fundacion_id, supervision_id, estado);

CREATE TABLE IF NOT EXISTS csc_auditoria (
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
CREATE INDEX IF NOT EXISTS idx_csc_auditoria_fund ON csc_auditoria(fundacion_id, fecha, accion);

CREATE TABLE IF NOT EXISTS csc_schema_version (
    id INTEGER PRIMARY KEY CHECK(id=1),
    version INTEGER NOT NULL,
    fecha_actualizacion TEXT NOT NULL
);
"""

DEFAULT_CHECKLIST = [
    ("CAL-DAT-01", "Administrativo y de Gestión", "Sistema de información", "La información de participantes, UCA y talento humano está completa, actualizada, oportuna, veraz y comprobable.", "Reporte de calidad de datos, RAM y Base Maestra", "ALTO", 10),
    ("CAL-DAT-02", "Administrativo y de Gestión", "Sistema de información", "Las fechas de vinculación, desvinculación y atenciones coinciden con la operación real y los soportes oficiales.", "Conciliación RAM, asistencia y Base Maestra", "ALTO", 20),
    ("CAL-RUT-01", "Administrativo y de Gestión", "Ruta operativa", "La UCA cuenta con evidencias suficientes de la fase y actividades operativas aplicables.", "Expediente Operativo por UCA", "ALTO", 30),
    ("CAL-FAM-01", "Familia, Comunidad y Redes Sociales", "Acompañamiento familiar", "Se evidencian acompañamientos, compromisos, participación y seguimiento a familias y cuidadores.", "Actas, listados, visitas y seguimientos", "MEDIO", 40),
    ("CAL-RED-01", "Familia, Comunidad y Redes Sociales", "Redes y articulación", "Existe directorio territorial y trazabilidad de articulaciones o activaciones de rutas cuando aplican.", "Directorio, comunicaciones y seguimientos", "ALTO", 50),
    ("CAL-SN-01", "Salud y Nutrición", "Atenciones priorizadas", "La UCA identifica y hace seguimiento a afiliación, vacunación, valoración integral, salud bucal y controles aplicables.", "Expediente de Salud y Nutrición", "ALTO", 60),
    ("CAL-SN-02", "Salud y Nutrición", "Seguimiento nutricional", "Las mediciones y alertas nutricionales cuentan con trazabilidad de revisión, canalización y seguimiento profesional.", "Historia antropométrica y alertas", "CRITICO", 70),
    ("CAL-PED-01", "Proceso Pedagógico", "Proyecto pedagógico", "El proyecto, las planeaciones, experiencias y seguimientos guardan coherencia con la caracterización y las evidencias.", "Proyecto pedagógico, planeaciones y bitácoras", "MEDIO", 80),
    ("CAL-TH-01", "Talento Humano", "Idoneidad e inducción", "El talento humano asignado cuenta con soportes de idoneidad, inducción, asignación y cualificación vigentes.", "Expedientes de talento humano", "ALTO", 90),
    ("CAL-AEP-01", "Ambientes Educativos y Protectores", "Condiciones de operación", "La infraestructura, dotación, saneamiento y gestión del riesgo cuentan con verificación y planes de acción.", "Listas de chequeo, inventarios y evidencias", "ALTO", 100),
    ("CAL-CONT-01", "Administrativo y de Gestión", "Cumplimiento contractual", "Los compromisos técnicos, administrativos y financieros del contrato cuentan con seguimiento y soporte.", "Matriz contractual, comités y productos", "ALTO", 110),
    ("CAL-PQRS-01", "Administrativo y de Gestión", "PQRSFD y control social", "Las PQRSFD, jornadas de socialización, control social y respuestas están registradas y trazables.", "Radicados, actas, respuestas y cierres", "MEDIO", 120),
    ("CAL-EVE-01", "Familia, Comunidad y Redes Sociales", "Eventos de violencia, lesiones o fallecimientos", "Los eventos reportables cuentan con seguimiento mensual, rutas, comunicaciones y actuaciones documentadas.", "Reporte oficial, póliza, rutas y seguimientos", "CRITICO", 130),
    ("CAL-MEJ-01", "Administrativo y de Gestión", "Mejora continua", "Los hallazgos y planes de mejora tienen responsables, fechas, evidencias y validación humana del cierre.", "Planes, acciones y seguimientos", "ALTO", 140),
]
