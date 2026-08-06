#!/usr/bin/env python3
"""Controles de regresión del núcleo multi-fundación, vigente en 2.5.2."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def require(path: str, *needles: str) -> str:
    text = (ROOT / path).read_text(encoding="utf-8", errors="ignore")
    for needle in needles:
        if needle not in text:
            raise AssertionError(f"{path} no contiene {needle!r}")
    return text


def main() -> None:
    env = require(
        ".env.example",
        "APP_VERSION=2.6.0-salud-nutricion-postgresql",
        "SINGLE_TENANT_MODE=false",
        "ALLOW_EXPERIMENTAL_MULTI_TENANT=true",
        "MULTI_TENANT_STRICT=true",
        "TENANT_STORAGE_ISOLATION=true",
        "MULTI_TENANT_SCHEMA_VERSION=3",
    )
    if re.search(r"INITIAL_ADMIN_PASSWORD=(?!REEMPLAZAR_).+", env):
        raise AssertionError(".env.example contiene contraseña utilizable")

    config = require(
        "backend/config.py",
        "ALLOW_EXPERIMENTAL_MULTI_TENANT=true como confirmación explícita",
        "MULTI_TENANT_STRICT debe permanecer activado",
        "TENANT_STORAGE_ISOLATION debe permanecer activado",
        "MULTI_TENANT_SCHEMA_VERSION debe ser 3 o superior",
    )
    require(
        "backend/app.py",
        "migrate_multitenant_phase3",
        "install_sqlite_tenant_guard",
        "tenant_path",
    )
    require(
        "backend/init_hosting.py",
        "migrate_multitenant_phase3",
        "ensure_tenant_directories",
    )
    require(
        "backend/modules/sqlalchemy_compat.py",
        "guarded_sql = _guard_core_sql",
        "execute_script con DML no está permitido",
    )
    require(
        "backend/modules/seguridad/routes.py",
        "LAST_SUPERADMIN_PROTECTED",
        "TENANT_INITIALIZATION_FAILED",
        "sesiones_invalidadas",
        "ensure_tenant_directories",
        "reglas_cumplimiento",
    )
    require(
        "backend/migrations/migrate_multitenant_phase3.py",
        "plantillas_oficiales_versiones",
        "reglas_cumplimiento",
        "estandares_icbf",
    )
    require(
        "backend/modules/motor_plantillas/schema.py",
        "idx_plantillas_versiones_fundacion",
        "fundacion_id INTEGER DEFAULT 1",
    )
    require(
        "backend/modules/facturacion_suscripcion/services.py",
        "authorized_fundacion_id",
        "No tienes permiso para operar sobre otra fundación",
    )
    require(
        "backend/modules/institucional_normativo.py",
        "tenant_storage_root",
        "/api/institucional-archivos/<path:relative_path>",
    )
    require(
        "frontend/js/modules/institucional-normativo.js",
        "Authorization",
        "URL.createObjectURL",
    )
    require(
        "INICIAR_PLATAFORMA_LOCAL.bat",
        "scripts_windows\\iniciar_plataforma.ps1",
        "-Mode Local",
    )
    launcher = require(
        "scripts_windows/iniciar_plataforma.ps1",
        "$env:SINGLE_TENANT_MODE = 'false'",
        "$env:ALLOW_EXPERIMENTAL_MULTI_TENANT = 'true'",
        "$env:MULTI_TENANT_STRICT = 'true'",
        "$env:TENANT_STORAGE_ISOLATION = 'true'",
    )

    # Los servicios que reciben un TenantPath deben resolverlo en tiempo de uso.
    require("backend/modules/paquete_mensual/services.py", "os.fspath(self._output_folder)")
    require("backend/modules/reportes_gerenciales/services.py", "os.fspath(self._output_folder)")
    require("backend/modules/salud_nutricion/entregables.py", "os.fspath(self._output_folder)")
    for relative in (
        "backend/modules/base_maestra/routes.py",
        "backend/modules/calidad_datos/routes.py",
        "backend/modules/cruce_bases/routes.py",
    ):
        text = (ROOT / relative).read_text(encoding="utf-8", errors="ignore")
        if "tenant_path" not in text and "resolve_tenant_path" not in text:
            raise AssertionError(f"{relative} no evidencia ruta por tenant")

    print("PASS test_multitenant_release_v2_4_0")


if __name__ == "__main__":
    main()
