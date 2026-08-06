"""Servicios del Motor de Integridad, Supervisión y Estabilidad."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


class IntegrityStabilityService:
    def __init__(self, project_root: str, data_dir: str) -> None:
        self.root = Path(project_root).resolve()
        self.data_dir = Path(data_dir).resolve()
        self.report_dir = self.data_dir / "integrity"
        self.report_dir.mkdir(parents=True, exist_ok=True)

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
            "version": os.getenv("APP_VERSION", "2.7.0-centro-planeacion-psicosocial"),
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
