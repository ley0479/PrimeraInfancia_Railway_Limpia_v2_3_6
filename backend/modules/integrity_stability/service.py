"""Servicios del Motor de Integridad, Supervisión y Estabilidad."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from modules.dbapi_compat import sqlite3


class IntegrityStabilityService:
    def __init__(self, project_root: str, data_dir: str, database_path: str | None = None) -> None:
        self.root = Path(project_root).resolve()
        self.data_dir = Path(data_dir).resolve()
        self.report_dir = self.data_dir / "integrity"
        self.report_dir.mkdir(parents=True, exist_ok=True)
        self.database_path = database_path

    def _database_diagnostic(self) -> dict[str, Any]:
        required = {
            "usuarios_app": ("id", "fundacion_id", "username", "password_hash", "rol", "activo"),
            "fundaciones": ("id",),
            "roles_sistema": ("id",),
            "sesiones_usuario": ("id", "usuario_id"),
            "calendario_entregables": ("id", "fundacion_id"),
        }
        result: dict[str, Any] = {"ok": False, "required_tables": {}, "users": {}}
        if not self.database_path:
            result["error"] = "Ruta de base no configurada para el diagnóstico."
            return result
        try:
            with sqlite3.connect(self.database_path, timeout=15) as conn:
                conn.row_factory = sqlite3.Row
                for table, columns in required.items():
                    try:
                        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
                        present = {str(row["name"]) for row in rows}
                        missing = sorted(set(columns) - present)
                        result["required_tables"][table] = {"exists": bool(rows), "missing_columns": missing}
                    except Exception as exc:
                        result["required_tables"][table] = {"exists": False, "error": type(exc).__name__}
                try:
                    users = conn.execute("SELECT rol,activo,COUNT(*) total FROM usuarios_app GROUP BY rol,activo").fetchall()
                    result["users"] = {
                        "total": sum(int(row["total"]) for row in users),
                        "active": sum(int(row["total"]) for row in users if int(row["activo"] or 0) == 1),
                        "roles": sorted({str(row["rol"] or "SIN_ROL") for row in users}),
                    }
                except Exception as exc:
                    result["users"] = {"error": type(exc).__name__}
            result["ok"] = all(x.get("exists") and not x.get("missing_columns") for x in result["required_tables"].values())
        except Exception as exc:
            result["error"] = f"{type(exc).__name__}: conexión o consulta fallida"
        return result

    def _log_diagnostic(self) -> dict[str, Any]:
        patterns = {
            "errors": re.compile(r"\b(ERROR|CRITICAL|Traceback|Exception)\b", re.I),
            "auth_401": re.compile(r"(?:auth/login|login).{0,120}\b401\b|\b401\b.{0,120}(?:auth/login|login)", re.I),
            "db_failures": re.compile(r"(database|postgres|psycopg|sql).{0,100}(error|failed|timeout|refused)", re.I),
        }
        summary = {"files_scanned": 0, "bytes_scanned": 0, "counts": {key: 0 for key in patterns}, "files": []}
        for directory in (self.data_dir / "logs", self.root / "logs_tunel"):
            if not directory.is_dir():
                continue
            for path in sorted(directory.glob("*.log"), key=lambda item: item.stat().st_mtime, reverse=True)[:20]:
                try:
                    size = path.stat().st_size
                    with path.open("rb") as stream:
                        stream.seek(max(0, size - 2 * 1024 * 1024))
                        text = stream.read().decode("utf-8", errors="ignore")
                    counts = {key: len(pattern.findall(text)) for key, pattern in patterns.items()}
                    summary["files_scanned"] += 1; summary["bytes_scanned"] += len(text.encode("utf-8"))
                    if any(counts.values()): summary["files"].append({"name": path.name, "counts": counts})
                    for key, value in counts.items(): summary["counts"][key] += value
                except OSError:
                    continue
        summary["privacy"] = "Solo se reportan conteos; no se exponen cuerpos, usuarios, claves ni tokens."
        return summary

    def runtime_monitor_status(self) -> dict[str, Any]:
        path = self.report_dir / "runtime_monitor.jsonl"
        if not path.is_file(): return {"status": "SIN_DATOS", "samples": 0}
        try:
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()[-100:]
            rows = [json.loads(line) for line in lines if line.strip()]
            failures = sum(not bool(row.get("ok")) for row in rows)
            return {"status": "OK" if rows and not failures else "DEGRADADO", "samples": len(rows), "failures": failures, "last": rows[-1] if rows else None}
        except Exception:
            return {"status": "ERROR_LECTURA", "samples": 0}

    def central_diagnostic(self, config: dict[str, Any], *, mode: str = "MANUAL") -> dict[str, Any]:
        auth_routes = (self.root / "backend/modules/seguridad/routes.py").read_text(encoding="utf-8", errors="ignore")
        permission_service = (self.root / "backend/modules/seguridad/services.py").read_text(encoding="utf-8", errors="ignore")
        protected = {
            "business_data": ["usuarios_app", "base_maestra", "participantes", "fundaciones"],
            "official_assets": ["plantillas oficiales", "formatos oficiales"],
            "automatic_mutation_allowed": False,
        }
        checks = {
            "login_endpoint": "/login" in auth_routes and "check_password_hash" in auth_routes,
            "jwt_generation": "create_access_token" in auth_routes or "encode_access_token" in auth_routes,
            "role_matrix": "ROLE_MENU_PERMISSIONS" in permission_service and "PATH_ROLE_RULES" in permission_service,
            "fail_closed_routes": "return False" in permission_service or "deniega" in permission_service.lower(),
            "secret_key_configured": len(str(config.get("SECRET_KEY") or "")) >= 32,
            "jwt_secret_configured": len(str(config.get("JWT_SECRET_KEY") or "")) >= 32,
            "separate_secrets": bool(config.get("SECRET_KEY")) and config.get("SECRET_KEY") != config.get("JWT_SECRET_KEY"),
        }
        database = self._database_diagnostic(); logs = self._log_diagnostic(); monitor = self.runtime_monitor_status()
        status = "PASS" if all(checks.values()) and database.get("ok") else "ATTENTION"
        report = {"schema_version": 1, "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "mode": mode, "status": status, "authentication_rbac": checks, "database_structure": database, "logs": logs, "permanent_monitor": monitor, "protection_policy": protected, "gate": self.latest_gate_report(), "repair": self.latest_repair_report()}
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        path = self.report_dir / f"central_diagnostic_{stamp}.json"
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        report["report_file"] = path.name
        return report

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any] | None:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None

    def latest_gate_report(self) -> dict[str, Any] | None:
        candidates = sorted(self.report_dir.glob("integrity_gate*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not candidates:
            default = self.report_dir / "integrity_gate.json"
            candidates = [default] if default.is_file() else []
        for path in candidates:
            data = self._read_json(path)
            if data is not None:
                data["report_file"] = path.name
                return data
        return None

    def latest_repair_report(self) -> dict[str, Any] | None:
        candidates = sorted(self.report_dir.glob("safe_repair*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        for path in candidates:
            data = self._read_json(path)
            if data is not None:
                data["report_file"] = path.name
                return data
        return None

    def architecture_inventory(self) -> dict[str, Any]:
        baseline_path = self.root / "integrity" / "baseline_v2_7_0.json"
        baseline = self._read_json(baseline_path) or {}
        modules = sorted([
            path.name for path in (self.root / "backend" / "modules").iterdir()
            if path.is_dir() and not path.name.startswith("__")
        ])
        return {
            "version": os.getenv("APP_VERSION", "2.7.1-universal-data-mapper"),
            "baseline_version": baseline.get("baseline_version"),
            "critical_modules": baseline.get("critical_modules", []),
            "modules_detected": modules,
            "roles": baseline.get("roles", []),
            "formats": baseline.get("format_capabilities", []),
            "database_contract": baseline.get("database_contract", {}),
        }

    def run_gate(self, update: Callable[..., None] | None = None, *, include_tests: bool = True) -> dict[str, Any]:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        report_path = self.report_dir / f"integrity_gate_{stamp}.json"
        command = [
            sys.executable,
            str(self.root / "backend" / "tools" / "integrity_gate.py"),
            "--root", str(self.root),
            "--report", str(report_path),
            "--skip-manifest",
        ]
        if not include_tests:
            command.append("--skip-tests")
        if update:
            update(progreso=10, etapa="Ejecutando gate de integridad", log=" ".join(command[:2]))
        run = subprocess.run(command, cwd=str(self.root), capture_output=True, text=True, check=False, timeout=900)
        if update:
            update(progreso=90, etapa="Leyendo resultados", log=(run.stdout + run.stderr)[-3000:])
        report = self._read_json(report_path) or {
            "status": "ERROR", "error": "El gate no produjo reporte.", "stdout": run.stdout[-2000:], "stderr": run.stderr[-2000:]
        }
        report["returncode"] = run.returncode
        return report

    def safe_repair(self, update: Callable[..., None] | None = None, *, apply: bool = False) -> dict[str, Any]:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        report_path = self.report_dir / f"safe_repair_{stamp}.json"
        command = [
            sys.executable,
            str(self.root / "backend" / "tools" / "safe_repair.py"),
            "--root", str(self.root),
            "--report", str(report_path),
        ]
        if apply:
            command.append("--apply")
        if update:
            update(progreso=20, etapa="Analizando reparaciones seguras")
        run = subprocess.run(command, cwd=str(self.root), capture_output=True, text=True, check=False, timeout=300)
        report = self._read_json(report_path) or {"status": "ERROR", "stderr": run.stderr[-2000:]}
        report["returncode"] = run.returncode
        return report
