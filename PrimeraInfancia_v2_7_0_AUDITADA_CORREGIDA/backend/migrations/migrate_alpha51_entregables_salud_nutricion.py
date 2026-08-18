"""Migración segura ALPHA51: Entregables Salud y Nutrición.

Crea tablas independientes con IF NOT EXISTS y siembra el catálogo base de 15
entregables. No modifica Base Maestra, usuarios, beneficiarios ni formatos.
"""
from __future__ import annotations

import os
import sqlite3
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = os.environ.get('PRIMERA_INFANCIA_DB') or str(ROOT / 'database.sqlite3')

ENTREGABLES_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS sn_entregables_catalogo (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo TEXT NOT NULL UNIQUE,
    nombre TEXT NOT NULL,
    descripcion TEXT,
    actividad TEXT,
    evidencias_requeridas TEXT,
    forma_entrega TEXT DEFAULT 'Físico',
    responsable TEXT DEFAULT 'Enfermera/Nutricionista',
    periodicidad TEXT DEFAULT 'Mensual',
    aplica_por_uds INTEGER DEFAULT 1,
    requiere_acta INTEGER DEFAULT 0,
    requiere_listado INTEGER DEFAULT 0,
    requiere_fotos INTEGER DEFAULT 0,
    minimo_fotos INTEGER DEFAULT 0,
    requiere_oficio INTEGER DEFAULT 0,
    requiere_formato_excel INTEGER DEFAULT 0,
    requiere_word INTEGER DEFAULT 0,
    requiere_pdf INTEGER DEFAULT 0,
    requiere_firma INTEGER DEFAULT 0,
    plantilla_asociada TEXT,
    estado TEXT DEFAULT 'ACTIVO',
    observaciones TEXT,
    fecha_creacion TEXT,
    fecha_actualizacion TEXT
);

CREATE TABLE IF NOT EXISTS sn_entregables_mes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    catalogo_id INTEGER NOT NULL,
    codigo TEXT NOT NULL,
    mes INTEGER NOT NULL,
    anio INTEGER NOT NULL,
    uds TEXT DEFAULT 'TODAS',
    coordinador TEXT,
    fundacion_id INTEGER DEFAULT 1,
    corporacion_id INTEGER DEFAULT 1,
    responsable TEXT,
    estado TEXT DEFAULT 'pendiente',
    observaciones TEXT,
    porcentaje INTEGER DEFAULT 0,
    fecha_creacion TEXT,
    fecha_actualizacion TEXT,
    usuario_id INTEGER,
    UNIQUE(catalogo_id, mes, anio, uds, fundacion_id),
    FOREIGN KEY (catalogo_id) REFERENCES sn_entregables_catalogo(id)
);

CREATE TABLE IF NOT EXISTS sn_entregables_evidencias (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entregable_id INTEGER NOT NULL,
    nombre_original TEXT,
    nombre_guardado TEXT,
    ruta_archivo TEXT NOT NULL,
    tipo TEXT DEFAULT 'foto',
    actividad TEXT,
    fecha_actividad TEXT,
    uds TEXT,
    responsable TEXT,
    observaciones TEXT,
    fecha_carga TEXT,
    usuario_id INTEGER,
    FOREIGN KEY (entregable_id) REFERENCES sn_entregables_mes(id)
);

CREATE TABLE IF NOT EXISTS sn_entregables_archivos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entregable_id INTEGER,
    tipo TEXT NOT NULL,
    nombre_archivo TEXT NOT NULL,
    ruta_archivo TEXT NOT NULL,
    estado TEXT DEFAULT 'generado',
    metadata_json TEXT,
    fecha_generacion TEXT,
    usuario_id INTEGER,
    FOREIGN KEY (entregable_id) REFERENCES sn_entregables_mes(id)
);

CREATE TABLE IF NOT EXISTS sn_entregables_validaciones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entregable_id INTEGER NOT NULL,
    valido INTEGER DEFAULT 0,
    pendientes_json TEXT,
    resultado_json TEXT,
    fecha_validacion TEXT,
    usuario_id INTEGER,
    FOREIGN KEY (entregable_id) REFERENCES sn_entregables_mes(id)
);

CREATE TABLE IF NOT EXISTS sn_entregables_observaciones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entregable_id INTEGER NOT NULL,
    observacion TEXT NOT NULL,
    estado TEXT DEFAULT 'abierta',
    fecha_creacion TEXT,
    usuario_id INTEGER,
    FOREIGN KEY (entregable_id) REFERENCES sn_entregables_mes(id)
);

CREATE INDEX IF NOT EXISTS idx_sn_entregables_mes_periodo ON sn_entregables_mes(anio, mes, uds);
CREATE INDEX IF NOT EXISTS idx_sn_entregables_mes_estado ON sn_entregables_mes(estado);
CREATE INDEX IF NOT EXISTS idx_sn_entregables_evidencias_entregable ON sn_entregables_evidencias(entregable_id);
CREATE INDEX IF NOT EXISTS idx_sn_entregables_archivos_entregable ON sn_entregables_archivos(entregable_id);
"""

CATALOGO_BASE = [
    dict(codigo='E01_REGISTRO_NOVEDADES', nombre='Registro de novedades, articulaciones en salud y garantía de derechos',
         actividad='Acta de revisión de carpeta; identificación de garantías de derechos y canalizaciones.',
         evidencias='Acta de revisión, formato de novedades, oficio/correo de articulación y evidencias fotográficas.', acta=1, listado=0, fotos=1, oficio=1, excel=1, word=1),
    dict(codigo='E02_AAVN', nombre='Preparación y consumo de AAVN',
         actividad='Orientación a familias sobre preparación y consumo de AAVN.',
         evidencias='Acta, listado de asistencia y evidencias fotográficas.', acta=1, listado=1, fotos=1, oficio=0, excel=0, word=1),
    dict(codigo='E03_LACTANCIA', nombre='Lactancia materna / extracción de lactancia',
         actividad='Promover práctica de lactancia con gestantes, madres lactantes y familias.',
         evidencias='Acta, listado de asistencia y evidencias fotográficas.', acta=1, listado=1, fotos=1, oficio=0, excel=0, word=1),
    dict(codigo='E04_FICHA_LACTANCIA', nombre='Ficha de observación de lactancia materna',
         actividad='Aplicación y diligenciamiento de formato de lactancia materna.',
         evidencias='Formato ficha de observación y soportes fotográficos.', acta=0, listado=0, fotos=1, oficio=0, excel=1, word=0),
    dict(codigo='E05_ANTROPOMETRIA', nombre='Formato de captura de medidas antropométricas',
         actividad='Toma de peso, talla y perímetro braquial; usuarios nuevos, gestantes y seguimiento a riesgo/DNT.',
         evidencias='Formato de captura por grupo, reporte de Cuéntame y fotografías de valoración.', acta=0, listado=0, fotos=1, oficio=0, excel=1, word=0),
    dict(codigo='E06_SIGNOS_FISICOS', nombre='Formato de identificación de signos físicos',
         actividad='Aplicación y diligenciamiento de formato de signos físicos.',
         evidencias='Formato Excel magnético y muestra física en informe.', acta=0, listado=0, fotos=0, oficio=0, excel=1, word=0),
    dict(codigo='E07_MONITOREO_DNT', nombre='Formato de monitoreo de signos de alarma DNT',
         actividad='Monitoreo semanal para DNT, riesgo de DNT y signos físicos.',
         evidencias='Formato Excel magnético y anexo físico en informe.', acta=0, listado=0, fotos=0, oficio=0, excel=1, word=0),
    dict(codigo='E08_SOCIALIZACION_RPP', nombre='Socialización de minuta RPP',
         actividad='Socialización de minuta de raciones alimentarias.',
         evidencias='Acta, listado de asistencia y evidencias fotográficas.', acta=1, listado=1, fotos=1, oficio=0, excel=0, word=1),
    dict(codigo='E09_CONTROL_CALIDAD', nombre='Control de calidad de raciones y alimentos',
         actividad='Verificación de raciones alimentarias, almacenamiento y entrega de RPP/Bienestarina.',
         evidencias='Acta de verificación de alimentos y evidencias de verificación/almacenamiento.', acta=1, listado=0, fotos=1, oficio=0, excel=1, word=1),
    dict(codigo='E10_LIMPIEZA_DESINFECCION', nombre='Acta de limpieza y desinfección de UCAS',
         actividad='Verificación de limpieza y desinfección en UCAS.',
         evidencias='Acta, evidencias fotográficas y muestras de saneamiento básico.', acta=1, listado=0, fotos=1, oficio=0, excel=1, word=1),
    dict(codigo='E11_ENCUENTROS_HOGAR', nombre='Encuentros en el hogar',
         actividad='Encuentros en hogares priorizados: puerperio, DNT, riesgo, enfermedad o garantía de derechos.',
         evidencias='Formato de encuentro en el hogar, mínimo 10 muestras y evidencias fotográficas.', acta=0, listado=1, fotos=1, oficio=0, excel=1, word=1),
    dict(codigo='E12_ARTICULACION_INTERINSTITUCIONAL', nombre='Articulación interinstitucional',
         actividad='Oficio de acuerdo a la situación encontrada.',
         evidencias='Oficio físico/digital.', acta=0, listado=0, fotos=0, oficio=1, excel=0, word=1),
    dict(codigo='E13_ENTREGA_RPP', nombre='Entrega de RPP',
         actividad='Evidencias fotográficas de entrega de RPP.',
         evidencias='Evidencias fotográficas de entrega de RPP.', acta=0, listado=0, fotos=1, oficio=0, excel=0, word=0),
    dict(codigo='E14_OLLAS_REFRIGERIOS', nombre='Preparaciones de ollas comunitarias o entrega de refrigerios',
         actividad='Evidencias de preparación de olla comunitaria o entrega/consumo de refrigerios.',
         evidencias='Evidencias fotográficas con participación de familias.', acta=0, listado=1, fotos=1, oficio=0, excel=0, word=1),
    dict(codigo='E15_CUALIFICACION_TH', nombre='Acta de cualificación al talento humano',
         actividad='Cualificación en lactancia, almacenamiento de alimentos y control de plagas.',
         evidencias='Acta, listado de asistencia y evidencias fotográficas.', acta=1, listado=1, fotos=1, oficio=0, excel=0, word=1),
]


def migrate(db_path: str = DB_PATH) -> dict:
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.executescript(ENTREGABLES_SCHEMA_SQL)
        now = datetime.now().isoformat(timespec='seconds')
        inserted = 0
        for item in CATALOGO_BASE:
            exists = cur.execute('SELECT id FROM sn_entregables_catalogo WHERE codigo = ?', (item['codigo'],)).fetchone()
            if exists:
                continue
            cur.execute(
                """
                INSERT INTO sn_entregables_catalogo
                (codigo, nombre, descripcion, actividad, evidencias_requeridas, forma_entrega, responsable,
                 periodicidad, aplica_por_uds, requiere_acta, requiere_listado, requiere_fotos, minimo_fotos,
                 requiere_oficio, requiere_formato_excel, requiere_word, requiere_pdf, requiere_firma,
                 plantilla_asociada, estado, observaciones, fecha_creacion, fecha_actualizacion)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item['codigo'], item['nombre'], item.get('descripcion') or item['nombre'], item['actividad'],
                    item['evidencias'], 'Físico', 'Enfermera/Nutricionista', 'Mensual', 1,
                    item.get('acta', 0), item.get('listado', 0), item.get('fotos', 0), 4 if item.get('fotos', 0) else 0,
                    item.get('oficio', 0), item.get('excel', 0), item.get('word', 0), 0,
                    1 if item.get('acta') or item.get('listado') else 0,
                    item['codigo'], 'ACTIVO', 'Catálogo base ALPHA51', now, now,
                ),
            )
            inserted += 1
        conn.commit()
        total = cur.execute('SELECT COUNT(*) FROM sn_entregables_catalogo').fetchone()[0]
        return {'ok': True, 'inserted': inserted, 'catalogo_total': total, 'db_path': db_path}
    finally:
        conn.close()


if __name__ == '__main__':
    print(migrate())
