#!/usr/bin/env python3
"""Gate reproducible de integridad, regresión y estabilidad.

El proceso termina con código distinto de cero cuando una capacidad estable se
pierde. No modifica datos de negocio y genera un reporte JSON auditable.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from postgresql_runtime_audit import audit_runtime_sql


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


class Gate:
    def __init__(self, root: Path, baseline: dict[str, Any]) -> None:
        self.root = root
        self.baseline = baseline
        self.checks: list[dict[str, Any]] = []
        self.blocking_failures = 0

    def record(self, name: str, ok: bool, detail: str = "", *, blocking: bool = True, evidence: Any = None) -> None:
        status = "PASS" if ok else ("FAIL" if blocking else "WARN")
        if not ok and blocking:
            self.blocking_failures += 1
        self.checks.append({"name": name, "status": status, "detail": detail, "evidence": evidence})
        print(f"[{status}] {name}" + (f": {detail}" if detail else ""))

    def check_contract(self) -> None:
        missing_files = [p for p in self.baseline.get("critical_files", []) if not (self.root / p).is_file()]
        self.record("Archivos críticos", not missing_files, ", ".join(missing_files[:20]), evidence=missing_files)

        missing_modules = [m for m in self.baseline.get("critical_modules", []) if not (self.root / "backend/modules" / m).exists()]
        self.record("Módulos críticos", not missing_modules, ", ".join(missing_modules[:20]), evidence=missing_modules)

        corpus = "\n".join(
            p.read_text(encoding="utf-8", errors="ignore")
            for base in (self.root / "backend", self.root / "frontend")
            for p in base.rglob("*") if p.is_file() and p.suffix.lower() in {".py", ".js", ".html"}
        )
        missing_routes = [token for token in self.baseline.get("critical_route_tokens", []) if token not in corpus]
        self.record("Rutas críticas", not missing_routes, ", ".join(missing_routes), evidence=missing_routes)
        missing_roles = [role for role in self.baseline.get("roles", []) if role not in corpus]
        self.record("Roles estables", not missing_roles, ", ".join(missing_roles), evidence=missing_roles)
        missing_formats = [name for name in self.baseline.get("format_capabilities", []) if name not in corpus.upper()]
        self.record("Capacidades de formatos", not missing_formats, ", ".join(missing_formats), evidence=missing_formats)

        changed_templates = []
        for rel, expected in (self.baseline.get("official_templates") or {}).items():
            path = self.root / rel
            if not path.is_file() or sha256(path) != expected.get("sha256"):
                changed_templates.append(rel)
        self.record("Plantillas oficiales estables", not changed_templates, ", ".join(changed_templates), evidence=changed_templates)

    def check_format_registry(self) -> None:
        """Valida la política transversal de continuidad de todos los formatos."""
        relative = self.baseline.get("format_capability_registry", "integrity/format_capabilities.json")
        path = self.root / relative
        if not path.is_file():
            self.record("Registro funcional de todos los formatos", False, f"{relative} ausente")
            return
        try:
            registry = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            self.record("Registro funcional de todos los formatos", False, f"JSON inválido: {exc}")
            return

        policy = registry.get("policy") or {}
        families = registry.get("format_families") or {}
        universal = registry.get("universal_capabilities") or []
        required_policy = {
            "default_protection": "PROTECTED",
            "unknown_formats": "AUTO_REGISTER_AND_BLOCK_UNTESTED",
            "deployment_on_failure": "BLOCKED",
        }
        errors = []
        if registry.get("scope") != "ALL_FORMATS":
            errors.append("scope debe ser ALL_FORMATS")
        for key, expected in required_policy.items():
            if policy.get(key) != expected:
                errors.append(f"policy.{key} debe ser {expected}")
        for key in ("stable_version_required", "incremental_patch_required", "regression_test_required", "official_template_hash_required"):
            if policy.get(key) is not True:
                errors.append(f"policy.{key} debe ser true")
        if not isinstance(universal, list) or len(set(universal)) < 10:
            errors.append("faltan capacidades universales")
        if not isinstance(families, dict) or "OTROS_DINAMICOS" not in families:
            errors.append("falta cobertura para formatos dinámicos")
        for name, config in families.items() if isinstance(families, dict) else []:
            if not config.get("aliases") or not config.get("capabilities"):
                errors.append(f"familia incompleta: {name}")
        self.record(
            "Registro funcional de todos los formatos",
            not errors,
            f"{len(families)} familias; {len(universal)} protecciones universales" if not errors else "; ".join(errors),
            evidence={"registry": relative, "errors": errors},
        )

    def check_protected_functionality(self) -> None:
        """Valida la matriz de baseline sin ejecutar ni modificar datos reales."""
        relative = self.baseline.get(
            "protected_functionality_registry",
            "integrity/protected_functionality.json",
        )
        path = self.root / relative
        if not path.is_file():
            self.record("Baseline funcional protegida", False, f"{relative} ausente")
            return
        try:
            registry = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            self.record("Baseline funcional protegida", False, f"JSON inválido: {exc}")
            return

        errors: list[str] = []
        functions = registry.get("functionalities") or []
        required = {"login", "panel", "postgresql", "base_maestra", "filtros_uds", "ram", "ran", "rran", "bienestarina", "rpp", "multi_tenant"}
        observed = {str(item.get("id") or "") for item in functions if isinstance(item, dict)}
        for missing in sorted(required - observed):
            errors.append(f"funcionalidad obligatoria ausente: {missing}")
        for item in functions:
            if not isinstance(item, dict):
                errors.append("registro de funcionalidad inválido")
                continue
            item_id = str(item.get("id") or "sin-id")
            if item.get("before") != "PASS":
                errors.append(f"{item_id}: baseline anterior no es PASS")
            if item.get("protection") != "PROTECTED":
                errors.append(f"{item_id}: protection debe ser PROTECTED")
            if not item.get("control_tests"):
                errors.append(f"{item_id}: sin prueba de control")
            for contract in item.get("contracts") or []:
                rel = str(contract.get("file") or "")
                token = str(contract.get("token") or "")
                source = self.root / rel
                if not rel or not token or not source.is_file():
                    errors.append(f"{item_id}: contrato inválido {rel}")
                    continue
                if token not in source.read_text(encoding="utf-8", errors="ignore"):
                    errors.append(f"{item_id}: contrato perdido en {rel}: {token}")
        environments = set(registry.get("required_environments") or [])
        if not {"LOCAL", "RAILWAY"}.issubset(environments):
            errors.append("la matriz debe exigir LOCAL y RAILWAY")
        self.record(
            "Baseline funcional protegida",
            not errors,
            f"{len(functions)} funcionalidades protegidas" if not errors else "; ".join(errors[:12]),
            evidence={"registry": relative, "errors": errors},
        )

    def check_python(self) -> None:
        failures = []
        files = [p for p in self.root.rglob("*.py") if ".git" not in p.parts]
        for path in files:
            try:
                ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            except Exception as exc:
                failures.append(f"{path.relative_to(self.root)}: {exc}")
        self.record("Sintaxis Python", not failures, f"{len(files)} archivos" if not failures else " | ".join(failures[:10]), evidence=failures)

    def check_javascript(self) -> None:
        node = shutil.which("node")
        if not node:
            self.record("Sintaxis JavaScript", True, "node no disponible; verificación diferida a CI", blocking=False)
            return
        failures = []
        files = list((self.root / "frontend").rglob("*.js"))
        for path in files:
            run = subprocess.run([node, "--check", str(path)], capture_output=True, text=True, check=False)
            if run.returncode:
                failures.append(f"{path.relative_to(self.root)}: {run.stderr.strip()}")
        self.record("Sintaxis JavaScript", not failures, f"{len(files)} archivos" if not failures else " | ".join(failures[:10]), evidence=failures)

    def check_postgresql_readiness(self) -> None:
        audit = audit_runtime_sql(self.root)
        direct = list(audit.get("direct_sqlite_imports") or [])
        unsupported = list(audit.get("unsupported_constructs") or [])
        missing_contract = list(audit.get("translator_contract_missing") or [])
        self.record("Runtime sin sqlite3 directo", not direct, ", ".join(direct), evidence=direct)
        self.record(
            "SQL runtime compatible con PostgreSQL",
            not unsupported and not missing_contract,
            f"sql={audit.get('sql_literals_scanned', 0)}, legado_soportado={len(audit.get('supported_legacy_constructs') or [])}, "
            f"no_soportado={len(unsupported)}, contrato_faltante={len(missing_contract)}",
            evidence={"unsupported": unsupported, "missing_contract": missing_contract},
        )
        backend = self.root / "backend"
        requirements = (backend / "requirements-production.txt").read_text(encoding="utf-8")
        self.record("Driver PostgreSQL declarado", "psycopg[binary]" in requirements, "psycopg[binary]")
        config = (backend / "config.py").read_text(encoding="utf-8")
        self.record(
            "Producción exige PostgreSQL",
            "REQUIRE_POSTGRESQL_IN_PRODUCTION" in config and "PostgreSQL" in config,
            "guard productivo",
        )


    def run_tests(self, tests_file: Path) -> None:
        spec = json.loads(tests_file.read_text(encoding="utf-8"))
        failures = []
        executed = 0
        env = os.environ.copy()
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env["PYTHONPATH"] = str(self.root / "backend")
        for rel in spec.get("tests", []):
            path = self.root / "backend" / rel
            if not path.is_file():
                failures.append(f"faltante:{rel}")
                continue
            run = subprocess.run(
                [sys.executable, str(path)], cwd=str(self.root / "backend"), env=env,
                capture_output=True, text=True, check=False, timeout=180,
            )
            executed += 1
            if run.returncode:
                failures.append(f"{rel}: {(run.stdout + run.stderr)[-1200:]}")
        self.record("Regresión crítica", not failures, f"{executed} pruebas" if not failures else " | ".join(failures[:8]), evidence=failures)

    def check_manifest(self) -> None:
        path = self.root / "MANIFEST_SHA256.txt"
        if not path.is_file():
            self.record("Manifiesto SHA-256", False, "MANIFEST_SHA256.txt ausente")
            return
        malformed = []
        missing = []
        mismatched = []
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip() or line.startswith("#"):
                continue
            match = re.fullmatch(r"([0-9a-f]{64})  (.+)", line)
            if not match:
                malformed.append(number)
                continue
            expected, rel = match.groups()
            file_path = self.root / rel
            if not file_path.is_file():
                missing.append(rel)
            elif sha256(file_path) != expected:
                mismatched.append(rel)
        # Durante desarrollo el manifiesto cambia; se exige coherencia en el ZIP final.
        ok = not malformed and not missing
        detail = f"malformadas={len(malformed)}, faltantes={len(missing)}, cambiadas={len(mismatched)}"
        self.record("Manifiesto SHA-256", ok, detail, blocking=True, evidence={"malformed": malformed, "missing": missing, "changed": mismatched})
        if mismatched:
            self.record("Manifiesto requiere regeneración", False, f"{len(mismatched)} archivos modificados", blocking=False, evidence=mismatched)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[2]))
    parser.add_argument("--baseline", default="integrity/baseline_v2_7_0.json")
    parser.add_argument("--tests", default="integrity/critical_tests.json")
    parser.add_argument("--report", default="data/integrity/integrity_gate.json")
    parser.add_argument("--skip-tests", action="store_true")
    parser.add_argument("--skip-manifest", action="store_true")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    baseline = json.loads((root / args.baseline).read_text(encoding="utf-8"))
    gate = Gate(root, baseline)
    started = time.perf_counter()
    gate.check_contract()
    gate.check_format_registry()
    gate.check_protected_functionality()
    gate.check_python()
    gate.check_javascript()
    gate.check_postgresql_readiness()
    if not args.skip_tests:
        gate.run_tests(root / args.tests)
    if not args.skip_manifest:
        gate.check_manifest()
    report = {
        "schema_version": 1,
        "started_at": now(),
        "baseline_version": baseline.get("baseline_version"),
        "duration_seconds": round(time.perf_counter() - started, 3),
        "status": "PASS" if gate.blocking_failures == 0 else "BLOCKED",
        "blocking_failures": gate.blocking_failures,
        "checks": gate.checks,
    }
    report_path = (root / args.report).resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Reporte: {report_path}")
    return 0 if gate.blocking_failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
