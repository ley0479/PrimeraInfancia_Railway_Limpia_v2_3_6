#!/usr/bin/env python3
"""Emite la URL PostgreSQL resuelta para el proceso de arranque.

La salida se captura en una variable del shell y nunca se escribe en el log.
"""
from __future__ import annotations

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from config import resolve_postgresql_url_from_environment


if __name__ == "__main__":
    value = resolve_postgresql_url_from_environment()
    if not value.startswith("postgresql+psycopg://"):
        raise SystemExit(20)
    sys.stdout.write(value)
