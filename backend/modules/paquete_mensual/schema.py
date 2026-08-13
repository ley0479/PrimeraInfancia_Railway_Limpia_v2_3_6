
from __future__ import annotations

PM_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS pm_paquetes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fundacion_id INTEGER DEFAULT 1,
    usuario_id INTEGER,
    periodo TEXT NOT NULL,
    mes INTEGER NOT NULL,
    anio INTEGER NOT NULL,
    estado TEXT DEFAULT 'GENERADO',
    nombre_archivo TEXT,
    ruta_zip TEXT,
    ruta_carpeta TEXT,
    total_archivos INTEGER DEFAULT 0,
    tamano_bytes INTEGER DEFAULT 0,
    manifest_json TEXT,
    componentes_json TEXT,
    errores_json TEXT,
    observaciones TEXT,
    fecha_creacion TEXT NOT NULL,
    fecha_actualizacion TEXT
);

CREATE TABLE IF NOT EXISTS pm_archivos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    paquete_id INTEGER NOT NULL,
    categoria TEXT NOT NULL,
    nombre_archivo TEXT NOT NULL,
    ruta_archivo TEXT,
    tipo TEXT,
    tamano_bytes INTEGER DEFAULT 0,
    estado TEXT DEFAULT 'GENERADO',
    observaciones TEXT,
    fecha_creacion TEXT NOT NULL,
    FOREIGN KEY(paquete_id) REFERENCES pm_paquetes(id)
);

CREATE TABLE IF NOT EXISTS pm_auditoria (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    paquete_id INTEGER,
    accion TEXT NOT NULL,
    detalle TEXT,
    usuario_id INTEGER,
    fundacion_id INTEGER DEFAULT 1,
    fecha_accion TEXT NOT NULL,
    FOREIGN KEY(paquete_id) REFERENCES pm_paquetes(id)
);
"""

CATEGORIAS_PAQUETE = [
    ('01_Bienestarina', 'Bienestarina'),
    ('02_RPP', 'RPP'),
    # Se conserva el código interno para compatibilidad con paquetes históricos.
    ('03_RAM_RAN_RRAN', 'RAM'),
    ('04_Relacion_Mes', 'Relación del mes'),
    ('05_Cuentas_Cobro', 'Cuentas de cobro'),
    ('06_Informe_Nutricional', 'Informe nutricional'),
    ('07_Informe_Novedades', 'Informe de novedades'),
    ('08_Talento_Humano', 'Informe de talento humano'),
    ('09_Reporte_Gerencial', 'Reporte gerencial'),
    ('10_Auditoria_Mensual', 'Auditoría mensual'),
]
