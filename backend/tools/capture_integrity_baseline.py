#!/usr/bin/env python3
"""Captura un contrato funcional estable sin congelar hashes del código.

El baseline conserva capacidades, rutas críticas, roles, formatos oficiales y
archivos obligatorios. Los cambios de implementación son permitidos mientras
el contrato se conserve o se amplíe.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_ROLES = [
    "SUPERADMIN", "GERENTE", "COORDINADOR", "AUXILIAR_ADMINISTRATIVO",
    "DOCENTE", "NUTRICIONISTA", "PSICOSOCIAL",
]
CRITICAL_MODULES = [
    "seguridad", "base_maestra", "gestion_integral_uca", "gestion_pedagogica",
    "salud_nutricion", "talento_humano", "calendario_inteligente",
    "motor_gestion_proyecto", "supervision_calidad", "familias_redes",
    "centro_planeacion", "componente_psicosocial", "backups", "reportes_gerenciales", "paquete_mensual",
]
CRITICAL_FILES = [
    "backend/app.py", "backend/config.py", "backend/database.py",
    "backend/modules/dbapi_compat.py", "backend/modules/seguridad/tenant_sql_guard.py",
    "backend/generador_formatos.py", "backend/motor_alertas.py",
    "frontend/index.html", "frontend/js/app.js", "frontend/js/config.js",
    "INICIAR_PLATAFORMA_LOCAL.bat", "INICIAR_PLATAFORMA_TUNEL_ONLINE.bat",
    "backend/modules/centro_planeacion/repository.py",
    "backend/modules/centro_planeacion/routes.py",
    "backend/modules/componente_psicosocial/repository.py",
    "backend/modules/componente_psicosocial/routes.py",
    "frontend/js/modules/centro-planeacion.js",
    "frontend/js/modules/componente-psicosocial.js",
    "frontend/css/centro-planeacion.css",
    "frontend/css/componente-psicosocial.css",
    "start_hosting.sh", "Dockerfile", "railway.json",
    "PROMPT_MAESTRO_CONTINUIDAD_NO_REGRESION.md",
    "integrity/format_capabilities.json",
]
CRITICAL_ROUTE_TOKENS = [
    "/api/health", "/api/auth/login", "/api/base-maestra",
    "/api/gestion-integral-uca", "/api/salud-nutricion",
    "/api/calendario-inteligente", "/api/motor-gestion-proyecto",
    "/api/supervision-calidad", "/api/familias-redes",
    "/api/centro-planeacion", "/api/psicosocial",
]
OFFICIAL_TEMPLATES = [
    "backend/seed_data/templates_originales/oficiales/plantilla_ram_oficial_v3.xlsx",
    "backend/seed_data/templates_originales/oficiales/plantilla_ram_oficial_v2_historica.xlsx",
    "backend/seed_data/templates_originales/oficiales/plantilla_rpp_oficial.xlsx",
    "backend/seed_data/templates_originales/oficiales/plantilla_rpp_oficial_v2026.xlsx",
    "backend/seed_data/templates_originales/oficiales/plantilla_bienestarina_oficial.xlsx",
    "backend/seed_data/templates_originales/oficiales/plantilla_bienestarina_oficial_v2026.xlsx",
]
FORMAT_CAPABILITIES = ["RAM", "RAN", "RPP", "BIENESTARINA", "LISTADO_ASISTENCIA"]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def route_strings(root: Path) -> list[str]:
    values: set[str] = set()
    pattern = re.compile(r"['\"](/api/[A-Za-z0-9_./{}<>:-]+)['\"]")
    for path in (root / "backend").rglob("*.py"):
        if "tests" in path.parts:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        values.update(pattern.findall(text))
    return sorted(values)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[2]))
    parser.add_argument("--version", default="2.7.0")
    parser.add_argument("--output", default="integrity/baseline_v2_7_0.json")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    output = (root / args.output).resolve()
    templates = {}
    for rel in OFFICIAL_TEMPLATES:
        path = root / rel
        if path.is_file():
            templates[rel] = {"sha256": sha256(path), "size": path.stat().st_size}
    baseline = {
        "schema_version": 1,
        "baseline_version": args.version,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "critical_files": CRITICAL_FILES,
        "critical_modules": CRITICAL_MODULES,
        "critical_route_tokens": CRITICAL_ROUTE_TOKENS,
        "observed_routes": route_strings(root),
        "roles": DEFAULT_ROLES,
        "format_capabilities": FORMAT_CAPABILITIES,
        "format_capability_scope": "ALL_FORMATS",
        "format_capability_registry": "integrity/format_capabilities.json",
        "official_templates": templates,
        "database_contract": {
            "production_backend": "postgresql",
            "local_recovery_backend": "sqlite",
            "multi_tenant_key": "fundacion_id",
            "schema_version_minimum": 3,
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(baseline, ensure_ascii=False, indent=2), encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
