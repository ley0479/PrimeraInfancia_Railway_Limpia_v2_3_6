#!/usr/bin/env python3
"""Contrato Railway: migrar en pre-deploy y servir sin DDL en runtime."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def require(value, message: str) -> None:
    if not value:
        raise AssertionError(message)


def run() -> None:
    railway = json.loads((ROOT / "railway.json").read_text(encoding="utf-8"))
    deploy = railway.get("deploy") or {}
    require(deploy.get("preDeployCommand") == ["./predeploy_hosting.sh"], "Pre-deploy Railway inválido")
    require(deploy.get("startCommand") == "./start_hosting.sh", "Start Command Railway inválido")
    require(deploy.get("healthcheckPath") == "/api/health", "Healthcheck Railway inválido")

    predeploy = (ROOT / "predeploy_hosting.sh").read_text(encoding="utf-8")
    runtime = (ROOT / "start_hosting.sh").read_text(encoding="utf-8")
    prepare = (ROOT / "backend" / "runtime_prepare.py").read_text(encoding="utf-8")
    require("python backend/init_hosting.py" in predeploy, "Pre-deploy no ejecuta migraciones")
    require("python backend/init_hosting.py" not in runtime, "Runtime todavía ejecuta migraciones")
    require("SKIP_RUNTIME_SCHEMA_DDL=1" in runtime, "Runtime no bloquea DDL")
    require("python backend/runtime_prepare.py" in runtime, "Runtime no prepara el volumen")
    require(runtime.find("runtime_prepare.py") < runtime.find("exec gunicorn"), "Gunicorn tiene orden inválido")
    require("get_db_connection" not in prepare and "configure_database" not in prepare, "Preparación runtime toca la base")
    print("PASS test_railway_healthcheck_predeploy_v2_7_0")


if __name__ == "__main__":
    run()
