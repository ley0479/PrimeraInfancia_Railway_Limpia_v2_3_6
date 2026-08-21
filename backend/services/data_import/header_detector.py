from __future__ import annotations

from typing import Any

from .catalog import CANONICAL_FIELDS
from .normalizers import normalize_header, normalize_text

KNOWN = {normalize_header(a) for cfg in CANONICAL_FIELDS.values() for a in cfg["aliases"]}


def detect_header(rows: list[list[Any]], max_rows: int = 50) -> tuple[int, int, list[str]]:
    """Detecta fila y profundidad (1/2) mediante densidad, aliases y datos inferiores."""
    best = (-10_000.0, 0, 1, [])
    for idx, row in enumerate(rows[:max_rows]):
        cells = [normalize_text(v) for v in row]
        non_empty = [v for v in cells if v]
        if not non_empty:
            continue
        normalized = [normalize_header(v) for v in cells]
        known = sum(1 for value in normalized if value in KNOWN)
        textual = sum(any(ch.isalpha() for ch in value) for value in non_empty)
        unique = len(set(normalized) - {""})
        below = rows[idx + 1:idx + 6]
        density = sum(bool(normalize_text(v)) for r in below for v in r) / max(1, len(below) * len(row))
        score = len(non_empty) * 2 + known * 30 + textual + unique + density * 20
        depth, headers = 1, cells
        if idx + 1 < len(rows):
            child = [normalize_text(v) for v in rows[idx + 1]]
            parent_terms = sum("unidad" in normalize_header(v) or "participante" in normalize_header(v) for v in cells)
            child_terms = sum(normalize_header(v) in {"codigo", "nombre", "documento", "fecha"} for v in child)
            if parent_terms and child_terms:
                depth = 2
                headers = [normalize_text(f"{cells[i] if i < len(cells) else ''} | {child[i] if i < len(child) else ''}") for i in range(max(len(cells), len(child)))]
                score += 20
        if score > best[0]:
            best = (score, idx, depth, headers)
    return best[1], best[2], best[3]
