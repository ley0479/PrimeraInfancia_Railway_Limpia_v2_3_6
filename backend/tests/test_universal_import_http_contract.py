from __future__ import annotations

import os
import sys
import tempfile
from io import BytesIO
from pathlib import Path

from flask import Flask, g

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from modules.importaciones_universales import routes


EXPECTED = {
    "/api/importaciones/analizar": {"POST"}, "/api/importaciones/<int:import_id>": {"GET"},
    "/api/importaciones/<int:import_id>/tablas": {"GET"}, "/api/importaciones/<int:import_id>/tabla": {"PUT"},
    "/api/importaciones/<int:import_id>/mapeo": {"GET", "PUT"}, "/api/importaciones/<int:import_id>/validar": {"POST"},
    "/api/importaciones/<int:import_id>/unidades": {"GET"}, "/api/importaciones/<int:import_id>/confirmar": {"POST"},
    "/api/importaciones/<int:import_id>/cancelar": {"POST"}, "/api/importaciones/<int:import_id>/errores": {"GET"},
    "/api/importaciones/<int:import_id>/auditoria": {"GET"},
}


class FakeRepository:
    def __init__(self, _path): pass
    def init_schema(self): pass
    def find_hash(self, *_): return None
    def create(self, _): return 9
    def confirmed_mapping(self, *_): return None
    def update_analysis(self, *_): return "REQUIERE_CONFIRMACION"
    def replace_staging(self, *_): return 1


class FakeService:
    def analyze(self, *_):
        return {"structure_fingerprint":"abc","selected_table":"data","preview":{"header_row":1,"header_depth":1,"rows":[],"columns":[]},"inspection":{"tables":[]},"mapping":{},"units":{"count":0},"format_compatibility":{},"requires_confirmation":True}
    def staging_rows(self, *_): return []


def main():
    originals = routes.UniversalImportRepository, routes.UniversalMappingService, routes.require_roles, routes.validate_tabular_source
    routes.UniversalImportRepository = FakeRepository; routes.UniversalMappingService = FakeService
    routes.require_roles = lambda *roles: (lambda function: function)
    routes.validate_tabular_source = lambda *args: {"signature_valid": True}
    try:
        with tempfile.TemporaryDirectory() as folder:
            app=Flask(__name__); app.config.update(ENABLE_UNIVERSAL_DATA_MAPPER=True, UNIVERSAL_IMPORT_MAX_BYTES=1024*1024)
            @app.before_request
            def user(): g.current_user={"id":4,"fundacion_id":7,"rol":"SUPERADMIN","username":"admin"}
            routes.register_importaciones_universales(app,str(Path(folder)/"db.sqlite3"),folder)
            rules={}
            for rule in app.url_map.iter_rules(): rules.setdefault(rule.rule,set()).update(rule.methods or ())
            for path,methods in EXPECTED.items():
                assert path in rules, f"Ruta no registrada: {path}"; assert methods <= rules[path], f"Método incorrecto: {path}"
            response=app.test_client().post("/api/importaciones/analizar",data={"file":(BytesIO(b"fixture"),"base.xlsx")},content_type="multipart/form-data")
            assert response.status_code == 201, response.get_json()
            assert response.get_json()["importacion_id"] == 9
    finally:
        routes.UniversalImportRepository, routes.UniversalMappingService, routes.require_roles, routes.validate_tabular_source = originals
    print("UNIVERSAL_IMPORT_HTTP_CONTRACT_PASS")


if __name__ == "__main__": main()
