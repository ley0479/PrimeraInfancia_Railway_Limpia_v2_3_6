from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any

COORDINATION_ROLES = {"SUPERADMIN", "GERENTE", "COORDINADOR"}
COMPLETED_STATES = {"APROBADA", "APROBADO", "CERRADA", "CERRADO", "ENTREGADA", "ENTREGADO", "REALIZADA", "REALIZADO", "NO_APLICA"}


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


def source_key(table: str, source_id: Any, extra: Any = None) -> str:
    raw = f"{normalize(table)}:{source_id}:{extra or ''}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def parse_date(value: Any) -> date | None:
    text = str(value or "").strip()[:10]
    try:
        return date.fromisoformat(text)
    except Exception:
        return None


def semaforo(fecha_limite: Any, estado: Any, bloqueada: Any = 0, today: date | None = None) -> dict[str, Any]:
    state = normalize(estado)
    current = today or date.today()
    due = parse_date(fecha_limite)
    if state in COMPLETED_STATES:
        return {"color": "VERDE", "nivel": "OK", "dias": None if not due else (due-current).days}
    if bool(bloqueada):
        return {"color": "ROJO", "nivel": "BLOQUEADA", "dias": None if not due else (due-current).days}
    if not due:
        return {"color": "AMARILLO", "nivel": "SIN_FECHA", "dias": None}
    days = (due-current).days
    if days < 0:
        return {"color": "ROJO", "nivel": "VENCIDA", "dias": days}
    if days <= 2:
        return {"color": "ROJO", "nivel": "CRITICA", "dias": days}
    if days <= 7:
        return {"color": "AMARILLO", "nivel": "PROXIMA", "dias": days}
    return {"color": "VERDE", "nivel": "EN_TIEMPO", "dias": days}


def file_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
