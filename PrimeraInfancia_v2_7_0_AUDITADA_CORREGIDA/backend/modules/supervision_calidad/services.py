"""Reglas y utilidades del Centro de Supervisión y Calidad."""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import date, datetime
from pathlib import Path
from typing import Any

SUPERVISION_STATES = {
    "BORRADOR", "PROGRAMADA", "EN_EJECUCION", "PENDIENTE_REVISION",
    "DEVUELTA", "APROBADA", "CERRADA", "CANCELADA",
}
VERIFICATION_RESULTS = {"PENDIENTE", "CUMPLE", "PARCIAL", "NO_CUMPLE", "NO_APLICA"}
FINDING_STATES = {"ABIERTO", "EN_PLAN", "EN_SEGUIMIENTO", "RESUELTO_PENDIENTE_VALIDACION", "CERRADO", "DESCARTADO"}
PLAN_STATES = {"BORRADOR", "PENDIENTE_APROBACION", "APROBADO", "EN_EJECUCION", "PENDIENTE_VALIDACION", "CERRADO", "CANCELADO"}
ACTION_STATES = {"PENDIENTE", "EN_EJECUCION", "PENDIENTE_VALIDACION", "COMPLETADA", "CANCELADA"}
RISK_LEVELS = {"BAJO", "MEDIO", "ALTO", "CRITICO"}


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def normalize(value: Any) -> str:
    raw = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", raw).strip().upper()


def unit_key(value: Any) -> str:
    raw = normalize(value)
    return re.sub(r"[^A-Z0-9]+", "_", raw).strip("_") or "SIN_UNIDAD"


def safe_state(value: Any, allowed: set[str], default: str) -> str:
    state = normalize(value).replace(" ", "_")
    return state if state in allowed else default


def json_dump(value: Any) -> str:
    return json.dumps(value if value is not None else {}, ensure_ascii=False, default=str, sort_keys=True)


def parse_json(value: Any, default: Any = None) -> Any:
    if value in (None, ""):
        return {} if default is None else default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except Exception:
        return {} if default is None else default


def file_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def valid_date(value: Any) -> str | None:
    raw = str(value or "").strip()[:10]
    if not raw:
        return None
    try:
        return date.fromisoformat(raw).isoformat()
    except ValueError:
        return None


def finding_code(supervision_id: int | None, sequence: int) -> str:
    prefix = f"SUP{int(supervision_id or 0):05d}" if supervision_id else "MANUAL"
    return f"H-{prefix}-{int(sequence):04d}"


def plan_code(hallazgo_id: int | None, sequence: int) -> str:
    prefix = f"H{int(hallazgo_id or 0):05d}" if hallazgo_id else "GENERAL"
    return f"PM-{prefix}-{int(sequence):04d}"


def compliance(rows: list[dict[str, Any]]) -> float:
    weights = {"CUMPLE": 1.0, "PARCIAL": 0.5, "NO_APLICA": 1.0, "NO_CUMPLE": 0.0, "PENDIENTE": 0.0}
    evaluable = [row for row in rows if row.get("resultado") != "NO_APLICA"]
    if not evaluable:
        return 0.0
    return round(sum(weights.get(str(row.get("resultado") or "PENDIENTE"), 0.0) for row in evaluable) * 100 / len(evaluable), 2)


def is_overdue(value: Any, state: str | None = None) -> bool:
    if normalize(state) in {"CERRADO", "CERRADA", "COMPLETADA", "CANCELADO", "CANCELADA"}:
        return False
    raw = valid_date(value)
    return bool(raw and raw < date.today().isoformat())
