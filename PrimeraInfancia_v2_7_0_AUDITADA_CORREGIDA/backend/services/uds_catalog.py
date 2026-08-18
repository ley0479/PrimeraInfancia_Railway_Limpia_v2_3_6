"""Catálogo central y sanitizado de Unidades de Servicio (UDS).

Evita que cada módulo mantenga sus propios alias. El catálogo contiene únicamente
nombres operativos de unidades y variantes de escritura; no contiene datos de
beneficiarios, personal, documentos, teléfonos ni credenciales.
"""
from __future__ import annotations

import json
import re
from modules.dbapi_compat import sqlite3
import unicodedata
from urllib.parse import unquote_plus
from functools import lru_cache
from datetime import datetime
from pathlib import Path
from typing import Any

BACKEND_DIR = Path(__file__).resolve().parents[1]
CATALOG_PATH = BACKEND_DIR / "config" / "uds_catalog.json"

INVALID_UNIT_VALUES = {
    "", "ACTIVO", "ACTIVA", "INACTIVO", "INACTIVA", "RETIRADO", "RETIRADA",
    "FALLECIDO", "FALLECIDA", "TRASLADADO", "TRASLADADA", "PENDIENTE",
    "UNIDAD DE SERVICIO", "TIPO DE UNIDAD", "SIN UNIDAD", "N/A", "NA", "NINGUNA",
}


def _text(value: Any) -> str:
    if value is None:
        return ""
    # Los nombres pueden llegar desde un segmento URL (por ejemplo,
    # ``GUADUALITO%20JAMPAPA``). Decodificar aquí mantiene una única regla de
    # comparación para consultas, formatos y rutas, sin fusionar nombres que
    # sean realmente distintos.
    text = unquote_plus(str(value)).strip().upper().replace("\t", " ")
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.replace("_", " ").replace("-", " ")
    text = re.sub(r"\s*#\s*", " # ", text)
    text = re.sub(r"[,.;:]+$", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _key(value: Any) -> str:
    text = _text(value)
    text = re.sub(r"[^A-Z0-9]+", " ", text)
    return " ".join(text.split())


@lru_cache(maxsize=1)
def load_catalog() -> dict[str, Any]:
    data = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    units = data.get("unidades")
    if not isinstance(units, list) or not units:
        raise RuntimeError("El catálogo UDS está vacío o es inválido.")
    names: set[str] = set()
    internal_codes: set[str] = set()
    for item in units:
        name = _text(item.get("nombre"))
        code = str(item.get("codigo_interno") or "").strip().upper()
        if not name or not code:
            raise RuntimeError("Cada UDS debe tener nombre y codigo_interno.")
        if name in names or code in internal_codes:
            raise RuntimeError(f"UDS o código duplicado en catálogo: {name} / {code}")
        names.add(name)
        internal_codes.add(code)
    return data


def catalog_version() -> str:
    return str(load_catalog().get("version") or "unknown")


def canonical_units() -> list[str]:
    return [_text(item["nombre"]) for item in load_catalog()["unidades"]]


def demo_to_canonical() -> dict[str, str]:
    """Mapeo determinista usado por la versión operativa v2.3.7.

    La limpieza sustituyó el catálogo original, ordenado alfabéticamente, por
    UNIDAD DEMO 01..32. Conservar este mapa permite actualizar instalaciones ya
    desplegadas sin tocar beneficiarios ni reconstruir la base desde cero.
    """
    return {f"UNIDAD DEMO {index:02d}": unit for index, unit in enumerate(canonical_units(), start=1)}


@lru_cache(maxsize=1)
def aliases_upper() -> dict[str, str]:
    result: dict[str, str] = {}
    for item in load_catalog()["unidades"]:
        canonical = _text(item["nombre"])
        variants = [canonical, f"UCA {canonical}", *(item.get("alias") or [])]
        for alias in list(variants):
            if not str(alias or "").upper().startswith("UCA "):
                variants.append(f"UCA {alias}")
        for alias in variants:
            if _key(alias):
                result[_key(alias)] = canonical
    for demo, canonical in demo_to_canonical().items():
        result[_key(demo)] = canonical
        result[_key(f"UCA {demo}")] = canonical
    return result


def aliases_lower() -> dict[str, str]:
    return {key.lower(): value for key, value in aliases_upper().items()}


def normalization_map() -> dict[str, str]:
    """Mapa compatible con módulos históricos que consultan claves en mayúscula."""
    result = aliases_upper().copy()
    for unit in canonical_units():
        result[unit] = unit
    return result


def normalize_unit(value: Any, *, preserve_unknown: bool = True) -> str:
    text = _text(value)
    if not text or text in INVALID_UNIT_VALUES:
        return ""
    key = _key(text)
    aliases = aliases_upper()
    if key in aliases:
        return aliases[key]
    if key.startswith("UCA "):
        stripped = key[4:].strip()
        if stripped in aliases:
            return aliases[stripped]
        return stripped if preserve_unknown else ""
    return text if preserve_unknown else ""


def is_known_unit(value: Any) -> bool:
    normalized = normalize_unit(value, preserve_unknown=False)
    return bool(normalized and normalized in set(canonical_units()))


def equivalent_values(value: Any) -> set[str]:
    canonical = normalize_unit(value)
    if not canonical:
        return set()
    equivalents = {canonical, f"UCA {canonical}"}
    for alias, target in aliases_upper().items():
        if target == canonical:
            equivalents.add(alias)
    return equivalents


def unit_record(value: Any) -> dict[str, Any] | None:
    canonical = normalize_unit(value, preserve_unknown=False)
    if not canonical:
        return None
    for item in load_catalog()["unidades"]:
        if _text(item.get("nombre")) == canonical:
            return dict(item)
    return None


def catalog_summary() -> dict[str, Any]:
    return {
        "version": catalog_version(),
        "total_unidades": len(canonical_units()),
        "total_aliases": len(aliases_upper()),
        "contiene_datos_personales": bool(load_catalog().get("contiene_datos_personales", False)),
    }


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", table):
        return set()
    exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    if not exists:
        return set()
    return {str(row[1]) for row in conn.execute(f'PRAGMA table_info("{table}")').fetchall()}


def _replace_json_value(value: Any, mapping: dict[str, str]) -> tuple[Any, bool]:
    changed = False
    if isinstance(value, str):
        normalized = _text(value)
        if normalized in mapping:
            return mapping[normalized], True
        if normalized.startswith("UCA ") and normalized[4:] in mapping:
            return mapping[normalized[4:]], True
        return value, False
    if isinstance(value, list):
        result = []
        for item in value:
            new_item, item_changed = _replace_json_value(item, mapping)
            changed = changed or item_changed
            result.append(new_item)
        return result, changed
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            new_item, item_changed = _replace_json_value(item, mapping)
            changed = changed or item_changed
            result[key] = new_item
        return result, changed
    return value, False


def migrate_demo_units_sqlite(database_path: str | Path) -> dict[str, Any]:
    """Convierte únicamente nombres UNIDAD DEMO xx al catálogo real.

    Es idempotente. No modifica nombres, documentos, teléfonos ni otros campos.
    """
    path = Path(database_path)
    if not path.exists():
        return {"updated_scalar_values": 0, "updated_json_values": 0, "tables": {}}
    mapping = demo_to_canonical()
    scalar_targets: dict[str, tuple[str, ...]] = {
        "beneficiarios": ("unidad",),
        "usuarios": ("unidad",),
        "unidades": ("nombre",),
        "movimientos": ("unidad_origen", "unidad_destino", "unidad"),
        "alertas": ("unidad",),
        "usuarios_app": ("unidad",),
        "talento_humano_personas": ("unidad",),
        "th_personas": ("unidad",),
        "planeaciones_pedagogicas": ("unidad",),
        "evidencias_pedagogicas": ("unidad",),
        "mp_pruebas": ("unidad",),
        "rpp_minutas_pruebas": ("unidad",),
    }
    json_targets: dict[str, tuple[str, ...]] = {
        "usuarios_app": ("unidades_json",),
        "talento_humano_personas": ("unidades_json",),
        "th_personas": ("unidades_json",),
        "coordinadores_unidades": ("unidades_json",),
    }
    total_scalar = 0
    total_json = 0
    table_report: dict[str, int] = {}
    conn = sqlite3.connect(str(path), timeout=30)
    try:
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("BEGIN IMMEDIATE")
        for table, columns in scalar_targets.items():
            available = _table_columns(conn, table)
            for column in columns:
                if column not in available:
                    continue
                count = 0
                for old, new in mapping.items():
                    cur = conn.execute(
                        f'UPDATE "{table}" SET "{column}"=? WHERE UPPER(TRIM(CAST("{column}" AS TEXT)))=?',
                        (new, old),
                    )
                    count += max(0, int(cur.rowcount or 0))
                    cur = conn.execute(
                        f'UPDATE "{table}" SET "{column}"=? WHERE UPPER(TRIM(CAST("{column}" AS TEXT)))=?',
                        (new, f"UCA {old}"),
                    )
                    count += max(0, int(cur.rowcount or 0))
                if count:
                    table_report[f"{table}.{column}"] = count
                    total_scalar += count
        for table, columns in json_targets.items():
            available = _table_columns(conn, table)
            id_column = "id" if "id" in available else None
            if not id_column:
                continue
            for column in columns:
                if column not in available:
                    continue
                rows = conn.execute(
                    f'SELECT "{id_column}", "{column}" FROM "{table}" WHERE "{column}" LIKE ?',
                    ("%UNIDAD DEMO%",),
                ).fetchall()
                count = 0
                for row_id, raw in rows:
                    try:
                        parsed = json.loads(raw or "null")
                    except Exception:
                        continue
                    replaced, changed = _replace_json_value(parsed, mapping)
                    if not changed:
                        continue
                    conn.execute(
                        f'UPDATE "{table}" SET "{column}"=? WHERE "{id_column}"=?',
                        (json.dumps(replaced, ensure_ascii=False), row_id),
                    )
                    count += 1
                if count:
                    table_report[f"{table}.{column}"] = count
                    total_json += count
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return {
        "updated_scalar_values": total_scalar,
        "updated_json_values": total_json,
        "tables": table_report,
        "catalog_version": catalog_version(),
    }


def ensure_catalog_units_sqlite(database_path: str | Path, fundacion_id: int = 1) -> dict[str, Any]:
    """Registra en `unidades` las UDS faltantes sin borrar ni sobrescribir datos."""
    path = Path(database_path)
    if not path.exists():
        return {"inserted": 0, "existing": 0}
    conn = sqlite3.connect(str(path), timeout=30)
    try:
        columns = _table_columns(conn, "unidades")
        if "nombre" not in columns:
            return {"inserted": 0, "existing": 0}
        if "fundacion_id" in columns:
            existing_rows = conn.execute(
                "SELECT nombre FROM unidades WHERE nombre IS NOT NULL AND COALESCE(fundacion_id, 1)=?",
                (int(fundacion_id or 1),),
            ).fetchall()
        else:
            existing_rows = conn.execute(
                "SELECT nombre FROM unidades WHERE nombre IS NOT NULL"
            ).fetchall()
        existing = {normalize_unit(row[0]) for row in existing_rows}
        inserted = 0
        for unit in canonical_units():
            if unit in existing:
                continue
            fields = ["nombre"]
            values: list[Any] = [unit]
            if "fundacion_id" in columns:
                fields.append("fundacion_id")
                values.append(int(fundacion_id or 1))
            if "total_usuarios" in columns:
                fields.append("total_usuarios")
                values.append(0)
            if "alerta_cobertura" in columns:
                fields.append("alerta_cobertura")
                values.append(1)
            timestamp = datetime.now().isoformat(timespec="seconds")
            if "ultima_actualizacion" in columns:
                fields.append("ultima_actualizacion")
                values.append(timestamp)
            if "fecha_actualizacion" in columns:
                fields.append("fecha_actualizacion")
                values.append(timestamp)
            quoted = ",".join(f'"{field}"' for field in fields)
            placeholders = ",".join("?" for _ in fields)
            conn.execute(f'INSERT INTO unidades ({quoted}) VALUES ({placeholders})', values)
            inserted += 1
        conn.commit()
        return {
            "inserted": inserted,
            "creadas": inserted,
            "existing": len(existing),
            "existentes": len(existing),
            "catalog_total": len(canonical_units()),
        }
    finally:
        conn.close()
