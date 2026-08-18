import ast
import sqlite3
from pathlib import Path


APP_PATH = Path(__file__).resolve().parents[1] / 'app.py'


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
