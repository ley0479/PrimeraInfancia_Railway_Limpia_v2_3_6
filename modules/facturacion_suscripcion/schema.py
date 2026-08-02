"""
FASE 4 - Sistema de planes, mensualidades, pagos, créditos y suscripción.
Crea tablas independientes sin reemplazar las fases anteriores.
"""

from __future__ import annotations

BILLING_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS planes_suscripcion (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL UNIQUE,
    descripcion TEXT,
    precio_mensual REAL DEFAULT 0,
    limite_usuarios INTEGER DEFAULT 0,
    limite_coordinadores INTEGER DEFAULT 0,
    limite_unidades INTEGER DEFAULT 0,
    creditos_incluidos INTEGER DEFAULT 0,
    modulos_habilitados TEXT,
    estado TEXT DEFAULT 'ACTIVO',
    personalizado INTEGER DEFAULT 0,
    fecha_creacion TEXT NOT NULL,
    fecha_actualizacion TEXT
);

CREATE TABLE IF NOT EXISTS suscripciones_fundacion (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fundacion_id INTEGER NOT NULL UNIQUE,
    plan_id INTEGER,
    estado TEXT DEFAULT 'ACTIVA',
    fecha_inicio TEXT NOT NULL,
    fecha_vencimiento TEXT NOT NULL,
    dias_gracia INTEGER DEFAULT 5,
    creditos_disponibles INTEGER DEFAULT 0,
    creditos_incluidos_periodo INTEGER DEFAULT 0,
    modulos_habilitados TEXT,
    renovacion_automatica INTEGER DEFAULT 0,
    observaciones TEXT,
    fecha_creacion TEXT NOT NULL,
    fecha_actualizacion TEXT,
    FOREIGN KEY(fundacion_id) REFERENCES fundaciones(id),
    FOREIGN KEY(plan_id) REFERENCES planes_suscripcion(id)
);

CREATE TABLE IF NOT EXISTS pagos_suscripcion (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fundacion_id INTEGER NOT NULL,
    suscripcion_id INTEGER,
    plan_id INTEGER,
    valor_pagado REAL NOT NULL,
    metodo_pago TEXT NOT NULL,
    fecha_pago TEXT NOT NULL,
    fecha_vencimiento TEXT NOT NULL,
    referencia_pago TEXT,
    comprobante_nombre TEXT,
    comprobante_ruta TEXT,
    usuario_registra_id INTEGER,
    observaciones TEXT,
    fecha_creacion TEXT NOT NULL,
    fecha_actualizacion TEXT,
    FOREIGN KEY(fundacion_id) REFERENCES fundaciones(id),
    FOREIGN KEY(suscripcion_id) REFERENCES suscripciones_fundacion(id),
    FOREIGN KEY(plan_id) REFERENCES planes_suscripcion(id)
);

CREATE TABLE IF NOT EXISTS paquetes_credito (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL UNIQUE,
    creditos INTEGER NOT NULL,
    precio REAL DEFAULT 0,
    estado TEXT DEFAULT 'ACTIVO',
    personalizado INTEGER DEFAULT 0,
    fecha_creacion TEXT NOT NULL,
    fecha_actualizacion TEXT
);

CREATE TABLE IF NOT EXISTS movimientos_credito (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fundacion_id INTEGER NOT NULL,
    suscripcion_id INTEGER,
    tipo TEXT NOT NULL,
    accion TEXT,
    creditos INTEGER NOT NULL,
    saldo_anterior INTEGER DEFAULT 0,
    saldo_nuevo INTEGER DEFAULT 0,
    referencia_tipo TEXT,
    referencia_id TEXT,
    descripcion TEXT,
    usuario_id INTEGER,
    fecha_movimiento TEXT NOT NULL,
    FOREIGN KEY(fundacion_id) REFERENCES fundaciones(id),
    FOREIGN KEY(suscripcion_id) REFERENCES suscripciones_fundacion(id)
);

CREATE TABLE IF NOT EXISTS modulos_plan (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_id INTEGER NOT NULL,
    modulo_codigo TEXT NOT NULL,
    habilitado INTEGER DEFAULT 1,
    fecha_creacion TEXT NOT NULL,
    UNIQUE(plan_id, modulo_codigo),
    FOREIGN KEY(plan_id) REFERENCES planes_suscripcion(id)
);

CREATE TABLE IF NOT EXISTS historial_suscripcion (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fundacion_id INTEGER NOT NULL,
    suscripcion_id INTEGER,
    accion TEXT NOT NULL,
    estado_anterior TEXT,
    estado_nuevo TEXT,
    plan_anterior_id INTEGER,
    plan_nuevo_id INTEGER,
    datos_anteriores TEXT,
    datos_nuevos TEXT,
    usuario_id INTEGER,
    fecha_accion TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS auditoria_facturacion (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id INTEGER,
    username TEXT,
    fundacion_id INTEGER,
    accion TEXT NOT NULL,
    tabla_afectada TEXT,
    registro_id INTEGER,
    datos_anteriores TEXT,
    datos_nuevos TEXT,
    ip TEXT,
    user_agent TEXT,
    fecha TEXT NOT NULL
);
"""

ALL_MODULES = [
    'dashboard',
    'administracion',
    'planeacion-pedagogica',
    'gestion-pedagogica',
    'gestion-coordinador',
    'cuentas-cobro',
    'relacion-mes',
    'paquete-mensual',
    'formatos',
    'nutricion',
    'salud-nutricion',
    'talento',
    'cumplimiento',
    'panel-comercial',
    'gerencia-general',
    'facturacion',
]

DEFAULT_PLANES = [
    {
        'nombre': 'BASICO',
        'descripcion': 'Plan inicial para operación pequeña.',
        'precio_mensual': 150000,
        'limite_usuarios': 8,
        'limite_coordinadores': 1,
        'limite_unidades': 6,
        'creditos_incluidos': 50,
        'modulos_habilitados': ['dashboard', 'formatos', 'talento', 'cuentas-cobro', 'relacion-mes', 'paquete-mensual', 'panel-comercial', 'gerencia-general', 'facturacion'],
    },
    {
        'nombre': 'PROFESIONAL',
        'descripcion': 'Plan operativo para fundaciones con varias unidades.',
        'precio_mensual': 300000,
        'limite_usuarios': 25,
        'limite_coordinadores': 4,
        'limite_unidades': 20,
        'creditos_incluidos': 150,
        'modulos_habilitados': ['dashboard', 'formatos', 'talento', 'cuentas-cobro', 'relacion-mes', 'paquete-mensual', 'gestion-pedagogica', 'gestion-coordinador', 'planeacion-pedagogica', 'cumplimiento', 'panel-comercial', 'gerencia-general', 'facturacion'],
    },
    {
        'nombre': 'PREMIUM',
        'descripcion': 'Plan completo con salud y nutrición, reportes y gestión pedagógica.',
        'precio_mensual': 600000,
        'limite_usuarios': 80,
        'limite_coordinadores': 12,
        'limite_unidades': 80,
        'creditos_incluidos': 500,
        'modulos_habilitados': ALL_MODULES,
    },
    {
        'nombre': 'PERSONALIZADO',
        'descripcion': 'Plan adaptable por contrato.',
        'precio_mensual': 0,
        'limite_usuarios': 0,
        'limite_coordinadores': 0,
        'limite_unidades': 0,
        'creditos_incluidos': 0,
        'modulos_habilitados': ALL_MODULES,
        'personalizado': 1,
    },
]

DEFAULT_PAQUETES = [
    ('50 créditos', 50, 50000, 0),
    ('100 créditos', 100, 90000, 0),
    ('300 créditos', 300, 240000, 0),
    ('500 créditos', 500, 350000, 0),
    ('Personalizado', 0, 0, 1),
]

METODOS_PAGO = ['Nequi', 'Bancolombia', 'Transferencia', 'Efectivo', 'PSE', 'Otro']
ESTADOS_SUSCRIPCION = ['ACTIVA', 'POR_VENCER', 'VENCIDA', 'SUSPENDIDA', 'CANCELADA']

CREDIT_COSTS = {
    'generar_informe_pdf': 1,
    'generar_acta': 1,
    'generar_formato_word': 1,
    'cruce_bases_datos': 3,
    'diagnostico_nutricional_masivo': 5,
    'paquete_mensual_completo': 10,
    'exportacion_masiva': 5,
}

CREDIT_PATH_RULES = [
    {'prefix': '/api/procesar', 'methods': ['POST'], 'accion': 'paquete_mensual_completo'},
    {'prefix': '/api/paquete-mensual/generar', 'methods': ['POST'], 'accion': 'paquete_mensual_completo'},
    {'prefix': '/api/salud-nutricion/importar', 'methods': ['POST'], 'accion': 'diagnostico_nutricional_masivo'},
    {'prefix': '/api/salud-nutricion/comparar', 'methods': ['POST'], 'accion': 'cruce_bases_datos'},
    {'prefix': '/api/salud-nutricion/reportes/dashboard', 'methods': ['GET'], 'accion': 'generar_informe_pdf'},
    {'prefix': '/api/planeacion-pedagogica/planeaciones/', 'contains': '/generar-documentos', 'methods': ['POST'], 'accion': 'generar_formato_word'},
    {'prefix': '/api/gestion-pedagogica/reportes', 'methods': ['GET', 'POST'], 'accion': 'generar_informe_pdf'},
    {'prefix': '/api/gestion-coordinador/reportes', 'methods': ['GET', 'POST'], 'accion': 'generar_informe_pdf'},
    {'prefix': '/api/cuentas-cobro/generar', 'methods': ['POST'], 'accion': 'generar_formato_word'},
    {'prefix': '/api/relacion-mes/generar', 'methods': ['GET', 'POST'], 'accion': 'exportacion_masiva'},
]

PATH_MODULE_MAP = [
    ('/api/planeacion-pedagogica', 'planeacion-pedagogica'),
    ('/api/gestion-pedagogica', 'gestion-pedagogica'),
    ('/api/gestion-coordinador', 'gestion-coordinador'),
    ('/api/salud-nutricion', 'salud-nutricion'),
    ('/api/nutricion', 'nutricion'),
    ('/api/cuentas-cobro', 'cuentas-cobro'),
    ('/api/relacion-mes', 'relacion-mes'),
    ('/api/paquete-mensual', 'paquete-mensual'),
    ('/api/talento', 'talento'),
    ('/api/cumplimiento', 'cumplimiento'),
    ('/api/formatos', 'formatos'),
    ('/api/plantillas', 'formatos'),
    ('/api/documentos-institucionales', 'cumplimiento'),
]
