from __future__ import annotations

from collections import defaultdict
from typing import Any

from .catalog import CANONICAL_FIELDS, NEGATIVE_TERMS
from .models import CandidateScore, ColumnDescriptor, MappingDecision
from .normalizers import normalize_header, normalize_text
from .profiler import profile_values


def _confidence(score: float, margin: float) -> str:
    if score >= 85 and margin >= 15: return "HIGH"
    if score >= 60: return "MEDIUM"
    return "LOW"


def score_column(field: str, column: ColumnDescriptor, values: list[Any], confirmed: bool = False) -> CandidateScore:
    header = column.normalized_header
    tokens = header.split()
    aliases = [normalize_header(a) for a in CANONICAL_FIELDS[field]["aliases"]]
    reasons: list[str] = []
    score = 0.0
    if header == aliases[0]: score += 100; reasons.append("exact_primary_alias")
    elif header in aliases: score += 80; reasons.append("exact_secondary_alias")
    else:
        best = max((len(set(tokens) & set(alias.split())) / max(1, len(set(alias.split()))) for alias in aliases), default=0)
        if best >= .75: score += 40; reasons.append("high_token_coverage")
        elif best >= .5: score += 20; reasons.append("partial_token_coverage")
    if field == "unidad.nombre":
        if "nombre" in tokens: score += 20; reasons.append("contains_name")
        if {"unidad", "servicio"}.issubset(tokens): score += 35; reasons.append("contains_unit_service")
    if field == "unidad.codigo":
        if "codigo" in tokens: score += 20; reasons.append("contains_code")
        if {"unidad", "servicio"}.issubset(tokens): score += 35; reasons.append("contains_unit_service")
        if not ({"codigo", "id", "identificador"} & set(tokens)) and header not in aliases:
            score -= 80; reasons.append("missing_code_semantics")
    for term, penalty in NEGATIVE_TERMS.get(field, {}).items():
        if set(term.split()).issubset(set(tokens)):
            score += penalty; reasons.append(f"negative:{term}")
    profile = profile_values(values)
    if field.endswith(".codigo") and profile["non_empty"] and profile["numeric_ratio"] + profile["alphanumeric_ratio"] >= .7:
        score += 25; reasons.append("code_value_profile")
    if field.endswith(".nombre") and profile["non_empty"] and profile["alpha_ratio"] + profile["alphanumeric_ratio"] >= .5:
        score += 25; reasons.append("name_value_profile")
    if confirmed: score += 200; reasons.append("administrator_confirmed")
    return CandidateScore(field, column.id, column.original_header, score, "LOW", reasons)


def map_columns(columns: list[ColumnDescriptor], rows: list[list[Any]], confirmed: dict[str, str] | None = None) -> dict[str, MappingDecision]:
    confirmed = confirmed or {}
    values = {col.id: [row[col.index] if col.index < len(row) else None for row in rows] for col in columns}
    result: dict[str, MappingDecision] = {}
    for field in CANONICAL_FIELDS:
        ranked = sorted((score_column(field, col, values[col.id], confirmed.get(field) == col.id) for col in columns), key=lambda item: item.score, reverse=True)
        top = ranked[0] if ranked else None
        margin = (top.score - ranked[1].score) if top and len(ranked) > 1 else (top.score if top else 0)
        if top: top.confidence = _confidence(top.score, margin)
        status = "AUTO" if top and top.confidence == "HIGH" else "REQUIRES_CONFIRMATION"
        if not top or top.score < 60: status = "NOT_DETECTED"
        result[field] = MappingDecision(field, top if top and top.score >= 60 else None, ranked[1:4], [r for r in ranked if any(x.startswith("negative:") for x in r.reasons)][:5], status)
    _score_unit_pair(result, columns, values)
    return result


def _score_unit_pair(result: dict[str, MappingDecision], columns: list[ColumnDescriptor], values: dict[str, list[Any]]) -> None:
    codes = result["unidad.codigo"].selected
    names = result["unidad.nombre"].selected
    if not codes or not names or codes.column_id == names.column_id: return
    pairs: dict[str, set[str]] = defaultdict(set)
    reverse: dict[str, set[str]] = defaultdict(set)
    for code, name in zip(values[codes.column_id], values[names.column_id]):
        c, n = normalize_text(code), normalize_text(name)
        if c and n: pairs[c].add(n); reverse[n.casefold()].add(c)
    stable = bool(pairs) and all(len(v) == 1 for v in pairs.values()) and all(len(v) == 1 for v in reverse.values())
    if stable:
        for candidate in (codes, names): candidate.score += 30; candidate.reasons.append("stable_unit_code_name_pair")
    positions = {c.id: c.index for c in columns}
    if abs(positions[codes.column_id] - positions[names.column_id]) <= 2:
        for candidate in (codes, names): candidate.score += 5; candidate.reasons.append("adjacent_unit_pair")
    for field, candidate in (("unidad.codigo", codes), ("unidad.nombre", names)):
        decision = result[field]
        second = decision.alternatives[0].score if decision.alternatives else 0
        candidate.confidence = _confidence(candidate.score, candidate.score - second)
        decision.status = "AUTO" if candidate.confidence == "HIGH" else "REQUIRES_CONFIRMATION"
