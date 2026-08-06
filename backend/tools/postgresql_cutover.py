#!/usr/bin/env python3
"""Orquesta el corte verificable SQLite -> PostgreSQL sin tocar el origen.

Ejecuta preflight, auditoría SQL runtime, migración/validación y gate rápido. La
URL solo se guarda en un archivo local cuando todas las fases terminan en PASS
y el operador lo solicita explícitamente.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from config import normalize_database_url  # noqa: E402
from tools.migrate_sqlite_to_postgresql import masked_url, sha256_file  # noqa: E402


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def run_step(name: str, command: list[str], *, cwd: Path, env: dict[str, str] | None = None) -> dict[str, Any]:
    started = datetime.now(timezone.utc)
    completed = subprocess.run(
        command,
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=1800,
    )
    return {
        "name": name,
        "status": "PASS" if completed.returncode == 0 else "FAIL",
        "returncode": completed.returncode,
        "started_at": started.isoformat(timespec="seconds"),
        "finished_at": now(),
        "stdout_tail": completed.stdout[-4000:],
        "stderr_tail": completed.stderr[-4000:],
    }


def secure_write(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(value.strip() + "\n", encoding="utf-8")
    try:
        temp.chmod(0o600)
    except OSError:
        pass
    temp.replace(path)
    try:
        path.chmod(0o600)
    except OSError:
        pass


def main() -> int:
    parser = argparse.ArgumentParser(description="Corte completo y verificable a PostgreSQL")
    parser.add_argument("--sqlite", required=True)
    parser.add_argument("--postgres", default=os.getenv("DATABASE_URL"))
    parser.add_argument("--schema", default="public")
    parser.add_argument("--report-dir", default="data/migration_reports/cutover")
    parser.add_argument("--activate-env-file", help="Guardar DATABASE_URL únicamente después de PASS")
    parser.add_argument("--verify-existing", action="store_true", help="No copiar; verificar una migración ya realizada")
    parser.add_argument("--truncate-target", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-gate", action="store_true")
    args = parser.parse_args()

    source = Path(args.sqlite).expanduser().resolve()
    if not source.is_file():
        raise SystemExit(f"No existe SQLite: {source}")
    if not args.postgres:
        raise SystemExit("Falta --postgres o DATABASE_URL.")
    url = normalize_database_url(args.postgres)
    if not url.startswith("postgresql+psycopg://"):
        raise SystemExit("El destino debe ser PostgreSQL con psycopg.")

    report_dir = Path(args.report_dir).expanduser()
    if not report_dir.is_absolute():
        report_dir = (ROOT / report_dir).resolve()
    report_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    manifest_path = report_dir / f"cutover_{stamp}.json"
    preflight_path = report_dir / f"preflight_{stamp}.json"
    runtime_path = report_dir / f"runtime_sql_{stamp}.json"
    migration_path = report_dir / f"migration_{stamp}.json"
    verify_path = report_dir / f"verification_{stamp}.json"
    gate_path = report_dir / f"integrity_gate_{stamp}.json"

    manifest: dict[str, Any] = {
        "schema_version": 1,
        "started_at": now(),
        "status": "RUNNING",
        "mode": "VERIFY_EXISTING" if args.verify_existing else ("DRY_RUN" if args.dry_run else "MIGRATE"),
        "source": str(source),
        "source_sha256": sha256_file(source),
        "target": masked_url(url),
        "schema": args.schema,
        "activation_requested": bool(args.activate_env_file),
        "activation_completed": False,
        "steps": [],
        "reports": {},
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    commands: list[tuple[str, list[str], Path]] = [
        (
            "postgresql_preflight",
            [sys.executable, str(BACKEND / "tools/postgresql_preflight.py"), "--postgres", url, "--schema", args.schema, "--report", str(preflight_path)],
            ROOT,
        ),
        (
            "postgresql_runtime_audit",
            [sys.executable, str(BACKEND / "tools/postgresql_runtime_audit.py"), "--root", str(ROOT), "--report", str(runtime_path)],
            ROOT,
        ),
    ]

    if args.verify_existing:
        commands.append((
            "verify_existing",
            [sys.executable, str(BACKEND / "tools/verify_sqlite_postgresql.py"), "--sqlite", str(source), "--postgres", url, "--schema", args.schema, "--report", str(verify_path)],
            ROOT,
        ))
    else:
        migrate_command = [
            sys.executable,
            str(BACKEND / "tools/migrate_sqlite_to_postgresql.py"),
            "--sqlite", str(source),
            "--postgres", url,
            "--schema", args.schema,
            "--report", str(migration_path),
        ]
        if args.truncate_target:
            migrate_command.append("--truncate-target")
        if args.dry_run:
            migrate_command.append("--dry-run")
        commands.append(("migrate", migrate_command, ROOT))
        if not args.dry_run:
            commands.append((
                "verify_after_migration",
                [sys.executable, str(BACKEND / "tools/verify_sqlite_postgresql.py"), "--sqlite", str(source), "--postgres", url, "--schema", args.schema, "--report", str(verify_path)],
                ROOT,
            ))

    if not args.skip_gate:
        commands.append((
            "integrity_gate",
            [
                sys.executable,
                str(BACKEND / "tools/integrity_gate.py"),
                "--root", str(ROOT),
                "--report", str(gate_path),
                "--skip-manifest",
            ],
            ROOT,
        ))

    try:
        for name, command, cwd in commands:
            result = run_step(name, command, cwd=cwd)
            manifest["steps"].append(result)
            manifest["reports"][name] = {
                "preflight": str(preflight_path),
                "postgresql_runtime_audit": str(runtime_path),
                "migrate": str(migration_path),
                "verify_existing": str(verify_path),
                "verify_after_migration": str(verify_path),
                "integrity_gate": str(gate_path),
            }.get(name)
            manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
            if result["status"] != "PASS":
                raise RuntimeError(f"Falló {name}; revise {manifest_path}")

        if args.activate_env_file and not args.dry_run:
            activation = Path(args.activate_env_file).expanduser().resolve()
            secure_write(activation, url)
            manifest["activation_completed"] = True
            manifest["activation_file"] = str(activation)

        manifest["status"] = "READY" if not args.dry_run else "DRY_RUN_OK"
        manifest["finished_at"] = now()
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({
            "status": manifest["status"],
            "target": manifest["target"],
            "manifest": str(manifest_path),
            "activation_completed": manifest["activation_completed"],
        }, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        manifest["status"] = "BLOCKED"
        manifest["finished_at"] = now()
        manifest["error"] = f"{type(exc).__name__}: {exc}"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        print(manifest["error"], file=sys.stderr)
        print(f"Manifest: {manifest_path}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
