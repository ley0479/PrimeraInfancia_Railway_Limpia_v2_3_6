from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

COMPLETED_STATES = {"CERRADO", "CERRADA", "CUMPLIDO", "CUMPLIDA", "APROBADO", "APROBADA", "VERIFICADO", "VERIFICADA"}


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def normalize_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip()).upper()


def safe_state(value: Any, default: str = "PENDIENTE") -> str:
    return normalize_text(value).replace(" ", "_") or default


def unit_key(value: Any) -> str:
    return re.sub(r"[^A-Z0-9]+", "_", normalize_text(value)).strip("_")


def json_dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def parse_json(value: Any, default: Any) -> Any:
    if value in (None, ""):
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(str(value))
    except (ValueError, TypeError):
        return default


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
