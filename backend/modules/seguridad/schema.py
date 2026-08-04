"""Esquema de seguridad, sesiones, recuperación y aislamiento por fundación."""

ROLES_SISTEMA = [
    'SUPERADMIN',
    'GERENTE',
    'COORDINADOR',
    'DOCENTE',
    'NUTRICIONISTA',
    'PSICOSOCIAL',
    'AUXILIAR_ADMINISTRATIVO',
]

PERMISOS_BASE = {
    'SUPERADMIN': ['*'],
    'GERENTE': [
        'dashboard.ver', 'fundacion.ver', 'usuarios.crear', 'usuarios.ver', 'talento.ver',
        'talento.crear', 'reportes.ver', 'cumplimiento.ver', 'formatos.ver', 'gestion.ver',
        'salud.ver', 'documentos.ver', 'cuentas.ver', 'planeacion.ver', 'planeacion.cargar',
        'planeacion.aprobar', 'planeacion.reportes', 'reportes.gerenciales', 'panel_comercial.ver',
        'facturacion.ver'
    ],
    'COORDINADOR': [
        'dashboard.ver', 'gestion.ver', 'planeacion.cargar', 'evidencias.revisar',
        'calendario.ver', 'informes.generar', 'documentos.ver', 'planeacion.ver',
        'planeacion.reportes', 'reportes.gerenciales', 'facturacion.ver'
    ],
    'DOCENTE': [
        'dashboard.ver', 'unidad.ver', 'evidencias.cargar', 'actividades.ver',
        'formatos.descargar', 'planeacion.ver', 'planeacion.evidencias'
    ],
    'NUTRICIONISTA': ['salud.ver', 'salud.cargar', 'salud.reportes', 'dashboard.ver'],
    'PSICOSOCIAL': ['psicosocial.ver', 'gestion.ver', 'documentos.ver', 'dashboard.ver', 'planeacion.ver'],
    'AUXILIAR_ADMINISTRATIVO': [
        'dashboard.ver', 'documentos.cargar', 'cuentas.ver', 'cuentas.generar',
        'reportes.ver', 'formatos.ver', 'relacion.ver', 'facturacion.ver',
        'planeacion.ver', 'planeacion.cargar', 'reportes.gerenciales'
    ],
}

SEGURIDAD_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS fundaciones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL UNIQUE,
    nit TEXT,
    representante TEXT,
    email TEXT,
    telefono TEXT,
    direccion TEXT,
    municipio TEXT,
    departamento TEXT,
    estado TEXT DEFAULT 'ACTIVA',
    plan TEXT DEFAULT 'PRUEBA',
    fecha_inicio TEXT,
    fecha_vencimiento TEXT,
    observaciones TEXT,
    fecha_creacion TEXT NOT NULL,
    fecha_actualizacion TEXT,
    eliminado_en TEXT,
    eliminado_por INTEGER,
    motivo_eliminacion TEXT
);

CREATE TABLE IF NOT EXISTS roles_sistema (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL UNIQUE,
    descripcion TEXT,
    activo INTEGER DEFAULT 1,
    fecha_creacion TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS permisos_sistema (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo TEXT NOT NULL UNIQUE,
    descripcion TEXT,
    modulo TEXT,
    fecha_creacion TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS rol_permiso (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rol TEXT NOT NULL,
    permiso_codigo TEXT NOT NULL,
    fecha_creacion TEXT NOT NULL,
    UNIQUE(rol, permiso_codigo)
);

CREATE TABLE IF NOT EXISTS sesiones_usuario (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id INTEGER NOT NULL,
    fundacion_id INTEGER,
    token_hash TEXT NOT NULL UNIQUE,
    ip TEXT,
    user_agent TEXT,
    activa INTEGER DEFAULT 1,
    fecha_creacion TEXT NOT NULL,
    fecha_expiracion TEXT NOT NULL,
    fecha_cierre TEXT,
    FOREIGN KEY(usuario_id) REFERENCES usuarios_app(id),
    FOREIGN KEY(fundacion_id) REFERENCES fundaciones(id)
);
CREATE INDEX IF NOT EXISTS idx_sesiones_usuario_activa ON sesiones_usuario(usuario_id, activa);
CREATE INDEX IF NOT EXISTS idx_sesiones_token_hash ON sesiones_usuario(token_hash);

CREATE TABLE IF NOT EXISTS recuperacion_password (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id INTEGER NOT NULL,
    fundacion_id INTEGER,
    token_hash TEXT NOT NULL UNIQUE,
    metodo TEXT DEFAULT 'EMAIL_LINK',
    solicitado_por INTEGER,
    ip TEXT,
    usado INTEGER DEFAULT 0,
    fecha_creacion TEXT NOT NULL,
    fecha_expiracion TEXT NOT NULL,
    FOREIGN KEY(usuario_id) REFERENCES usuarios_app(id),
    FOREIGN KEY(fundacion_id) REFERENCES fundaciones(id)
);
CREATE INDEX IF NOT EXISTS idx_recuperacion_usuario ON recuperacion_password(usuario_id, usado);

CREATE TABLE IF NOT EXISTS auth_intentos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    clave_hash TEXT NOT NULL UNIQUE,
    alcance TEXT NOT NULL,
    intentos INTEGER NOT NULL DEFAULT 0,
    ventana_inicio TEXT NOT NULL,
    bloqueado_hasta TEXT,
    fecha_actualizacion TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_auth_intentos_bloqueo ON auth_intentos(bloqueado_hasta);

CREATE TABLE IF NOT EXISTS auditoria_seguridad (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id INTEGER,
    username TEXT,
    fundacion_id INTEGER,
    accion TEXT NOT NULL,
    modulo TEXT DEFAULT 'SEGURIDAD',
    tabla_afectada TEXT,
    registro_id INTEGER,
    datos_anteriores TEXT,
    datos_nuevos TEXT,
    ip TEXT,
    user_agent TEXT,
    fecha TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_auditoria_fecha ON auditoria_seguridad(fecha);
"""

MULTITENANT_COLUMNS = {
    'fundacion_id': 'INTEGER',
    'usuario_creador_id': 'INTEGER',
    'fecha_creacion': 'TEXT',
    'fecha_actualizacion': 'TEXT'
}

MULTITENANT_TABLES = [
    'beneficiarios', 'gestantes', 'docentes', 'coordinadores', 'unidades', 'peso_talla',
    'movimientos', 'plantillas', 'alertas', 'auditoria', 'cargas_archivo',
    'documentos_institucionales', 'entregables_operacion', 'informes_pedagogicos',
    'evidencias', 'copias_seguridad', 'usuarios', 'cuentas_cobro_plantillas',
    'cuentas_cobro_generadas', 'relacion_mes_generada'
]
