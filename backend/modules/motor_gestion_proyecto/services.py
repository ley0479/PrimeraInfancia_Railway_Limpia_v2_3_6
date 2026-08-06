"""Reglas puras del Motor Inteligente de Gestión del Proyecto."""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable

OPEN_STATES = {
    "", "PENDIENTE", "PROGRAMADA", "EN_PROCESO", "EN_EJECUCION",
    "PENDIENTE_EVIDENCIA", "PENDIENTE_REVISION", "DEVUELTA", "VENCIDA",
    "BORRADOR", "ACTIVA", "ABIERTO", "ABIERTA",
}
COMPLETED_STATES = {
    "COMPLETADA", "COMPLETADO", "ENTREGADA", "ENTREGADO", "APROBADA",
    "APROBADO", "CERRADA", "CERRADO", "NO_APLICA", "GENERADO", "VALIDADO",
}
REVIEW_STATES = {"PENDIENTE_REVISION", "DEVUELTA", "APROBADA", "CERRADA"}


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def normalize_text(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or "").strip())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"[^A-Za-z0-9]+", "_", text).strip("_").upper()


def state(value: Any) -> str:
    return normalize_text(value) or "PENDIENTE"


def json_dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)


def parse_json(value: Any, fallback: Any = None) -> Any:
    if value in (None, ""):
        return fallback
    if isinstance(value, (dict, list, tuple, int, float, bool)):
        return value
    try:
        return json.loads(str(value))
    except Exception:
        return fallback


def valid_date(value: Any) -> str | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    raw = raw[:10]
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def unit_key(value: Any) -> str:
    normalized = normalize_text(value)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:24] if normalized else ""


def source_key(table: str, source_id: Any, extra: Any = None) -> str:
    raw = f"{table}|{source_id or 0}|{extra or ''}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:40]


def days_remaining(due_date: Any, today: date | None = None) -> int | None:
    parsed = valid_date(due_date)
    if not parsed:
        return None
    reference = today or date.today()
    return (datetime.strptime(parsed, "%Y-%m-%d").date() - reference).days


def is_complete(value: Any) -> bool:
    return state(value) in COMPLETED_STATES


def calculate_priority(task: dict[str, Any], dependency_open: bool = False, today: date | None = None) -> dict[str, Any]:
    current_state = state(task.get("estado"))
    if current_state in COMPLETED_STATES:
        return {"puntaje": 0, "prioridad": "BAJA", "vencida": False, "dias_restantes": days_remaining(task.get("fecha_limite"), today), "bloqueada": False}

    score = 5
    due = days_remaining(task.get("fecha_limite"), today)
    overdue = due is not None and due < 0
    if overdue:
        score += 75
    elif due is not None and due <= 2:
        score += 45
    elif due is not None and due <= 7:
        score += 25
    elif due is not None and due <= 15:
        score += 10

    if bool(task.get("requiere_evidencia")) and int(task.get("evidencias_total") or 0) <= 0:
        score += 20
    if current_state in {"DEVUELTA", "RECHAZADA"}:
        score += 35
    if dependency_open:
        score += 25
    if normalize_text(task.get("prioridad")) in {"CRITICA", "URGENTE"}:
        score += 20
    elif normalize_text(task.get("prioridad")) == "ALTA":
        score += 10

    score = min(100, score)
    priority = "CRITICA" if score >= 80 else ("ALTA" if score >= 55 else ("MEDIA" if score >= 25 else "BAJA"))
    return {"puntaje": score, "prioridad": priority, "vencida": overdue, "dias_restantes": due, "bloqueada": bool(dependency_open)}


def compliance_percentage(tasks: Iterable[dict[str, Any]]) -> float:
    rows = list(tasks)
    if not rows:
        return 0.0
    completed = sum(1 for item in rows if is_complete(item.get("estado")))
    return round(completed / len(rows) * 100.0, 2)


def file_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_period(value: Any) -> str:
    raw = str(value or "").strip()
    if re.fullmatch(r"\d{4}-\d{2}", raw):
        month = int(raw[-2:])
        if 1 <= month <= 12:
            return raw
    return date.today().strftime("%Y-%m")


def task_role_can_edit(task: dict[str, Any], user: dict[str, Any]) -> bool:
    role = normalize_text(user.get("rol"))
    if role in {"SUPERADMIN", "GERENTE", "COORDINADOR", "AUXILIAR_ADMINISTRATIVO"}:
        return True
    user_id = int(user.get("id") or 0)
    responsible_id = int(task.get("responsable_id") or 0)
    if user_id and responsible_id:
        return user_id == responsible_id
    responsible = normalize_text(task.get("responsable_nombre"))
    username = normalize_text(user.get("username") or user.get("nombre") or user.get("email"))
    return bool(responsible and username and (responsible == username or username in responsible))
