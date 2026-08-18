"""Evita que un job de Fundación X se ejecute accidentalmente como fundación 1."""
import ast
import sys
from pathlib import Path
from types import SimpleNamespace

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from modules.seguridad.tenant_context import tenant_context


def _helpers():
    tree = ast.parse((BACKEND / "app.py").read_text(encoding="utf-8"))
    names = {"usuario_actual", "fundacion_actual_id", "rol_actual"}
    nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
    namespace = {"g": SimpleNamespace()}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(BACKEND / "app.py"), "exec"), namespace)
    return namespace


def test_job_conserva_fundacion_y_rol_autenticados():
    helpers = _helpers()
    with tenant_context(27, role="COORDINADOR", username="coord-x", source="test-job"):
        assert helpers["fundacion_actual_id"]() == 27
        assert helpers["rol_actual"]() == "COORDINADOR"
        assert helpers["usuario_actual"]()["username"] == "coord-x"


def test_request_autenticado_tiene_prioridad():
    helpers = _helpers()
    helpers["g"].current_user = {"fundacion_id": 9, "rol": "GERENTE", "username": "gerente"}
    with tenant_context(27, role="COORDINADOR", username="coord-x", source="test-job"):
        assert helpers["fundacion_actual_id"]() == 9
        assert helpers["rol_actual"]() == "GERENTE"


if __name__ == "__main__":
    test_job_conserva_fundacion_y_rol_autenticados()
    test_request_autenticado_tiene_prioridad()
    print("Tenant background generation v2.7.0: PASS")
