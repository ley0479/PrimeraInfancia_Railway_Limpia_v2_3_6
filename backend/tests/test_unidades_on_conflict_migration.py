import ast
import sqlite3
from pathlib import Path


APP_PATH = Path(__file__).resolve().parents[1] / 'app.py'
MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / 'migrations'
    / 'migrate_unidades_tenant_unique_v7.py'
)


def _load_schema_helpers():
    source = APP_PATH.read_text(encoding='utf-8')
    tree = ast.parse(source)
    wanted = {'table_columns', 'ensure_column', 'ensure_unidades_upsert_constraint'}
    nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in wanted]
    namespace = {}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(APP_PATH), 'exec'), namespace)
    # El contrato productivo consulta information_schema. Para reproducir la
    # migración con SQLite en memoria solo se sustituye esa introspección.
    namespace['table_columns'] = lambda cursor, table: {
        row[1] for row in cursor.execute(f"PRAGMA table_info('{table}')").fetchall()
    }
    return namespace


def _legacy_database():
    conn = sqlite3.connect(':memory:')
    conn.execute('''
        CREATE TABLE unidades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT UNIQUE NOT NULL,
            total_usuarios INTEGER DEFAULT 0,
            fecha_actualizacion TEXT NOT NULL
        )
    ''')
    conn.execute(
        "INSERT INTO unidades(nombre, total_usuarios, fecha_actualizacion) VALUES('UDS EXISTENTE', 3, 'antes')"
    )
    return conn


def test_migracion_existente_habilita_on_conflict_sin_perder_datos():
    helpers = _load_schema_helpers()
    conn = _legacy_database()

    helpers['ensure_unidades_upsert_constraint'](conn.cursor())
    conn.execute('''
        INSERT INTO unidades(nombre, total_usuarios, fecha_actualizacion, fundacion_id)
        VALUES('UDS EXISTENTE', 20, 'despues', 1)
        ON CONFLICT(fundacion_id, nombre) DO UPDATE SET
            total_usuarios=excluded.total_usuarios,
            fecha_actualizacion=excluded.fecha_actualizacion
    ''')

    rows = conn.execute(
        'SELECT nombre, total_usuarios, fecha_actualizacion, fundacion_id FROM unidades'
    ).fetchall()
    assert rows == [('UDS EXISTENTE', 20, 'despues', 1)]


def test_migracion_es_idempotente():
    helpers = _load_schema_helpers()
    conn = _legacy_database()

    helpers['ensure_unidades_upsert_constraint'](conn.cursor())
    helpers['ensure_unidades_upsert_constraint'](conn.cursor())

    indexes = conn.execute("PRAGMA index_list('unidades')").fetchall()
    assert sum(1 for row in indexes if row[1] == 'idx_unidades_fundacion_nombre') == 1
    assert conn.execute('SELECT COUNT(*) FROM unidades').fetchone()[0] == 1


def test_contrato_final_permite_el_mismo_nombre_en_fundaciones_distintas():
    conn = sqlite3.connect(':memory:')
    conn.execute('''
        CREATE TABLE unidades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fundacion_id INTEGER NOT NULL,
            nombre TEXT NOT NULL,
            total_usuarios INTEGER DEFAULT 0,
            UNIQUE(fundacion_id, nombre)
        )
    ''')

    conn.execute(
        "INSERT INTO unidades(fundacion_id, nombre, total_usuarios) VALUES(1, 'BAJO PACURITA', 10)"
    )
    conn.execute(
        "INSERT INTO unidades(fundacion_id, nombre, total_usuarios) VALUES(2, 'BAJO PACURITA', 15)"
    )
    conn.execute('''
        INSERT INTO unidades(fundacion_id, nombre, total_usuarios)
        VALUES(2, 'BAJO PACURITA', 20)
        ON CONFLICT(fundacion_id, nombre) DO UPDATE SET
            total_usuarios=excluded.total_usuarios
    ''')

    assert conn.execute(
        "SELECT fundacion_id, total_usuarios FROM unidades WHERE nombre='BAJO PACURITA' ORDER BY fundacion_id"
    ).fetchall() == [(1, 10), (2, 20)]


def test_predeploy_retira_solo_la_restriccion_global_legacy():
    source = MIGRATION_PATH.read_text(encoding='utf-8')

    assert 'constraint_columns == ["nombre"]' in source
    assert 'ALTER TABLE unidades DROP CONSTRAINT' in source
    assert 'DROP CONSTRAINT IF EXISTS unidades_nombre_key' in source
    assert 'remaining_legacy' in source
    assert 'ON unidades(fundacion_id, nombre)' in source
    assert 'HAVING COUNT(*) > 1' in source
    assert 'DELETE FROM UNIDADES' not in source.upper()
    assert 'DROP TABLE' not in source.upper()


if __name__ == '__main__':
    test_migracion_existente_habilita_on_conflict_sin_perder_datos()
    test_migracion_es_idempotente()
    test_contrato_final_permite_el_mismo_nombre_en_fundaciones_distintas()
    test_predeploy_retira_solo_la_restriccion_global_legacy()
    print('UNIDADES_TENANT_UNIQUE_MIGRATION_PASS')
