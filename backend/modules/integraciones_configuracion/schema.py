SCHEMA_VERSION=1
SCHEMA_SQL=r"""
CREATE TABLE IF NOT EXISTS ic_parametros (
 id INTEGER PRIMARY KEY AUTOINCREMENT,fundacion_id INTEGER NOT NULL,modulo TEXT NOT NULL,
 clave TEXT NOT NULL,valor TEXT,tipo TEXT DEFAULT 'TEXTO',descripcion TEXT,
 estado TEXT DEFAULT 'ACTIVO',actualizado_por INTEGER,fecha_creacion TEXT NOT NULL,
 fecha_actualizacion TEXT NOT NULL,UNIQUE(fundacion_id,modulo,clave)
);
CREATE INDEX IF NOT EXISTS idx_ic_parametros ON ic_parametros(fundacion_id,modulo,estado);
CREATE TABLE IF NOT EXISTS ic_integraciones (
 id INTEGER PRIMARY KEY AUTOINCREMENT,fundacion_id INTEGER NOT NULL,codigo TEXT NOT NULL,
 nombre TEXT NOT NULL,tipo TEXT NOT NULL,base_url TEXT,credential_ref TEXT,
 estado TEXT DEFAULT 'BORRADOR',alcance TEXT,timeout_segundos INTEGER DEFAULT 10,
 ultimo_estado TEXT DEFAULT 'NO_PROBADA',ultima_prueba TEXT,observaciones TEXT,
 creado_por INTEGER,actualizado_por INTEGER,fecha_creacion TEXT NOT NULL,
 fecha_actualizacion TEXT NOT NULL,UNIQUE(fundacion_id,codigo)
);
CREATE INDEX IF NOT EXISTS idx_ic_integraciones ON ic_integraciones(fundacion_id,estado,tipo);
CREATE TABLE IF NOT EXISTS ic_auditoria (
 id INTEGER PRIMARY KEY AUTOINCREMENT,fundacion_id INTEGER NOT NULL,usuario_id INTEGER,
 usuario TEXT,accion TEXT NOT NULL,entidad TEXT NOT NULL,entidad_id INTEGER,
 detalle_json TEXT,fecha TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS ic_schema_version(id INTEGER PRIMARY KEY CHECK(id=1),version INTEGER NOT NULL,fecha_actualizacion TEXT NOT NULL);
"""
