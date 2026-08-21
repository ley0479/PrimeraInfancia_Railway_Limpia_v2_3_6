from __future__ import annotations

import sqlite3
import os
import sys
import tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]; sys.path.insert(0,str(ROOT/"backend")); sys.path.insert(0,str(ROOT))
from modules.base_maestra.repository import BaseMaestraRepository
from modules.importaciones_universales.repository import UniversalImportRepository
from services.data_import import UniversalMappingService
from services.data_import.service import file_sha256
from tests.test_universal_data_mapper_regression import build_fixture


def main():
    with tempfile.TemporaryDirectory(prefix="pi-universal-e2e-") as folder:
        database_path=str(Path(folder)/"database.sqlite3"); source=Path(folder)/"source.xlsx"; build_fixture(source)
        previous_skip=os.environ.get("SKIP_RUNTIME_SCHEMA_DDL"); previous_mode=os.environ.get("APP_SCHEMA_MIGRATION_MODE")
        os.environ["SKIP_RUNTIME_SCHEMA_DDL"]="1"; os.environ["APP_SCHEMA_MIGRATION_MODE"]="0"
        UniversalImportRepository(database_path).init_schema()
        assert not Path(database_path).exists(),"Runtime no debe crear esquema"
        os.environ["SKIP_RUNTIME_SCHEMA_DDL"]="0"; os.environ["APP_SCHEMA_MIGRATION_MODE"]="1"
        BaseMaestraRepository(database_path).init_schema(); repo=UniversalImportRepository(database_path); repo.init_schema()
        if previous_skip is None: os.environ.pop("SKIP_RUNTIME_SCHEMA_DDL",None)
        else: os.environ["SKIP_RUNTIME_SCHEMA_DDL"]=previous_skip
        if previous_mode is None: os.environ.pop("APP_SCHEMA_MIGRATION_MODE",None)
        else: os.environ["APP_SCHEMA_MIGRATION_MODE"]=previous_mode
        digest=file_sha256(str(source)); import_id=repo.create({"tenant_id":7,"usuario_id":11,"nombre_archivo":"source.xlsx","nombre_guardado":"source.xlsx","tipo_archivo":".xlsx","hash_sha256":digest})
        service=UniversalMappingService(); analysis=service.analyze(str(source)); repo.update_analysis(import_id,7,analysis)
        assert repo.replace_staging(import_id,7,service.staging_rows(str(source),analysis,chunk_size=53)) == 417
        mapping={field:decision["selected"]["column_id"] for field,decision in analysis["mapping"].items() if decision.get("selected")}
        profile_v1=repo.save_profile(import_id,7,11,mapping); assert profile_v1["version"] == 1
        profile_v2=repo.save_profile(import_id,7,11,mapping); assert profile_v2["version"] == 2,"Una corrección nueva debe crear versión, no sobrescribir"
        validation=repo.validate(import_id,7); assert not validation["errores"],validation
        imported=repo.import_to_base_master(import_id,7,11,"tester")
        assert imported["registros_importados"] == 417 and imported["registros_omitidos"] == 0,imported
        assert repo.find_hash(7,digest)["id"] == import_id
        assert repo.find_hash(8,digest) is None,"El hash no debe cruzar tenants"
        conn=sqlite3.connect(database_path)
        try:
            assert conn.execute("SELECT COUNT(*) FROM staging_cuentame WHERE carga_id=? AND fundacion_id=7",(imported["base_maestra_carga_id"],)).fetchone()[0] == 417
            assert conn.execute("SELECT COUNT(DISTINCT codigo_unidad) FROM staging_cuentame WHERE carga_id=?",(imported["base_maestra_carga_id"],)).fetchone()[0] == 39
            assert conn.execute("SELECT COUNT(*) FROM master_ninos").fetchone()[0] == 0,"Analizar/importar staging no debe publicar automáticamente"
        finally: conn.close()
        print("UNIVERSAL_IMPORT_E2E_SQLITE_PASS: 417 registros, 39 UDS, tenant aislado, sin publicación automática")


if __name__ == "__main__": main()
