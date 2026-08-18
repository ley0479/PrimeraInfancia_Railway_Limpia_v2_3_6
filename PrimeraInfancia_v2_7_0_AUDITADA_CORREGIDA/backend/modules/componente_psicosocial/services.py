from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

COORDINATION_ROLES = {"SUPERADMIN", "GERENTE", "COORDINADOR"}
READ_ROLES = COORDINATION_ROLES | {"PSICOSOCIAL"}
COMPLETED_STATES = {"CERRADO", "CERRADA", "VALIDADO", "VALIDADA", "COMPLETADO", "COMPLETADA", "APROBADO", "APROBADA"}


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def normalize(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip()).upper()


def unit_key(value: Any) -> str:
    return re.sub(r"[^A-Z0-9]+", "-", normalize(value)).strip("-")


def json_dump(value: Any) -> str:
    return json.dumps(value if value is not None else {}, ensure_ascii=False, sort_keys=True, default=str)


def parse_json(value: Any, fallback: Any = None) -> Any:
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value) if value not in (None, "") else fallback
    except Exception:
        return fallback


def file_sha256(path: str | Path) -> str:
    digest=hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024*1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
