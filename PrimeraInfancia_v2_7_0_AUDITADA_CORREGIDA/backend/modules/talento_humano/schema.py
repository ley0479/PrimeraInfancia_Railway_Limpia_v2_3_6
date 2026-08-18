"""Esquema transicional de Talento Humano.

Fase 2C.7 conserva las tablas históricas, pero formaliza el núcleo de
Talento Humano como fuente maestra para coordinadores, agentes educativos, asignaciones
y equipo interdisciplinario.
"""
from __future__ import annotations

TALENTO_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS unidades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT,
    direccion TEXT,
    telefono TEXT,
    coordinador_id INTEGER,
    total_usuarios INTEGER DEFAULT 0,
    total_gestantes INTEGER DEFAULT 0,
    docente_asignado TEXT,
    docente_documento TEXT,
    coordinador_nombre TEXT,
    contrato TEXT,
    fundacion_id INTEGER DEFAULT 1,
    fecha_actualizacion TEXT
);

CREATE TABLE IF NOT EXISTS usuarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    documento TEXT,
    nombre TEXT,
    unidad TEXT,
    docente TEXT,
    fundacion_id INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS beneficiarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    documento TEXT,
    nombres TEXT,
    apellidos TEXT,
    nombre TEXT,
    unidad TEXT,
    docente TEXT,
    fundacion_id INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS coordinadores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    documento TEXT,
    nombre TEXT,
    nombres TEXT,
    apellidos TEXT,
    cargo TEXT,
    unidad TEXT,
    unidades TEXT,
    direccion TEXT,
    telefono TEXT,
    coordinador TEXT,
    tipo_equipo TEXT,
    contrato TEXT,
    perfil TEXT,
    estado TEXT DEFAULT 'activo',
    activo INTEGER DEFAULT 1,
    archivo TEXT,
    fecha_carga TEXT,
    fecha_ultima_actualizacion TEXT,
    fundacion_id INTEGER DEFAULT 1,
    usuario_creador_id INTEGER,
    fecha_creacion TEXT,
    fecha_actualizacion TEXT
);

CREATE TABLE IF NOT EXISTS docentes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    documento TEXT,
    nombres TEXT,
    apellidos TEXT,
    cargo TEXT,
    unidad TEXT,
    email TEXT,
    telefono TEXT,
    fecha_vinculacion TEXT,
    activo INTEGER DEFAULT 1,
    fecha_carga TEXT,
    fundacion_id INTEGER DEFAULT 1,
    usuario_creador_id INTEGER,
    fecha_creacion TEXT,
    fecha_actualizacion TEXT
);

CREATE TABLE IF NOT EXISTS th_personas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    documento TEXT,
    nombre TEXT NOT NULL,
    nombres TEXT,
    apellidos TEXT,
    cargo TEXT,
    tipo_equipo TEXT,
    rol_normalizado TEXT,
    unidad TEXT,
    direccion TEXT,
    telefono TEXT,
    coordinador TEXT,
    contrato TEXT,
    perfil TEXT,
    estado TEXT DEFAULT 'activo',
    activo INTEGER DEFAULT 1,
    origen_tabla TEXT DEFAULT 'coordinadores',
    origen_id INTEGER,
    archivo TEXT,
    fundacion_id INTEGER DEFAULT 1,
    usuario_creador_id INTEGER,
    fecha_creacion TEXT,
    fecha_actualizacion TEXT
);

CREATE TABLE IF NOT EXISTS th_asignaciones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    persona_id INTEGER,
    coordinador_id INTEGER,
    coordinador_nombre TEXT,
    unidad TEXT,
    rol TEXT,
    cargo TEXT,
    estado TEXT DEFAULT 'ACTIVO',
    fecha_inicio TEXT,
    fecha_fin TEXT,
    observaciones TEXT,
    fundacion_id INTEGER DEFAULT 1,
    usuario_creador_id INTEGER,
    fecha_creacion TEXT,
    fecha_actualizacion TEXT
);

CREATE TABLE IF NOT EXISTS th_historial (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    persona_id INTEGER,
    accion TEXT,
    datos_anteriores TEXT,
    datos_nuevos TEXT,
    usuario TEXT,
    fundacion_id INTEGER DEFAULT 1,
    fecha_accion TEXT
);

CREATE TABLE IF NOT EXISTS th_sincronizaciones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    origen TEXT,
    total_personas INTEGER DEFAULT 0,
    total_asignaciones INTEGER DEFAULT 0,
    resultado_json TEXT,
    usuario TEXT,
    fundacion_id INTEGER DEFAULT 1,
    fecha_sincronizacion TEXT
);

CREATE TABLE IF NOT EXISTS th_documentos (
    id INTEGER PRIMARY KEY AUTOINCREMENT, fundacion_id INTEGER NOT NULL,
    persona_id INTEGER NOT NULL, tipo TEXT NOT NULL, nombre TEXT NOT NULL,
    fecha_emision TEXT, fecha_vencimiento TEXT, estado TEXT DEFAULT 'VIGENTE',
    archivo_referencia TEXT, observaciones TEXT, validado_por INTEGER,
    fecha_validacion TEXT, creado_por INTEGER, fecha_creacion TEXT NOT NULL,
    fecha_actualizacion TEXT NOT NULL, FOREIGN KEY(persona_id) REFERENCES th_personas(id)
);
CREATE INDEX IF NOT EXISTS idx_th_documentos_persona ON th_documentos(fundacion_id,persona_id,estado,fecha_vencimiento);

CREATE TABLE IF NOT EXISTS th_formaciones (
    id INTEGER PRIMARY KEY AUTOINCREMENT, fundacion_id INTEGER NOT NULL,
    persona_id INTEGER NOT NULL, nombre TEXT NOT NULL, entidad TEXT,
    tipo TEXT DEFAULT 'FORMACION', fecha_inicio TEXT, fecha_fin TEXT,
    horas REAL DEFAULT 0, estado TEXT DEFAULT 'PROGRAMADA', certificado_referencia TEXT,
    calendario_entregable_id INTEGER, observaciones TEXT, creado_por INTEGER,
    fecha_creacion TEXT NOT NULL, fecha_actualizacion TEXT NOT NULL,
    FOREIGN KEY(persona_id) REFERENCES th_personas(id)
);
CREATE INDEX IF NOT EXISTS idx_th_formaciones_persona ON th_formaciones(fundacion_id,persona_id,estado,fecha_inicio);

CREATE TABLE IF NOT EXISTS th_evaluaciones (
    id INTEGER PRIMARY KEY AUTOINCREMENT, fundacion_id INTEGER NOT NULL,
    persona_id INTEGER NOT NULL, periodo TEXT NOT NULL, tipo TEXT DEFAULT 'ACOMPANAMIENTO',
    fortalezas TEXT, oportunidades TEXT, compromisos TEXT, resultado TEXT,
    estado TEXT DEFAULT 'BORRADOR', evaluador_id INTEGER, evaluador_nombre TEXT,
    validado_por INTEGER, fecha_validacion TEXT, fecha_evaluacion TEXT NOT NULL,
    fecha_creacion TEXT NOT NULL, fecha_actualizacion TEXT NOT NULL,
    FOREIGN KEY(persona_id) REFERENCES th_personas(id)
);
CREATE INDEX IF NOT EXISTS idx_th_evaluaciones_persona ON th_evaluaciones(fundacion_id,persona_id,periodo,estado);

CREATE TABLE IF NOT EXISTS th_capacidades (
    id INTEGER PRIMARY KEY AUTOINCREMENT, fundacion_id INTEGER NOT NULL,
    persona_id INTEGER NOT NULL, capacidad TEXT NOT NULL, nivel TEXT DEFAULT 'EN_DESARROLLO',
    interes_apoyo INTEGER DEFAULT 0, necesidad_formacion INTEGER DEFAULT 0,
    observaciones TEXT, actualizado_por INTEGER, fecha_actualizacion TEXT NOT NULL,
    UNIQUE(fundacion_id,persona_id,capacidad), FOREIGN KEY(persona_id) REFERENCES th_personas(id)
);
CREATE INDEX IF NOT EXISTS idx_th_capacidades_mapa ON th_capacidades(fundacion_id,capacidad,nivel);
"""


GP_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS gp_coordinadores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    contrato_id INTEGER,
    contrato TEXT,
    nombre TEXT NOT NULL,
    documento TEXT,
    telefono TEXT,
    email TEXT,
    cargo TEXT DEFAULT 'COORDINADOR',
    zona TEXT,
    unidades_json TEXT,
    observaciones TEXT,
    activo INTEGER DEFAULT 1,
    fecha_creacion TEXT,
    fecha_actualizacion TEXT,
    fundacion_id INTEGER DEFAULT 1,
    usuario_creador_id INTEGER,
    usuario_id INTEGER
);

CREATE TABLE IF NOT EXISTS gp_docentes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    coordinador_id INTEGER,
    nombre TEXT NOT NULL,
    documento TEXT,
    unidad TEXT,
    telefono TEXT,
    email TEXT,
    cargo TEXT DEFAULT 'DOCENTE',
    activo INTEGER DEFAULT 1,
    fecha_creacion TEXT,
    fecha_actualizacion TEXT,
    fundacion_id INTEGER DEFAULT 1,
    usuario_creador_id INTEGER,
    usuario_id INTEGER
);

CREATE TABLE IF NOT EXISTS gp_equipos_interdisciplinarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    coordinador_id INTEGER,
    nombre TEXT NOT NULL,
    documento TEXT,
    rol TEXT NOT NULL,
    profesion TEXT,
    telefono TEXT,
    email TEXT,
    activo INTEGER DEFAULT 1,
    fecha_creacion TEXT,
    fecha_actualizacion TEXT,
    fundacion_id INTEGER DEFAULT 1,
    usuario_creador_id INTEGER
);

CREATE TABLE IF NOT EXISTS gp_unidades_asignadas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    coordinador_id INTEGER NOT NULL,
    unidad TEXT NOT NULL,
    estado TEXT DEFAULT 'activo',
    fecha_creacion TEXT NOT NULL,
    fecha_actualizacion TEXT,
    fundacion_id INTEGER DEFAULT 1,
    usuario_creador_id INTEGER
);

CREATE TABLE IF NOT EXISTS gp_asignaciones_coordinador (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    coordinador_id INTEGER,
    tipo_talento TEXT,
    origen_tabla TEXT,
    origen_id INTEGER,
    nombre TEXT,
    documento TEXT,
    cargo TEXT,
    rol TEXT,
    unidad TEXT,
    telefono TEXT,
    email TEXT,
    estado TEXT DEFAULT 'ACTIVO',
    fecha_inicio TEXT,
    fecha_fin TEXT,
    observaciones TEXT,
    fecha_creacion TEXT,
    fecha_actualizacion TEXT,
    fundacion_id INTEGER DEFAULT 1,
    usuario_creador_id INTEGER
);

CREATE TABLE IF NOT EXISTS gp_historial_acciones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario TEXT,
    accion TEXT NOT NULL,
    entidad_tipo TEXT,
    entidad_id INTEGER,
    datos_anteriores TEXT,
    datos_nuevos TEXT,
    fecha_accion TEXT NOT NULL,
    fundacion_id INTEGER DEFAULT 1,
    usuario_creador_id INTEGER
);
"""

COORDINADORES_COLUMNS = {
    'documento': 'TEXT',
    'nombre': 'TEXT',
    'nombres': 'TEXT',
    'apellidos': 'TEXT',
    'cargo': 'TEXT',
    'unidad': 'TEXT',
    'unidades': 'TEXT',
    'direccion': 'TEXT',
    'telefono': 'TEXT',
    'coordinador': 'TEXT',
    'tipo_equipo': 'TEXT',
    'contrato': 'TEXT',
    'perfil': 'TEXT',
    'estado': "TEXT DEFAULT 'activo'",
    'activo': 'INTEGER DEFAULT 1',
    'archivo': 'TEXT',
    'fecha_carga': 'TEXT',
    'fecha_ultima_actualizacion': 'TEXT',
    'fundacion_id': 'INTEGER DEFAULT 1',
    'usuario_creador_id': 'INTEGER',
    'fecha_creacion': 'TEXT',
    'fecha_actualizacion': 'TEXT',
}

UNIDADES_COLUMNS = {
    'docente_asignado': 'TEXT',
    'docente_documento': 'TEXT',
    'coordinador_nombre': 'TEXT',
    'contrato': 'TEXT',
    'direccion': 'TEXT',
    'telefono': 'TEXT',
    'fecha_actualizacion': 'TEXT',
    'fundacion_id': 'INTEGER DEFAULT 1',
}


USUARIOS_COLUMNS = {
    'documento': 'TEXT',
    'nombre': 'TEXT',
    'unidad': 'TEXT',
    # Campo histórico usado por formatos RAM/RAN/asistencia.
    # Aunque internamente siga llamándose docente por compatibilidad, en UI se muestra como agente educativo.
    'docente': 'TEXT',
    'fundacion_id': 'INTEGER DEFAULT 1',
}

BENEFICIARIOS_COLUMNS = {
    'documento': 'TEXT',
    'nombres': 'TEXT',
    'apellidos': 'TEXT',
    'nombre': 'TEXT',
    'unidad': 'TEXT',
    # Corrige bases antiguas que tenían docente_id pero no docente.
    # La sincronización escribe aquí el Agente Educativo responsable de la UDS.
    'docente': 'TEXT',
    'fundacion_id': 'INTEGER DEFAULT 1',
}

GP_COMMON_COLUMNS = {
    'fundacion_id': 'INTEGER DEFAULT 1',
    'usuario_creador_id': 'INTEGER',
    'fecha_actualizacion': 'TEXT',
}

TH_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_th_personas_documento ON th_personas(documento)",
    "CREATE INDEX IF NOT EXISTS idx_th_personas_fundacion ON th_personas(fundacion_id)",
    "CREATE INDEX IF NOT EXISTS idx_th_personas_rol ON th_personas(rol_normalizado)",
    "CREATE INDEX IF NOT EXISTS idx_th_personas_unidad ON th_personas(unidad)",
    "CREATE INDEX IF NOT EXISTS idx_th_asignaciones_persona ON th_asignaciones(persona_id)",
    "CREATE INDEX IF NOT EXISTS idx_th_asignaciones_coordinador ON th_asignaciones(coordinador_id)",
    "CREATE INDEX IF NOT EXISTS idx_th_asignaciones_fundacion ON th_asignaciones(fundacion_id)",
]
