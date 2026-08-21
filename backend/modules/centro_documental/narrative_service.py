from __future__ import annotations

from .validators import find_contradictions


LABELS = {
    "PARTICIPACION": "Durante el encuentro,",
    "OBSERVACION": "Como observación,",
    "LOGRO": "En relación con los logros,",
    "DIFICULTAD": "Como dificultad,",
    "COMPROMISO": "Se acordó como compromiso",
    "RECOMENDACION": "Se recomienda",
}


def assemble_narrative(selections: list[dict]) -> dict:
    contradictions = find_contradictions(selections)
    if contradictions:
        raise ValueError("Hay respuestas contradictorias. Revise la selección antes de continuar.")
    grouped: dict[str, list[str]] = {}
    for item in selections:
        text = " ".join(str(item.get("texto") or item.get("texto_personalizado") or "").split())
        if text:
            grouped.setdefault(str(item.get("categoria") or "OBSERVACION").upper(), []).append(text.rstrip("."))
    paragraphs = []
    for category in ("PARTICIPACION", "OBSERVACION", "LOGRO", "DIFICULTAD", "COMPROMISO", "RECOMENDACION"):
        values = grouped.get(category, [])
        if values:
            paragraphs.append(f"{LABELS[category]} " + "; ".join(values) + ".")
    return {"estado": "BORRADOR_GENERADO", "editable": True, "texto": " ".join(paragraphs)}
