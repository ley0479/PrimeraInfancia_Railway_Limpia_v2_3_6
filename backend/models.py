"""
Modelos de datos para SinergiaInfancia - Primera Infancia ICBF
"""
from datetime import datetime
from functools import wraps
import json
import os

from services.uds_catalog import canonical_units, normalization_map

# Directorio de base de datos
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_PATH = os.path.join(BASE_DIR, 'database.sqlite3')


class Rol:
    """Roles del sistema"""
    SUPERADMIN = 'SUPERADMIN'
    GERENTE = 'GERENTE'
    COORDINADOR = 'COORDINADOR'
    DOCENTE = 'DOCENTE'
    NUTRICIONISTA = 'NUTRICIONISTA'
    PSICOSOCIAL = 'PSICOSOCIAL'
    AUXILIAR_ADMINISTRATIVO = 'AUXILIAR_ADMINISTRATIVO'

    # Compatibilidad con versiones anteriores.
    ADMINISTRADOR = SUPERADMIN
    CONSULTA = DOCENTE
    
    ROLES_VALIDOS = [
        SUPERADMIN, GERENTE, COORDINADOR, DOCENTE, NUTRICIONISTA,
        PSICOSOCIAL, AUXILIAR_ADMINISTRATIVO
    ]


class EstadoUsuario:
    """Estados posibles de un usuario"""
    ACTIVO = 'ACTIVO'
    RETIRADO = 'RETIRADO'
    FALLECIDO = 'FALLECIDO'
    TRASLADADO = 'TRASLADADO'
    
    ESTADOS_VALIDOS = [ACTIVO, RETIRADO, FALLECIDO, TRASLADADO]


class TipoMovimiento:
    """Tipos de movimiento de usuarios"""
    INGRESO = 'INGRESO'
    RETIRO = 'RETIRO'
    TRASLADO = 'TRASLADO'
    FALLECIMIENTO = 'FALLECIMIENTO'
    TRANSICION_LACTANTE = 'TRANSICION_LACTANTE'
    TRANSICION_EGRESO = 'TRANSICION_EGRESO'
    CAMBIO_DOCENTE = 'CAMBIO_DOCENTE'
    CAMBIO_UNIDAD = 'CAMBIO_UNIDAD'


class EstadoNutricion:
    """Estados nutricionales"""
    ADECUADO = 'ADECUADO'
    RIESGO = 'RIESGO'
    DESNUTRICION = 'DESNUTRICION'
    SOBREPESO = 'SOBREPESO'
    PENDIENTE = 'PENDIENTE'


class AlertaNivel:
    """Niveles de alerta"""
    VERDE = 'VERDE'
    AMARILLO = 'AMARILLO'
    ROJO = 'ROJO'
    CRITICA = 'CRITICA'


class TipoGestante:
    """Tipos de gestante"""
    EMBARAZADA = 'EMBARAZADA'
    LACTANTE = 'LACTANTE'


class EvidenciaCategoria:
    """Categorías de evidencias pedagógicas"""
    FOTOGRAFIA = 'FOTOGRAFIA'
    ACTA = 'ACTA'
    EVALUACION = 'EVALUACION'
    TALLER = 'TALLER'
    OTRA = 'OTRA'


class AlertaConfiguracion:
    """Configuración de umbrales de alertas"""
    
    # Edad (meses)
    EDAD_VERDE_MAX = 67
    EDAD_AMARILLO_MAX = 70
    EDAD_ROJO_MAX = 999  # Mayor a 70 meses
    
    # Cobertura mínima por unidad
    COBERTURA_MINIMA = 20
    
    # Control trimestral (días)
    DIAS_CONTROL_NUTRICION = 90
    
    # Alertas de gestantes (semanas)
    SEMANAS_ALERTA_PARTO = 2
    
    # Archivo carga máxima (MB)
    TAMAÑO_MAX_MB = 50


class ConfiguracionSistema:
    """Configuración general del sistema"""
    
    UNIDADES = canonical_units()

    NORMALIZACION_UNIDADES = normalization_map()
    
    FORMATOS_ICBF = [
        'ASISTENCIA',
        'BIENESTARINA',
        'RPP',  # Registro Procedencia Procedimiento
        'RAN',  # Registro Asistencia Nutrición
        'NUTRICION',
        'TALENTO_HUMANO',
        'INFORME_PEDAGOGICO'
    ]


class Schema:
    """Esquema de la base de datos"""
    
    @staticmethod
    def get_schema_sql():
        """Retorna SQL para crear todas las tablas"""
        return """
-- Tabla de usuarios de la aplicación (login)
CREATE TABLE IF NOT EXISTS usuarios_app (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    rol TEXT NOT NULL DEFAULT 'CONSULTA',
    unidades TEXT,  -- JSON con unidades asignadas
    activo INTEGER DEFAULT 1,
    fecha_creacion TEXT NOT NULL,
    fecha_ultima_conexion TEXT
);

-- Tabla de beneficiarios (niños, niñas)
CREATE TABLE IF NOT EXISTS beneficiarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    documento TEXT NOT NULL,
    nombres TEXT NOT NULL,
    apellidos TEXT NOT NULL,
    fecha_nacimiento TEXT NOT NULL,
    sexo TEXT,
    unidad TEXT NOT NULL,
    docente_id INTEGER,
    estado TEXT DEFAULT 'ACTIVO',
    tipo_beneficiario TEXT DEFAULT 'NINO',
    fecha_ingreso TEXT NOT NULL,
    fecha_retiro TEXT,
    motivo_retiro TEXT,
    indice_registrado INTEGER DEFAULT 0,
    fecha_carga TEXT NOT NULL,
    FOREIGN KEY (docente_id) REFERENCES docentes(id),
    UNIQUE(documento, unidad)
);

-- Tabla de gestantes
CREATE TABLE IF NOT EXISTS gestantes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    documento TEXT UNIQUE NOT NULL,
    nombres TEXT NOT NULL,
    apellidos TEXT NOT NULL,
    fecha_nacimiento TEXT,
    edad INTEGER,
    unidad TEXT NOT NULL,
    coordinador_id INTEGER,
    tipo_gestante TEXT DEFAULT 'EMBARAZADA',
    semanas_gestacion INTEGER,
    fecha_probable_parto TEXT,
    fecha_nacimiento_bebe TEXT,
    estado TEXT DEFAULT 'ACTIVO',
    fecha_carga TEXT NOT NULL,
    FOREIGN KEY (coordinador_id) REFERENCES coordinadores(id)
);

-- Tabla de docentes
CREATE TABLE IF NOT EXISTS docentes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    documento TEXT UNIQUE NOT NULL,
    nombres TEXT NOT NULL,
    apellidos TEXT NOT NULL,
    cargo TEXT,
    unidad TEXT NOT NULL,
    email TEXT,
    telefono TEXT,
    fecha_vinculacion TEXT,
    activo INTEGER DEFAULT 1,
    fecha_carga TEXT NOT NULL
);

-- Tabla de coordinadores
CREATE TABLE IF NOT EXISTS coordinadores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    documento TEXT UNIQUE NOT NULL,
    nombres TEXT NOT NULL,
    apellidos TEXT NOT NULL,
    cargo TEXT,
    unidades TEXT,  -- JSON con unidades
    email TEXT,
    telefono TEXT,
    fecha_vinculacion TEXT,
    activo INTEGER DEFAULT 1,
    fecha_carga TEXT NOT NULL
);

-- Tabla de unidades
CREATE TABLE IF NOT EXISTS unidades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT UNIQUE NOT NULL,
    direccion TEXT,
    telefono TEXT,
    coordinador_id INTEGER,
    total_usuarios INTEGER DEFAULT 0,
    total_gestantes INTEGER DEFAULT 0,
    fecha_actualizacion TEXT NOT NULL,
    FOREIGN KEY (coordinador_id) REFERENCES coordinadores(id)
);

-- Tabla de peso y talla
CREATE TABLE IF NOT EXISTS peso_talla (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    beneficiario_id INTEGER NOT NULL,
    peso REAL,
    talla REAL,
    fecha_medicion TEXT NOT NULL,
    responsable TEXT,
    estado_nutricional TEXT DEFAULT 'PENDIENTE',
    fecha_proximo_control TEXT,
    fecha_carga TEXT NOT NULL,
    FOREIGN KEY (beneficiario_id) REFERENCES beneficiarios(id)
);

-- Tabla de movimientos
CREATE TABLE IF NOT EXISTS movimientos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    beneficiario_id INTEGER NOT NULL,
    tipo TEXT NOT NULL,
    unidad_origen TEXT,
    unidad_destino TEXT,
    fecha_movimiento TEXT NOT NULL,
    razon TEXT,
    usuario_registra TEXT,
    fecha_registro TEXT NOT NULL,
    FOREIGN KEY (beneficiario_id) REFERENCES beneficiarios(id)
);

-- Tabla de plantillas ICBF
CREATE TABLE IF NOT EXISTS plantillas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL,
    tipo TEXT NOT NULL,
    ruta_archivo TEXT NOT NULL,
    ruta_backup TEXT,
    configuracion_campos TEXT,  -- JSON con mapeo de campos
    versión TEXT,
    activa INTEGER DEFAULT 1,
    fecha_carga TEXT NOT NULL,
    fecha_ultima_actualizacion TEXT
);

-- Tabla de informes pedagógicos
CREATE TABLE IF NOT EXISTS informes_pedagogicos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    docente_id INTEGER NOT NULL,
    unidad TEXT NOT NULL,
    año INTEGER NOT NULL,
    mes INTEGER NOT NULL,
    tema_mes TEXT,
    objetivos TEXT,
    actividades TEXT,
    resultados TEXT,
    observaciones TEXT,
    participacion_familiar TEXT,
    logros TEXT,
    dificultades TEXT,
    recomendaciones TEXT,
    fecha_creacion TEXT NOT NULL,
    fecha_ultima_edicion TEXT,
    FOREIGN KEY (docente_id) REFERENCES docentes(id)
);

-- Tabla de evidencias pedagógicas
CREATE TABLE IF NOT EXISTS evidencias (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    informe_id INTEGER NOT NULL,
    año INTEGER NOT NULL,
    mes INTEGER NOT NULL,
    docente_id INTEGER NOT NULL,
    unidad TEXT NOT NULL,
    categoria TEXT,
    descripcion TEXT,
    ruta_archivo TEXT NOT NULL,
    tipo_archivo TEXT,
    fecha_carga TEXT NOT NULL,
    FOREIGN KEY (informe_id) REFERENCES informes_pedagogicos(id),
    FOREIGN KEY (docente_id) REFERENCES docentes(id)
);

-- Tabla de alertas
CREATE TABLE IF NOT EXISTS alertas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    beneficiario_id INTEGER,
    tipo_alerta TEXT NOT NULL,
    nivel TEXT NOT NULL DEFAULT 'AMARILLO',
    descripcion TEXT NOT NULL,
    detalles TEXT,
    resuelta INTEGER DEFAULT 0,
    fecha_generacion TEXT NOT NULL,
    fecha_resolucion TEXT,
    usuario_resuelve TEXT,
    FOREIGN KEY (beneficiario_id) REFERENCES beneficiarios(id)
);

-- Tabla de auditoría
CREATE TABLE IF NOT EXISTS auditoria (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario TEXT NOT NULL,
    accion TEXT NOT NULL,
    tabla TEXT,
    registro_id INTEGER,
    datos_anteriores TEXT,
    datos_nuevos TEXT,
    archivo_cargado TEXT,
    formato_generado TEXT,
    fecha_accion TEXT NOT NULL,
    direccion_ip TEXT
);

-- Tabla de cargas/importaciones
CREATE TABLE IF NOT EXISTS cargas_archivo (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    archivo_nombre TEXT NOT NULL,
    archivo_ruta TEXT NOT NULL,
    tipo_carga TEXT NOT NULL,
    total_registros INTEGER,
    registros_procesados INTEGER,
    registros_error INTEGER,
    cambios_detectados TEXT,  -- JSON
    nuevos_ingresos INTEGER DEFAULT 0,
    retiros INTEGER DEFAULT 0,
    traslados INTEGER DEFAULT 0,
    cambios_docente INTEGER DEFAULT 0,
    usuario_carga TEXT,
    fecha_carga TEXT NOT NULL
);

-- Tabla de configuración del sistema
CREATE TABLE IF NOT EXISTS configuracion (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    clave TEXT UNIQUE NOT NULL,
    valor TEXT,
    tipo TEXT,
    fecha_actualizacion TEXT NOT NULL
);

-- Tabla de copias de seguridad
CREATE TABLE IF NOT EXISTS copias_seguridad (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tipo TEXT NOT NULL,
    ruta_archivo TEXT NOT NULL,
    tamaño INTEGER,
    fecha_creacion TEXT NOT NULL,
    fecha_siguiente TEXT
);

-- Índices para mejorar rendimiento
"""
