from __future__ import annotations

import math
import re
import unicodedata
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""
    text = unicodedata.normalize("NFKC", str(value)).replace("\u00a0", " ")
    return re.sub(r"\s+", " ", text).strip()


def normalize_header(value: Any) -> str:
    text = normalize_text(value).lower()
    text = "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def normalize_identifier(value: Any) -> str:
    return re.sub(r"\s+", "", normalize_text(value)).upper()


def normalize_unit_code(value: Any) -> str:
    """Conserva códigos como texto y solo retira un .0 artificial seguro."""
    text = normalize_text(value)
    if re.fullmatch(r"[+-]?\d+\.0", text):
        text = text[:-2]
    if re.search(r"[eE][+-]?\d+$", text):
        try:
            number = Decimal(text)
            exact = format(number, "f")
            if "." in exact:
                exact = exact.rstrip("0").rstrip(".")
            text = exact
        except InvalidOperation:
            pass
    return text


def normalize_document_number(value: Any) -> str:
    return re.sub(r"[^A-Za-z0-9]", "", normalize_unit_code(value)).upper()


def normalize_person_name(value: Any) -> str:
    return normalize_text(value).upper()


def normalize_unit_name(value: Any) -> str:
    return normalize_text(value)


def normalize_date(value: Any) -> str | None:
    if isinstance(value, (date, datetime)):
        return value.date().isoformat() if isinstance(value, datetime) else value.isoformat()
    text = normalize_text(value)
    return text or None


def normalize_boolean(value: Any) -> bool | None:
    text = normalize_header(value)
    if text in {"si", "s", "true", "1", "x", "activo"}:
        return True
    if text in {"no", "n", "false", "0", "inactivo"}:
        return False
    return None


def normalize_decimal(value: Any) -> Decimal | None:
    text = normalize_text(value).replace(",", ".")
    try:
        return Decimal(text) if text else None
    except InvalidOperation:
        return None
