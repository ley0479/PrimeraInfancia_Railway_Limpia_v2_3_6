from __future__ import annotations

SPECIAL_STATES = {"PENDIENTE_DE_DILIGENCIAMIENTO", "NO_SE_PRESENTARON_NOVEDADES", "NO_APLICA", "OTRO"}


def validate_special_state(state: str | None, justification: str | None = None) -> None:
    if state and state not in SPECIAL_STATES:
        raise ValueError("Estado especial no permitido.")
    if state == "NO_APLICA" and not str(justification or "").strip():
        raise ValueError("NO APLICA requiere justificación.")


def find_contradictions(selections: list[dict]) -> list[dict]:
    selected = {str(item.get("codigo") or "").upper() for item in selections}
    issues = []
    rules = {
        "SIN_DIFICULTADES": {"BAJA_PARTICIPACION", "ACTIVIDAD_NO_REALIZADA", "REPROGRAMACION"},
        "OBJETIVO_COMPLETO": {"ACTIVIDAD_NO_REALIZADA", "SIN_LOGROS_COMPROBABLES"},
    }
    for source, incompatible in rules.items():
        conflict = sorted(selected.intersection(incompatible))
        if source in selected and conflict:
            issues.append({"codigo": "RESPUESTAS_CONTRADICTORIAS", "selecciones": [source, *conflict]})
    return issues
