
from __future__ import annotations

MOTOR_PLANTILLAS_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS mp_plantillas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL,
    tipo TEXT NOT NULL,
    nombre_original TEXT,
    nombre_guardado TEXT,
    ruta_archivo TEXT NOT NULL,
    version TEXT DEFAULT '1.0',
    estado TEXT DEFAULT 'ACTIVA',
    hoja_principal TEXT,
    total_hojas INTEGER DEFAULT 0,
    metadata_json TEXT,
    fundacion_id INTEGER DEFAULT 1,
    usuario_creador_id INTEGER,
    fecha_creacion TEXT NOT NULL,
    fecha_actualizacion TEXT
);

CREATE TABLE IF NOT EXISTS mp_mapeos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plantilla_id INTEGER NOT NULL,
    nombre TEXT DEFAULT 'Mapeo principal',
    version TEXT DEFAULT '1.0',
    mapeo_json TEXT NOT NULL,
    validacion_json TEXT,
    activo INTEGER DEFAULT 1,
    usuario_creador_id INTEGER,
    fecha_creacion TEXT NOT NULL,
    fecha_actualizacion TEXT,
    FOREIGN KEY (plantilla_id) REFERENCES mp_plantillas(id)
);

CREATE TABLE IF NOT EXISTS mp_pruebas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plantilla_id INTEGER NOT NULL,
    mapeo_id INTEGER,
    unidad TEXT,
    estado TEXT DEFAULT 'PENDIENTE',
    total_usuarios INTEGER DEFAULT 0,
    errores_json TEXT,
    archivo_generado TEXT,
    usuario_id INTEGER,
    fecha_creacion TEXT NOT NULL,
    FOREIGN KEY (plantilla_id) REFERENCES mp_plantillas(id),
    FOREIGN KEY (mapeo_id) REFERENCES mp_mapeos(id)
);

CREATE TABLE IF NOT EXISTS mp_auditoria (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    accion TEXT NOT NULL,
    plantilla_id INTEGER,
    mapeo_id INTEGER,
    usuario_id INTEGER,
    fundacion_id INTEGER DEFAULT 1,
    detalle_json TEXT,
    fecha TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_mp_plantillas_fundacion ON mp_plantillas(fundacion_id);
CREATE INDEX IF NOT EXISTS idx_mp_mapeos_plantilla ON mp_mapeos(plantilla_id);
CREATE INDEX IF NOT EXISTS idx_mp_pruebas_plantilla ON mp_pruebas(plantilla_id);


-- ALPHA52: versionamiento oficial compatible con motor existente.
CREATE TABLE IF NOT EXISTS plantillas_oficiales (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tipo_formato TEXT NOT NULL,
    codigo TEXT,
    nombre TEXT NOT NULL,
    descripcion TEXT,
    activo INTEGER DEFAULT 1,
    fundacion_id INTEGER DEFAULT 1,
    usuario_creador_id INTEGER,
    created_at TEXT,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS plantillas_oficiales_versiones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plantilla_oficial_id INTEGER,
    mp_plantilla_id INTEGER,
    tipo_formato TEXT NOT NULL,
    codigo TEXT,
    nombre TEXT,
    version TEXT NOT NULL,
    fecha_vigencia TEXT,
    fecha_vigencia_fin TEXT,
    estado TEXT DEFAULT 'borrador',
    estado_publicacion TEXT,
    archivo_path TEXT NOT NULL,
    hash_sha256 TEXT,
    manual_path TEXT,
    reglas_json TEXT,
    archivo_original TEXT,
    observaciones TEXT,
    mapeo_json TEXT,
    productos_json TEXT,
    usuario_carga INTEGER,
    fundacion_id INTEGER DEFAULT 1,
    created_at TEXT,
    updated_at TEXT,
    FOREIGN KEY (plantilla_oficial_id) REFERENCES plantillas_oficiales(id),
    FOREIGN KEY (mp_plantilla_id) REFERENCES mp_plantillas(id)
);

CREATE TABLE IF NOT EXISTS plantillas_oficiales_mapeos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    version_id INTEGER NOT NULL,
    campo TEXT NOT NULL,
    hoja TEXT,
    columna TEXT,
    col_index INTEGER,
    fila_inicio INTEGER,
    fila_fin INTEGER,
    obligatorio INTEGER DEFAULT 0,
    config_json TEXT,
    fundacion_id INTEGER DEFAULT 1,
    created_at TEXT,
    updated_at TEXT,
    FOREIGN KEY (version_id) REFERENCES plantillas_oficiales_versiones(id)
);

CREATE TABLE IF NOT EXISTS plantillas_oficiales_productos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    version_id INTEGER NOT NULL,
    nombre_producto TEXT NOT NULL,
    columna TEXT,
    col_index INTEGER,
    unidad_medida TEXT,
    cantidad TEXT,
    grupo_etario_aplica TEXT,
    orden INTEGER DEFAULT 0,
    activo INTEGER DEFAULT 1,
    fundacion_id INTEGER DEFAULT 1,
    created_at TEXT,
    updated_at TEXT,
    FOREIGN KEY (version_id) REFERENCES plantillas_oficiales_versiones(id)
);

CREATE TABLE IF NOT EXISTS plantillas_oficiales_pruebas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    version_id INTEGER NOT NULL,
    unidad TEXT,
    estado TEXT DEFAULT 'pendiente',
    archivo_generado TEXT,
    total_usuarios INTEGER DEFAULT 0,
    resultado_json TEXT,
    created_at TEXT,
    usuario_id INTEGER,
    fundacion_id INTEGER DEFAULT 1,
    FOREIGN KEY (version_id) REFERENCES plantillas_oficiales_versiones(id)
);

CREATE TABLE IF NOT EXISTS plantillas_oficiales_auditoria (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    accion TEXT NOT NULL,
    tipo_formato TEXT,
    version_id INTEGER,
    mp_plantilla_id INTEGER,
    usuario_id INTEGER,
    fundacion_id INTEGER DEFAULT 1,
    detalle_json TEXT,
    created_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_plantillas_oficiales_fundacion ON plantillas_oficiales(fundacion_id);
CREATE INDEX IF NOT EXISTS idx_plantillas_versiones_fundacion ON plantillas_oficiales_versiones(fundacion_id);
CREATE INDEX IF NOT EXISTS idx_plantillas_mapeos_fundacion ON plantillas_oficiales_mapeos(fundacion_id);
CREATE INDEX IF NOT EXISTS idx_plantillas_productos_fundacion ON plantillas_oficiales_productos(fundacion_id);
CREATE INDEX IF NOT EXISTS idx_plantillas_pruebas_fundacion ON plantillas_oficiales_pruebas(fundacion_id);
CREATE INDEX IF NOT EXISTS idx_plantillas_auditoria_fundacion ON plantillas_oficiales_auditoria(fundacion_id);
CREATE INDEX IF NOT EXISTS idx_plantillas_oficiales_tipo ON plantillas_oficiales(tipo_formato);
CREATE INDEX IF NOT EXISTS idx_plantillas_versiones_tipo_estado ON plantillas_oficiales_versiones(tipo_formato, estado);
CREATE INDEX IF NOT EXISTS idx_plantillas_versiones_mp ON plantillas_oficiales_versiones(mp_plantilla_id);
CREATE INDEX IF NOT EXISTS idx_plantillas_mapeos_version ON plantillas_oficiales_mapeos(version_id);
CREATE INDEX IF NOT EXISTS idx_plantillas_productos_version ON plantillas_oficiales_productos(version_id);
CREATE INDEX IF NOT EXISTS idx_plantillas_pruebas_version ON plantillas_oficiales_pruebas(version_id);

"""

CAMPOS_CANONICOS = [
    {
        "id": "consecutivo",
        "label": "Consecutivo / numeración",
        "categoria": "Identificación",
        "descripcion": "Solo números consecutivos. Nunca documento o NUI."
    },
    {
        "id": "tipo_documento",
        "label": "Tipo de documento del beneficiario",
        "categoria": "Beneficiario",
        "descripcion": "RC, TI, CC, CE, PA, PEP o PPT."
    },
    {
        "id": "documento_beneficiario",
        "label": "Documento / NUI del beneficiario",
        "categoria": "Beneficiario",
        "descripcion": "Número de documento del niño, NUI o NUIP."
    },
    {
        "id": "nombre_completo",
        "label": "Nombre completo del beneficiario",
        "categoria": "Beneficiario",
        "descripcion": "Nombres y apellidos completos."
    },
    {
        "id": "primer_nombre",
        "label": "Primer nombre",
        "categoria": "Beneficiario",
        "descripcion": "Primer nombre del niño."
    },
    {
        "id": "segundo_nombre",
        "label": "Segundo nombre",
        "categoria": "Beneficiario",
        "descripcion": "Segundo nombre del niño."
    },
    {
        "id": "primer_apellido",
        "label": "Primer apellido",
        "categoria": "Beneficiario",
        "descripcion": "Primer apellido del niño."
    },
    {
        "id": "segundo_apellido",
        "label": "Segundo apellido",
        "categoria": "Beneficiario",
        "descripcion": "Segundo apellido del niño."
    },
    {
        "id": "edad_anios",
        "label": "Edad - años",
        "categoria": "Beneficiario",
        "descripcion": "Solo el número de años."
    },
    {
        "id": "edad_meses",
        "label": "Edad - meses",
        "categoria": "Beneficiario",
        "descripcion": "Solo el número de meses restantes."
    },
    {
        "id": "acudiente_nombre_cedula",
        "label": "Nombre completo y cédula del acudiente",
        "categoria": "Acudiente",
        "descripcion": "Nombre completo + tipo documento + documento."
    },
    {
        "id": "nombre_acudiente",
        "label": "Nombre completo del acudiente",
        "categoria": "Acudiente",
        "descripcion": "Nombre completo del acudiente o responsable."
    },
    {
        "id": "documento_acudiente",
        "label": "Documento del acudiente",
        "categoria": "Acudiente",
        "descripcion": "Número de documento del acudiente."
    },
    {
        "id": "tipo_documento_acudiente",
        "label": "Tipo documento acudiente",
        "categoria": "Acudiente",
        "descripcion": "CC, CE, TI u otro tipo abreviado."
    },
    {
        "id": "parentesco",
        "label": "Parentesco",
        "categoria": "Acudiente",
        "descripcion": "Madre, padre, abuela, acudiente, tutor, etc."
    },
    {
        "id": "telefono",
        "label": "Número celular / teléfono",
        "categoria": "Contacto",
        "descripcion": "Solo debe ir en columnas de celular, teléfono o contacto."
    },

    {
        "id": "sexo",
        "label": "Sexo",
        "categoria": "Beneficiario",
        "descripcion": "Sexo del participante cuando la plantilla lo requiera."
    },
    {
        "id": "grupo_etario",
        "label": "Grupo etario",
        "categoria": "Beneficiario",
        "descripcion": "Grupo etario operativo para RPP/RAM/RAN/RRAN."
    },
    {
        "id": "unidad_servicio",
        "label": "Unidad de servicio / UDS / UCA",
        "categoria": "Unidad",
        "descripcion": "Nombre de la unidad de servicio."
    },
    {
        "id": "observaciones",
        "label": "Observaciones",
        "categoria": "Formato",
        "descripcion": "Observaciones del registro o del formato."
    },
    {
        "id": "fecha_entrega",
        "label": "Fecha de entrega",
        "categoria": "Entrega",
        "descripcion": "Fecha de entrega del complemento o formato."
    },
    {
        "id": "lote",
        "label": "Lote",
        "categoria": "Entrega",
        "descripcion": "Lote de Bienestarina u otro complemento."
    },
    {
        "id": "cantidad",
        "label": "Cantidad",
        "categoria": "Entrega",
        "descripcion": "Cantidad entregada."
    },
    {
        "id": "asistencia_x",
        "label": "Asistencia diaria X",
        "categoria": "Asistencia",
        "descripcion": "Marca X en días programados."
    },
    {
        "id": "total_asistencias",
        "label": "Total asistencias",
        "categoria": "Asistencia",
        "descripcion": "Total mensual de asistencias."
    },
    {
        "id": "verificacion_menor_6",
        "label": "Verificación cobertura menores de 6 meses",
        "categoria": "Cobertura",
        "descripcion": "Total de menores de seis meses."
    },
    {
        "id": "verificacion_mayor_6",
        "label": "Verificación cobertura mayores de 6 meses",
        "categoria": "Cobertura",
        "descripcion": "Total de mayores de seis meses."
    },
    {
        "id": "verificacion_gestantes",
        "label": "Verificación cobertura gestantes",
        "categoria": "Cobertura",
        "descripcion": "Total de madres gestantes."
    },
]
