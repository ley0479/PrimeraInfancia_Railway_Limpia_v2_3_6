#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from modules.dbapi_compat import _sql_like, _translate_sqlite_sql  # noqa: E402
from tools.postgresql_runtime_audit import audit_runtime_sql  # noqa: E402


def require(ok, msg):
    if not ok:
        raise AssertionError(msg)


translated = _translate_sqlite_sql(
    "SELECT julianday(fecha_probable_parto)-julianday('now') FROM gestantes"
)
require("EXTRACT(EPOCH FROM CAST(fecha_probable_parto AS TIMESTAMP))" in translated, "julianday(columna) no se traduce")
require("EXTRACT(EPOCH FROM CURRENT_TIMESTAMP)" in translated, "julianday('now') no se traduce")
require("julianday" not in translated.lower(), "Quedó julianday en SQL PostgreSQL")
require(_sql_like("gp_planeaciones", "gp_%"), "LIKE positivo incorrecto")
require(not _sql_like("sn_valoraciones", "gp_%"), "LIKE filtró tabla equivocada")

audit = audit_runtime_sql(ROOT)
require(audit["status"] == "PASS", json.dumps(audit, ensure_ascii=False)[:3000])
require(not audit["direct_sqlite_imports"], "Persisten imports sqlite3 directos")
require(not audit["unsupported_constructs"], "Persisten construcciones SQL no soportadas")
require(any(item["construct"] == "julianday" for item in audit["supported_legacy_constructs"]), "La auditoría no detectó julianday legado")

for rel in [
    ".github/workflows/integrity-ci.yml",
    "backend/tools/integrity_gate.py",
    "backend/tools/safe_repair.py",
    "backend/tools/postgresql_runtime_audit.py",
    "backend/services/observability.py",
    "backend/modules/integrity_stability/routes.py",
    "integrity/baseline_v2_7_0.json",
    "integrity/safe_autofix_policy.json",
]:
    require((ROOT / rel).is_file(), f"Falta {rel}")

workflow = (ROOT / ".github/workflows/integrity-ci.yml").read_text(encoding="utf-8")
for token in ["postgres:16-alpine", "migrate_sqlite_to_postgresql.py", "integrity_gate.py", "merge_group", "Release package validator", "deployment-gate", "upload-artifact"]:
    require(token in workflow, f"CI no contiene {token}")


service_text = (ROOT / "backend/modules/integrity_stability/service.py").read_text(encoding="utf-8")
require('self.report_dir / f"integrity_gate_' in service_text, "El gate no escribe en DATA_DIR/integrity")
require('self.report_dir / f"safe_repair_' in service_text, "Safe Repair no escribe en DATA_DIR/integrity")

policy = json.loads((ROOT / "integrity/safe_autofix_policy.json").read_text(encoding="utf-8"))
require("change_business_rules" in policy["forbidden"], "La política no protege reglas de negocio")
require("auto_apply_database_migrations_in_production" in policy["forbidden"], "La política permite migraciones productivas automáticas")
print("Integridad/PostgreSQL 2.6.1: PASS")
