from __future__ import annotations

from collections import Counter
from typing import Any

from .normalizers import normalize_text


def profile_values(values: list[Any], sample_limit: int = 500) -> dict[str, Any]:
    raw = values[:sample_limit]
    clean = [normalize_text(v) for v in raw]
    present = [v for v in clean if v]
    counts = Counter(present)
    numeric = sum(v.replace(".", "", 1).isdigit() for v in present)
    alpha = sum(v.replace(" ", "").isalpha() for v in present)
    scientific = sum("e+" in v.lower() or "e-" in v.lower() for v in present)
    return {
        "rows": len(raw), "non_empty": len(present), "empty": len(raw) - len(present),
        "unique": len(counts), "uniqueness": round(len(counts) / len(present), 4) if present else 0,
        "min_length": min(map(len, present)) if present else 0, "max_length": max(map(len, present)) if present else 0,
        "examples": list(dict.fromkeys(present))[:5], "frequent": counts.most_common(5),
        "numeric_ratio": round(numeric / len(present), 4) if present else 0,
        "alpha_ratio": round(alpha / len(present), 4) if present else 0,
        "alphanumeric_ratio": round((len(present) - numeric - alpha) / len(present), 4) if present else 0,
        "scientific_notation": scientific,
    }
