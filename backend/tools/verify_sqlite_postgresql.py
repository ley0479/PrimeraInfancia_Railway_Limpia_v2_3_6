#!/usr/bin/env python3
"""Verifica una migración existente sin copiar ni modificar datos."""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Verificar SQLite contra PostgreSQL")
    parser.add_argument("--sqlite", required=True)
    parser.add_argument("--postgres", default=os.getenv("DATABASE_URL"))
    parser.add_argument("--schema", default="public")
    parser.add_argument("--report", default="data/migration_reports/verify_sqlite_postgresql.json")
    parser.add_argument("--no-fingerprints", action="store_true")
    args = parser.parse_args()
    if not args.postgres:
        raise SystemExit("Falta --postgres o DATABASE_URL.")

    script = Path(__file__).with_name("migrate_sqlite_to_postgresql.py")
    command = [
        sys.executable,
        str(script),
        "--sqlite", args.sqlite,
        "--postgres", args.postgres,
        "--schema", args.schema,
        "--verify-only",
        "--report", args.report,
    ]
    if args.no_fingerprints:
        command.append("--no-fingerprints")
    return subprocess.call(command)


if __name__ == "__main__":
    raise SystemExit(main())
