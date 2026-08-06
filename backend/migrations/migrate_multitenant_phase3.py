#!/usr/bin/env python3
"""Migración reversible de aislamiento multi-fundación para SQLite.

- agrega metadatos tenant a tablas operativas heredadas;
- reemplaza restricciones UNIQUE globales de entidades principales por claves
  compuestas con ``fundacion_id``;
- crea índices de búsqueda por tenant;
- registra versión y resultado de la migración.

No elimina filas ni cambia el tenant de datos existentes: los valores NULL se
asignan a la fundación 1, que representa la instalación histórica.
"""
from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 3

CONTROL_TABLES = {
    'fundaciones', 'usuarios_app', 'sesiones_usuario', 'recuperacion_password',
    'auth_intentos', 'roles_sistema', 'permisos_sistema', 'rol_permiso',
    'planes_suscripcion', 'modulos_plan', 'paquetes_credito',
    'suscripciones_fundacion', 'historial_suscripcion', 'pagos_suscripcion',
    'movimientos_credito', 'auditoria_facturacion', 'configuracion',
}

LEGACY_TENANT_TABLES = {
    'beneficiarios', 'gestantes', 'docentes', 'coordinadores', 'unidades',
    'peso_talla', 'movimientos', 'plantillas', 'alertas', 'auditoria',
    'cargas_archivo', 'documentos_institucionales', 'entregables_operacion',
    'informes_pedagogicos', 'evidencias', 'copias_seguridad', 'usuarios',
    'cuentas_cobro_plantillas', 'cuentas_cobro_generadas',
    'relacion_mes_generada', 'configuracion_institucional',
    'identidad_visual_archivos', 'manuales_operativos',
    'manuales_operativos_secciones', 'auditoria_institucional_alpha41',
    'rpp_minutas', 'rpp_minutas_versiones', 'rpp_minutas_grupos',
    'rpp_minutas_productos', 'rpp_minutas_equivalencias',
    'rpp_minutas_pruebas', 'rpp_minutas_auditoria',
    'auditoria_seguridad', 'backups_sistema', 'backups_auditoria',
    'cargas_archivos', 'validaciones_cargas', 'corporaciones',
    'evaluaciones_cumplimiento', 'pc_ticket_comentarios', 'reglas_cumplimiento',
    'plantillas_oficiales', 'plantillas_oficiales_versiones',
    'plantillas_oficiales_mapeos', 'plantillas_oficiales_productos',
    'plantillas_oficiales_pruebas', 'plantillas_oficiales_auditoria',
}

TENANT_PREFIXES = (
    'gp_', 'sn_', 'pp_', 'master_', 'staging_', 'cb_', 'cd_', 'mp_',
    'pm_', 'rg_', 'th_', 'tm_', 'ui_', 'calendario_', 'gg_', 'pc_',
    'giu_', 'biblioteca_',
)

# Catálogos compartidos que conservan NULL como ámbito global.
SHARED_TABLES = {
    'tm_temas', 'sn_referencias_oms', 'sn_entregables_catalogo',
    'pp_tipos_actividad', 'gp_configuracion_entregables', 'estandares_icbf',
}

CORE_UNIQUE_RULES = {
    'beneficiarios': ('UNIQUE(fundacion_id, documento, unidad)', [
        (r'UNIQUE\s*\(\s*documento\s*,\s*unidad\s*\)', ''),
    ]),
    'gestantes': ('UNIQUE(fundacion_id, documento)', [
        (r'(\bdocumento\s+TEXT)\s+UNIQUE(\s+NOT\s+NULL)', r'\1\2'),
    ]),
    'docentes': ('UNIQUE(fundacion_id, documento)', [
        (r'(\bdocumento\s+TEXT)\s+UNIQUE(\s+NOT\s+NULL)', r'\1\2'),
    ]),
    'coordinadores': ('UNIQUE(fundacion_id, documento)', [
        (r'(\bdocumento\s+TEXT)\s+UNIQUE(\s+NOT\s+NULL)', r'\1\2'),
    ]),
    'unidades': ('UNIQUE(fundacion_id, nombre)', [
        (r'(\bnombre\s+TEXT)\s+UNIQUE(\s+NOT\s+NULL)', r'\1\2'),
    ]),
}


def _now() -> str:
    return datetime.now().isoformat(timespec='seconds')


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return bool(conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone())


def _columns(conn: sqlite3.Connection, table: str) -> list[str]:
    safe = table.replace('"', '""')
    return [str(r[1]) for r in conn.execute(f'PRAGMA table_info("{safe}")').fetchall()]


def _is_tenant_table(table: str) -> bool:
    if table.startswith('sqlite_') or table in CONTROL_TABLES:
        return False
    return table in LEGACY_TENANT_TABLES or table.startswith(TENANT_PREFIXES)


def _ensure_columns(conn: sqlite3.Connection, table: str) -> list[str]:
    existing = set(_columns(conn, table))
    added: list[str] = []
    definitions = {
        'fundacion_id': 'INTEGER',
        'usuario_creador_id': 'INTEGER',
        'fecha_creacion': 'TEXT',
        'fecha_actualizacion': 'TEXT',
    }
    for column, ddl in definitions.items():
        if column not in existing:
            conn.execute(f'ALTER TABLE "{table}" ADD COLUMN "{column}" {ddl}')
            existing.add(column)
            added.append(column)
    if 'fundacion_id' in existing and table not in SHARED_TABLES:
        conn.execute(f'UPDATE "{table}" SET fundacion_id=1 WHERE fundacion_id IS NULL')
    if 'fecha_creacion' in existing:
        conn.execute(
            f'UPDATE "{table}" SET fecha_creacion=COALESCE(fecha_creacion, ?) '
            'WHERE fecha_creacion IS NULL', (_now(),)
        )
    return added


def _normalize_table_sql(create_sql: str) -> str:
    """Limpia separadores residuales después de retirar restricciones."""
    previous = None
    normalized = create_sql
    while previous != normalized:
        previous = normalized
        normalized = re.sub(r',\s*,', ',', normalized)
    normalized = re.sub(r',\s*\)', '\n)', normalized)
    return normalized


def _insert_table_constraint(create_sql: str, constraint: str) -> str:
    create_sql = _normalize_table_sql(create_sql)
    close = create_sql.rfind(')')
    if close < 0:
        raise RuntimeError('CREATE TABLE inválido; no se encontró paréntesis final.')
    before = create_sql[:close].rstrip()
    # La restricción eliminada puede dejar una coma colgante. Se reconstruye
    # deliberadamente un solo separador antes de añadir la nueva restricción.
    before = re.sub(r',\s*$', '', before)
    separator = '' if before.endswith('(') else ','
    return before + separator + '\n    ' + constraint + '\n' + create_sql[close:]


def _rebuild_core_unique(conn: sqlite3.Connection, table: str) -> bool:
    if not _table_exists(conn, table):
        return False
    rule = CORE_UNIQUE_RULES[table]
    constraint, replacements = rule
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    if not row or not row[0]:
        return False
    original_sql = str(row[0])
    normalized = re.sub(r'\s+', '', original_sql).lower()
    if re.sub(r'\s+', '', constraint).lower() in normalized:
        return False

    # Captura índices y triggers explícitos; los autoíndices se recrean por la
    # nueva restricción UNIQUE compuesta.
    related = [
        (str(r[0]), str(r[1]), str(r[2]))
        for r in conn.execute(
            "SELECT type, name, sql FROM sqlite_master "
            "WHERE tbl_name=? AND type IN ('index','trigger') AND sql IS NOT NULL",
            (table,),
        ).fetchall()
    ]
    modified = original_sql
    for pattern, replacement in replacements:
        modified = re.sub(pattern, replacement, modified, flags=re.I)
    modified = _normalize_table_sql(modified)
    modified = _insert_table_constraint(modified, constraint)
    temporary = f'__mt3_new_{table}'
    modified = re.sub(
        r'^(\s*CREATE\s+TABLE\s+)(?:IF\s+NOT\s+EXISTS\s+)?["`\[]?' + re.escape(table) + r'["`\]]?',
        lambda m: m.group(1) + f'"{temporary}"',
        modified,
        count=1,
        flags=re.I,
    )
    columns = _columns(conn, table)
    quoted = ', '.join(f'"{c}"' for c in columns)
    conn.execute(f'DROP TABLE IF EXISTS "{temporary}"')
    conn.execute(modified)
    conn.execute(f'INSERT INTO "{temporary}" ({quoted}) SELECT {quoted} FROM "{table}"')
    conn.execute(f'DROP TABLE "{table}"')
    conn.execute(f'ALTER TABLE "{temporary}" RENAME TO "{table}"')
    for _kind, _name, ddl in related:
        try:
            conn.execute(ddl)
        except sqlite3.OperationalError as exc:
            # Un índice antiguo puede duplicar la nueva restricción; los demás
            # errores sí deben detener la migración.
            if 'already exists' not in str(exc).lower():
                raise
    return True


def _ensure_indexes(conn: sqlite3.Connection, table: str) -> list[str]:
    columns = set(_columns(conn, table))
    if 'fundacion_id' not in columns:
        return []
    safe_name = re.sub(r'[^A-Za-z0-9_]', '_', table)
    created: list[str] = []
    index_name = f'idx_mt3_{safe_name}_fundacion'
    conn.execute(f'CREATE INDEX IF NOT EXISTS "{index_name}" ON "{table}"(fundacion_id)')
    created.append(index_name)
    if 'id' in columns:
        compound = f'idx_mt3_{safe_name}_fundacion_id'
        conn.execute(f'CREATE INDEX IF NOT EXISTS "{compound}" ON "{table}"(fundacion_id, id)')
        created.append(compound)
    return created


def _migrate_calendar_unique(conn: sqlite3.Connection) -> bool:
    table = 'calendario_entregables'
    if not _table_exists(conn, table) or 'fundacion_id' not in _columns(conn, table):
        return False
    conn.execute('DROP INDEX IF EXISTS idx_calendario_entregables_clave')
    conn.execute(
        'CREATE UNIQUE INDEX IF NOT EXISTS idx_calendario_entregables_clave '
        'ON calendario_entregables(fundacion_id, clave_unica)'
    )
    return True


def migrate(database_path: str | Path) -> dict[str, Any]:
    path = Path(database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=60)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA busy_timeout=60000')
    conn.execute('PRAGMA foreign_keys=OFF')
    report: dict[str, Any] = {
        'schema_version': SCHEMA_VERSION,
        'started_at': _now(),
        'tables_tenant': [],
        'columns_added': {},
        'tables_rebuilt': [],
        'indexes_created': [],
        'calendar_unique_migrated': False,
    }
    try:
        conn.execute('BEGIN IMMEDIATE')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS tenant_migration_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                version INTEGER NOT NULL,
                estado TEXT NOT NULL,
                detalle_json TEXT,
                fecha TEXT NOT NULL
            )
        ''')
        tables = [
            str(r[0]) for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            ).fetchall()
        ]
        for table in tables:
            if not _is_tenant_table(table):
                continue
            report['tables_tenant'].append(table)
            added = _ensure_columns(conn, table)
            if added:
                report['columns_added'][table] = added

        for table in CORE_UNIQUE_RULES:
            if _rebuild_core_unique(conn, table):
                report['tables_rebuilt'].append(table)

        # Relee tablas luego de los rebuilds.
        for table in report['tables_tenant']:
            if _table_exists(conn, table):
                report['indexes_created'].extend(_ensure_indexes(conn, table))
        report['calendar_unique_migrated'] = _migrate_calendar_unique(conn)

        report['finished_at'] = _now()
        conn.execute(
            'INSERT INTO tenant_migration_log(version, estado, detalle_json, fecha) VALUES (?,?,?,?)',
            (SCHEMA_VERSION, 'OK', json.dumps(report, ensure_ascii=False), report['finished_at']),
        )
        conn.commit()
        check = conn.execute('PRAGMA integrity_check').fetchone()[0]
        if check != 'ok':
            raise RuntimeError(f'PRAGMA integrity_check falló después de migración: {check}')
        report['integrity'] = check
        return report
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.execute('PRAGMA foreign_keys=ON')
        conn.close()


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('database_path')
    args = parser.parse_args()
    print(json.dumps(migrate(args.database_path), ensure_ascii=False, indent=2))
