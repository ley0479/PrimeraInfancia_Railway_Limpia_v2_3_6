SCHEMA_VERSION=1
SCHEMA_SQL=r"""
CREATE TABLE IF NOT EXISTS af_presupuestos (
 id INTEGER PRIMARY KEY AUTOINCREMENT,fundacion_id INTEGER NOT NULL,contrato_id INTEGER,
 vigencia TEXT NOT NULL,codigo_rubro TEXT NOT NULL,nombre_rubro TEXT NOT NULL,
 valor_aprobado REAL NOT NULL DEFAULT 0,valor_modificado REAL NOT NULL DEFAULT 0,
 estado TEXT DEFAULT 'BORRADOR',observaciones TEXT,creado_por INTEGER,actualizado_por INTEGER,
 fecha_creacion TEXT NOT NULL,fecha_actualizacion TEXT NOT NULL,
 UNIQUE(fundacion_id,contrato_id,vigencia,codigo_rubro)
);
CREATE INDEX IF NOT EXISTS idx_af_presupuesto ON af_presupuestos(fundacion_id,vigencia,estado);
CREATE TABLE IF NOT EXISTS af_proveedores (
 id INTEGER PRIMARY KEY AUTOINCREMENT,fundacion_id INTEGER NOT NULL,tipo_documento TEXT,
 documento TEXT NOT NULL,razon_social TEXT NOT NULL,contacto TEXT,telefono TEXT,email TEXT,
 estado TEXT DEFAULT 'ACTIVO',creado_por INTEGER,fecha_creacion TEXT NOT NULL,fecha_actualizacion TEXT NOT NULL,
 UNIQUE(fundacion_id,documento)
);
CREATE TABLE IF NOT EXISTS af_compras (
 id INTEGER PRIMARY KEY AUTOINCREMENT,fundacion_id INTEGER NOT NULL,contrato_id INTEGER,
 presupuesto_id INTEGER,proveedor_id INTEGER,unidad TEXT,numero TEXT NOT NULL,objeto TEXT NOT NULL,
 fecha_solicitud TEXT NOT NULL,fecha_compra TEXT,valor REAL NOT NULL DEFAULT 0,
 estado TEXT DEFAULT 'SOLICITADA',responsable_id INTEGER,responsable_nombre TEXT,
 soporte_referencia TEXT,observaciones TEXT,creado_por INTEGER,actualizado_por INTEGER,
 fecha_creacion TEXT NOT NULL,fecha_actualizacion TEXT NOT NULL,
 UNIQUE(fundacion_id,numero),FOREIGN KEY(presupuesto_id) REFERENCES af_presupuestos(id),
 FOREIGN KEY(proveedor_id) REFERENCES af_proveedores(id)
);
CREATE INDEX IF NOT EXISTS idx_af_compras ON af_compras(fundacion_id,estado,fecha_solicitud);
CREATE TABLE IF NOT EXISTS af_movimientos (
 id INTEGER PRIMARY KEY AUTOINCREMENT,fundacion_id INTEGER NOT NULL,presupuesto_id INTEGER NOT NULL,
 compra_id INTEGER,tipo TEXT NOT NULL,fecha TEXT NOT NULL,valor REAL NOT NULL,
 concepto TEXT NOT NULL,referencia_tipo TEXT,referencia_id INTEGER,creado_por INTEGER,
 fecha_creacion TEXT NOT NULL,FOREIGN KEY(presupuesto_id) REFERENCES af_presupuestos(id),
 FOREIGN KEY(compra_id) REFERENCES af_compras(id)
);
CREATE INDEX IF NOT EXISTS idx_af_movimientos ON af_movimientos(fundacion_id,presupuesto_id,fecha,tipo);
CREATE TABLE IF NOT EXISTS af_legalizaciones (
 id INTEGER PRIMARY KEY AUTOINCREMENT,fundacion_id INTEGER NOT NULL,compra_id INTEGER NOT NULL,
 fecha_limite TEXT,fecha_presentacion TEXT,valor_legalizado REAL DEFAULT 0,
 estado TEXT DEFAULT 'PENDIENTE',soporte_referencia TEXT,observaciones TEXT,
 revisado_por INTEGER,fecha_revision TEXT,creado_por INTEGER,fecha_creacion TEXT NOT NULL,
 fecha_actualizacion TEXT NOT NULL,FOREIGN KEY(compra_id) REFERENCES af_compras(id)
);
CREATE INDEX IF NOT EXISTS idx_af_legalizaciones ON af_legalizaciones(fundacion_id,estado,fecha_limite);
CREATE TABLE IF NOT EXISTS af_auditoria (
 id INTEGER PRIMARY KEY AUTOINCREMENT,fundacion_id INTEGER NOT NULL,usuario_id INTEGER,usuario TEXT,
 accion TEXT NOT NULL,entidad TEXT NOT NULL,entidad_id INTEGER,detalle_json TEXT,fecha TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS af_schema_version(id INTEGER PRIMARY KEY CHECK(id=1),version INTEGER NOT NULL,fecha_actualizacion TEXT NOT NULL);
"""
