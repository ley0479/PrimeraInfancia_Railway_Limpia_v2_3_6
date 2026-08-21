from __future__ import annotations


DOCUMENTS_SCHEMA_VERSION = "1"

DOCUMENTS_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS doc_tipos_documento (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 codigo TEXT NOT NULL UNIQUE, nombre TEXT NOT NULL, componente TEXT NOT NULL,
 requiere_capture INTEGER DEFAULT 0, activo INTEGER DEFAULT 1,
 creado_en TEXT NOT NULL, actualizado_en TEXT
);
CREATE TABLE IF NOT EXISTS doc_plantillas (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 codigo TEXT NOT NULL, nombre TEXT NOT NULL, componente TEXT NOT NULL,
 tipo_documento TEXT NOT NULL, scope TEXT NOT NULL DEFAULT 'FUNDACION',
 fundacion_id INTEGER, estado TEXT NOT NULL DEFAULT 'CARGADA', protegida INTEGER DEFAULT 1,
 creado_por INTEGER, creado_en TEXT NOT NULL, actualizado_en TEXT,
 UNIQUE(fundacion_id,codigo)
);
CREATE TABLE IF NOT EXISTS doc_plantilla_versiones (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 plantilla_id INTEGER NOT NULL, fundacion_id INTEGER, version TEXT NOT NULL,
 nombre_original TEXT NOT NULL, nombre_seguro TEXT NOT NULL, ruta_privada TEXT NOT NULL,
 mime_type TEXT, extension TEXT NOT NULL, hash_sha256 TEXT NOT NULL,
 fecha_vigencia_desde TEXT, fecha_vigencia_hasta TEXT, capacidad_por_pagina INTEGER,
 estado TEXT NOT NULL DEFAULT 'CARGADA', inspeccion_json TEXT, mapa_version INTEGER DEFAULT 0,
 usuario_creador_id INTEGER, usuario_aprobador_id INTEGER,
 creado_en TEXT NOT NULL, actualizado_en TEXT,
 UNIQUE(plantilla_id,version), UNIQUE(fundacion_id,hash_sha256),
 FOREIGN KEY(plantilla_id) REFERENCES doc_plantillas(id)
);
CREATE TABLE IF NOT EXISTS doc_mapeos (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 plantilla_version_id INTEGER NOT NULL, fundacion_id INTEGER, version INTEGER NOT NULL,
 estado TEXT NOT NULL DEFAULT 'PROPUESTO', mapa_json TEXT NOT NULL,
 usuario_creador_id INTEGER, usuario_aprobador_id INTEGER,
 creado_en TEXT NOT NULL, aprobado_en TEXT,
 UNIQUE(plantilla_version_id,version),
 FOREIGN KEY(plantilla_version_id) REFERENCES doc_plantilla_versiones(id)
);
CREATE TABLE IF NOT EXISTS doc_catalogos_respuesta (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 codigo TEXT NOT NULL, categoria TEXT NOT NULL, componente TEXT NOT NULL,
 tipo_actividad TEXT DEFAULT '', tipo_documento TEXT DEFAULT '', grupo_poblacional TEXT DEFAULT '',
 scope TEXT NOT NULL DEFAULT 'GLOBAL', fundacion_id INTEGER, activo INTEGER DEFAULT 1,
 creado_por INTEGER, creado_en TEXT NOT NULL, actualizado_en TEXT,
 UNIQUE(fundacion_id,codigo)
);
CREATE TABLE IF NOT EXISTS doc_opciones_respuesta (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 catalogo_id INTEGER NOT NULL, codigo TEXT NOT NULL, texto TEXT NOT NULL,
 orden INTEGER DEFAULT 0, activo INTEGER DEFAULT 1, requiere_justificacion INTEGER DEFAULT 0,
 contradice_json TEXT DEFAULT '[]', creado_por INTEGER, creado_en TEXT NOT NULL, actualizado_en TEXT,
 UNIQUE(catalogo_id,codigo), FOREIGN KEY(catalogo_id) REFERENCES doc_catalogos_respuesta(id)
);
CREATE TABLE IF NOT EXISTS doc_instancias (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 fundacion_id INTEGER NOT NULL, tipo_documento TEXT NOT NULL, componente TEXT NOT NULL,
 plantilla_version_id INTEGER, actividad_id INTEGER, uds TEXT, periodo TEXT,
 modo TEXT NOT NULL DEFAULT 'PLANEACION', estado TEXT NOT NULL DEFAULT 'BORRADOR',
 tema TEXT, datos_json TEXT DEFAULT '{}', planeacion_json TEXT DEFAULT '{}',
 hechos_json TEXT DEFAULT '{}', narrativa TEXT, version_actual INTEGER DEFAULT 1,
 creado_por INTEGER, actualizado_por INTEGER, creado_en TEXT NOT NULL, actualizado_en TEXT,
 FOREIGN KEY(plantilla_version_id) REFERENCES doc_plantilla_versiones(id)
);
CREATE TABLE IF NOT EXISTS doc_participantes (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 documento_id INTEGER NOT NULL, fundacion_id INTEGER NOT NULL,
 origen_tipo TEXT NOT NULL, origen_id TEXT NOT NULL, nombre_mostrado TEXT,
 creado_en TEXT NOT NULL, UNIQUE(documento_id,origen_tipo,origen_id),
 FOREIGN KEY(documento_id) REFERENCES doc_instancias(id)
);
CREATE TABLE IF NOT EXISTS doc_selecciones (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 documento_id INTEGER NOT NULL, fundacion_id INTEGER NOT NULL, categoria TEXT NOT NULL,
 opcion_id INTEGER, texto_personalizado TEXT, estado_especial TEXT, justificacion TEXT,
 confirmado_por INTEGER, confirmado_en TEXT NOT NULL,
 FOREIGN KEY(documento_id) REFERENCES doc_instancias(id)
);
CREATE TABLE IF NOT EXISTS doc_versiones (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 documento_id INTEGER NOT NULL, fundacion_id INTEGER NOT NULL, version INTEGER NOT NULL,
 estado TEXT NOT NULL, contenido_json TEXT NOT NULL, archivo_word TEXT, archivo_pdf TEXT,
 hash_sha256 TEXT, creado_por INTEGER, creado_en TEXT NOT NULL,
 UNIQUE(documento_id,version), FOREIGN KEY(documento_id) REFERENCES doc_instancias(id)
);
CREATE TABLE IF NOT EXISTS doc_revisiones (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 documento_id INTEGER NOT NULL, fundacion_id INTEGER NOT NULL, accion TEXT NOT NULL,
 observacion TEXT, usuario_id INTEGER, creado_en TEXT NOT NULL,
 FOREIGN KEY(documento_id) REFERENCES doc_instancias(id)
);
CREATE TABLE IF NOT EXISTS doc_evidencias (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 documento_id INTEGER NOT NULL, fundacion_id INTEGER NOT NULL, actividad_id INTEGER,
 requisito TEXT, nombre_original TEXT NOT NULL, nombre_seguro TEXT NOT NULL,
 ruta_privada TEXT NOT NULL, mime_type TEXT, tamano_bytes INTEGER, hash_sha256 TEXT NOT NULL,
 version INTEGER DEFAULT 1, estado TEXT DEFAULT 'CARGADA', usuario_id INTEGER, creado_en TEXT NOT NULL,
 FOREIGN KEY(documento_id) REFERENCES doc_instancias(id)
);
CREATE TABLE IF NOT EXISTS doc_auditoria (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 fundacion_id INTEGER NOT NULL, entidad TEXT NOT NULL, entidad_id INTEGER,
 accion TEXT NOT NULL, usuario_id INTEGER, detalle_json TEXT DEFAULT '{}', creado_en TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_doc_plantillas_scope ON doc_plantillas(fundacion_id,tipo_documento,estado);
CREATE INDEX IF NOT EXISTS idx_doc_versiones_estado ON doc_plantilla_versiones(fundacion_id,estado);
CREATE INDEX IF NOT EXISTS idx_doc_instancias_tenant ON doc_instancias(fundacion_id,estado,componente,periodo);
CREATE INDEX IF NOT EXISTS idx_doc_participantes_tenant ON doc_participantes(fundacion_id,origen_tipo,origen_id);
CREATE INDEX IF NOT EXISTS idx_doc_evidencias_tenant ON doc_evidencias(fundacion_id,documento_id);
CREATE INDEX IF NOT EXISTS idx_doc_auditoria_tenant ON doc_auditoria(fundacion_id,entidad,entidad_id,creado_en);
"""
