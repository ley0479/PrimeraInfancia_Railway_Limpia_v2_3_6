SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS importaciones_universales (
 id INTEGER PRIMARY KEY AUTOINCREMENT, tenant_id INTEGER NOT NULL, usuario_id INTEGER,
 nombre_archivo TEXT NOT NULL, nombre_guardado TEXT NOT NULL, tipo_archivo TEXT NOT NULL,
 hash_sha256 TEXT NOT NULL, estado TEXT NOT NULL, porcentaje INTEGER NOT NULL DEFAULT 0,
 etapa_actual TEXT NOT NULL, tabla_seleccionada TEXT, fila_encabezado INTEGER,
 cantidad_filas INTEGER DEFAULT 0, cantidad_unidades INTEGER DEFAULT 0,
 cantidad_errores INTEGER DEFAULT 0, cantidad_advertencias INTEGER DEFAULT 0,
 fingerprint_estructura TEXT, perfil_mapeo_id INTEGER, resultado_json TEXT NOT NULL DEFAULT '{}',
 errores_json TEXT NOT NULL DEFAULT '[]', creado_en TEXT NOT NULL, actualizado_en TEXT NOT NULL,
 confirmado_en TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_importacion_hash_tenant ON importaciones_universales(tenant_id, hash_sha256);
CREATE INDEX IF NOT EXISTS idx_importacion_estado_tenant ON importaciones_universales(tenant_id, estado, actualizado_en);

CREATE TABLE IF NOT EXISTS perfiles_mapeo_universal (
 id INTEGER PRIMARY KEY AUTOINCREMENT, tenant_id INTEGER NOT NULL, nombre TEXT NOT NULL,
 fingerprint_estructura TEXT NOT NULL, version INTEGER NOT NULL DEFAULT 1, estado TEXT NOT NULL DEFAULT 'BORRADOR',
 mapeo_json TEXT NOT NULL, catalogo_version TEXT NOT NULL, usuario_id INTEGER,
 creado_en TEXT NOT NULL, publicado_en TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_perfil_version_tenant ON perfiles_mapeo_universal(tenant_id, fingerprint_estructura, version);

CREATE TABLE IF NOT EXISTS importaciones_filas_staging (
 id INTEGER PRIMARY KEY AUTOINCREMENT, importacion_id INTEGER NOT NULL, tenant_id INTEGER NOT NULL,
 numero_fila INTEGER NOT NULL, hash_fila TEXT NOT NULL, original_json TEXT NOT NULL,
 normalizado_json TEXT NOT NULL, errores_json TEXT NOT NULL DEFAULT '[]', advertencias_json TEXT NOT NULL DEFAULT '[]',
 FOREIGN KEY(importacion_id) REFERENCES importaciones_universales(id) ON DELETE CASCADE
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_staging_fila_importacion ON importaciones_filas_staging(importacion_id, numero_fila);

CREATE TABLE IF NOT EXISTS auditoria_importaciones_universal (
 id INTEGER PRIMARY KEY AUTOINCREMENT, importacion_id INTEGER NOT NULL, tenant_id INTEGER NOT NULL,
 usuario_id INTEGER, evento TEXT NOT NULL, detalle_json TEXT NOT NULL DEFAULT '{}', creado_en TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS unidades_identificadores_origen (
 id INTEGER PRIMARY KEY AUTOINCREMENT, tenant_id INTEGER NOT NULL, unidad_id INTEGER,
 perfil_origen_id INTEGER NOT NULL, codigo_externo TEXT, nombre_externo TEXT,
 nombre_normalizado TEXT, municipio_externo TEXT, vigente INTEGER NOT NULL DEFAULT 1, creado_en TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_unidad_origen_codigo ON unidades_identificadores_origen(tenant_id, perfil_origen_id, codigo_externo) WHERE codigo_externo IS NOT NULL AND codigo_externo <> '';
"""
