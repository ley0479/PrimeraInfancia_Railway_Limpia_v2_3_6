#!/usr/bin/env python3
"""Autorreparaciones explícitamente seguras.

Nunca modifica tablas, formatos oficiales, roles, permisos ni registros de
negocio. Por defecto solo informa; requiere --apply para ejecutar.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[2]))
    parser.add_argument("--policy", default="integrity/safe_autofix_policy.json")
    parser.add_argument("--report", default="data/integrity/safe_repair.json")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    policy = json.loads((root / args.policy).read_text(encoding="utf-8"))
    stale_seconds = int(policy.get("stale_temp_hours", 24)) * 3600
    max_log = int(policy.get("max_log_bytes", 20 * 1024 * 1024))
    now = time.time()
    candidates: list[dict] = []

    for directory in root.rglob("__pycache__"):
        if ".git" not in directory.parts:
            candidates.append({"action": "remove_python_bytecode", "path": str(directory), "kind": "directory"})
    for path in root.rglob("*.py[co]"):
        if ".git" not in path.parts:
            candidates.append({"action": "remove_python_bytecode", "path": str(path), "kind": "file"})

    for rel in (".runtime_windows", "data/tmp"):
        directory = root / rel
        if not directory.is_dir():
            continue
        for path in directory.rglob("*"):
            if path.is_file() and path.suffix.lower() in {".tmp", ".part", ".download"}:
                age = now - path.stat().st_mtime
                if age >= stale_seconds:
                    candidates.append({"action": "remove_stale_runtime_temp", "path": str(path), "kind": "file", "age_seconds": round(age)})

    runtime_dir = root / ".runtime_windows"
    if runtime_dir.is_dir():
        for path in runtime_dir.glob("*.pid"):
            if not path.is_file():
                continue
            age = now - path.stat().st_mtime
            raw = path.read_text(encoding="utf-8", errors="ignore").strip()
            try:
                pid = int(raw)
            except ValueError:
                pid = 0
            alive = False
            if pid > 0:
                try:
                    os.kill(pid, 0)
                    alive = True
                except PermissionError:
                    alive = True
                except (OSError, ProcessLookupError):
                    alive = False
            if not alive and age >= stale_seconds:
                candidates.append({
                    "action": "remove_stale_pid_files", "path": str(path), "kind": "file",
                    "pid": pid or None, "age_seconds": round(age),
                })

    for rel in ("data/logs", "logs_tunel"):
        directory = root / rel
        if not directory.is_dir():
            continue
        for path in directory.glob("*.log"):
            if path.is_file() and path.stat().st_size > max_log:
                candidates.append({"action": "rotate_oversized_logs", "path": str(path), "kind": "log", "size": path.stat().st_size})

    applied = []
    errors = []
    if args.apply:
        allowed = set(policy.get("allowed", []))
        for item in candidates:
            if item["action"] not in allowed:
                continue
            path = Path(item["path"])
            try:
                if item["action"] == "rotate_oversized_logs":
                    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    rotated = path.with_name(f"{path.stem}_{stamp}{path.suffix}")
                    path.replace(rotated)
                    path.touch()
                    item["rotated_to"] = str(rotated)
                elif path.is_dir():
                    shutil.rmtree(path)
                elif path.exists():
                    path.unlink()
                applied.append(item)
            except Exception as exc:
                errors.append({**item, "error": f"{type(exc).__name__}: {exc}"})

    report = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "mode": "APPLY" if args.apply else "PLAN",
        "candidates": candidates,
        "applied": applied,
        "errors": errors,
        "business_data_modified": False,
    }
    report_path = (root / args.report).resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
