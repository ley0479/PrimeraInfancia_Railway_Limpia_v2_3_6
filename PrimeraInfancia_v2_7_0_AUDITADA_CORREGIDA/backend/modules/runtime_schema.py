"""Control explícito de migraciones y DDL en tiempo de ejecución.

Las migraciones se habilitan únicamente durante ``init_hosting.py``. Los
workers y las peticiones normales no deben crear ni alterar tablas.
"""
from __future__ import annotations

import os

_TRUE_VALUES = {"1", "true", "yes", "si", "sí", "on"}


def env_flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return bool(default)
    return str(raw).strip().lower() in _TRUE_VALUES


def migration_mode() -> bool:
    """Indica que el proceso actual es el migrador controlado de arranque."""
    return env_flag("APP_SCHEMA_MIGRATION_MODE", False)


def runtime_schema_ddl_disabled() -> bool:
    """Bloquea DDL durante imports de workers y peticiones HTTP."""
    return env_flag("SKIP_RUNTIME_SCHEMA_DDL", False) and not migration_mode()


def schema_ddl_enabled() -> bool:
    return not runtime_schema_ddl_disabled()
