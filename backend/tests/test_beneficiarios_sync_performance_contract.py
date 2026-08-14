import ast
from pathlib import Path


APP_PATH = Path(__file__).resolve().parents[1] / 'app.py'


def _function_node(name):
    tree = ast.parse(APP_PATH.read_text(encoding='utf-8'))
    return next(
        node for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name
    )


def test_beneficiarios_sync_precarga_ids_fuera_del_bucle():
    """Impide reintroducir un SELECT por cada fila de la Base Maestra."""
    function = _function_node('guardar_beneficiarios_actuales')
    source = ast.get_source_segment(APP_PATH.read_text(encoding='utf-8'), function)

    assert 'SELECT id, documento FROM beneficiarios' in source

    row_loop = next(
        node for node in ast.walk(function)
        if isinstance(node, ast.For) and 'df.iterrows()' in ast.unparse(node.iter)
    )
    loop_source = ast.get_source_segment(APP_PATH.read_text(encoding='utf-8'), row_loop)
    assert 'SELECT id FROM beneficiarios WHERE documento' not in loop_source


def test_beneficiarios_sync_conserva_transaccion_y_aislamiento_tenant():
    function = _function_node('guardar_beneficiarios_actuales')
    source = ast.get_source_segment(APP_PATH.read_text(encoding='utf-8'), function)

    assert 'fundacion_id = fundacion_actual_id()' in source
    assert 'COALESCE(fundacion_id, 1) = ?' in source
    assert 'conn.commit()' in source
    assert 'conn.close()' in source
