from __future__ import annotations

import hashlib
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .adapters import CsvAdapter, DocumentExtractionAdapter, ExcelAdapter, JsonAdapter, RelationalDatabaseAdapter
from .catalog import CATALOG_VERSION, FORMAT_REQUIREMENTS
from .mapper import map_columns
from .normalizers import normalize_document_number, normalize_person_name, normalize_text, normalize_unit_code


class UniversalMappingService:
    def __init__(self, adapters=None):
        self.adapters = adapters or [ExcelAdapter(), CsvAdapter(), JsonAdapter(), RelationalDatabaseAdapter(), DocumentExtractionAdapter()]

    def adapter_for(self, source: str):
        adapter = next((item for item in self.adapters if item.can_handle(source)), None)
        if not adapter: raise ValueError("Tipo de fuente no soportado")
        return adapter

    def analyze(self, source: str, table_id: str | None = None, confirmed: dict[str, str] | None = None) -> dict[str, Any]:
        adapter = self.adapter_for(source)
        inspection = adapter.inspect(source)
        candidates = sorted((table for table in inspection.tables if not table.empty), key=lambda item: item.score, reverse=True)
        if not candidates: raise ValueError("La fuente no contiene tablas con datos")
        selected = table_id or candidates[0].id
        preview = adapter.preview(source, selected, 500)
        mapping = map_columns(preview.columns, preview.rows, confirmed)
        selected_fields = {field for field, decision in mapping.items() if decision.selected}
        if "participante.nombre_completo" not in selected_fields and (
            "participante.primer_nombre" in selected_fields and "participante.primer_apellido" in selected_fields
        ):
            selected_fields.add("participante.nombre_completo")
        compatibility = {}
        for name, requirements in FORMAT_REQUIREMENTS.items():
            required = requirements["required"]
            present = [field for field in required if field in selected_fields]
            compatibility[name] = {"percent": round(len(present) / len(required) * 100), "missing": [field for field in required if field not in selected_fields]}
        units = self.detect_units(preview, mapping)
        return {
            "catalog_version": CATALOG_VERSION,
            "inspection": asdict(inspection), "selected_table": selected,
            "preview": asdict(preview), "mapping": {field: decision.as_dict() for field, decision in mapping.items()},
            "units": units, "format_compatibility": compatibility,
            "structure_fingerprint": adapter.get_source_fingerprint(source, selected),
            "requires_confirmation": any(decision.status != "AUTO" for field, decision in mapping.items() if field in {"unidad.codigo", "unidad.nombre"}),
        }

    def staging_rows(self, source: str, analysis: dict[str, Any], chunk_size: int = 2000):
        """Entrega filas canónicas con evidencia; no realiza escrituras."""
        adapter = self.adapter_for(source)
        mapping = analysis["mapping"]
        headers = {column["id"]: column for column in analysis["preview"]["columns"]}
        selected = {field: decision.get("selected") for field, decision in mapping.items() if decision.get("selected")}
        number = analysis["preview"]["header_row"] + analysis["preview"]["header_depth"]
        for chunk in adapter.read_chunks(source, analysis["selected_table"], chunk_size):
            for raw in chunk:
                number += 1
                canonical = {}
                provenance = {}
                for field, decision in selected.items():
                    column_id = decision["column_id"]
                    original = raw.get(column_id)
                    value = normalize_text(original)
                    if field == "unidad.codigo": value = normalize_unit_code(original)
                    elif field == "participante.numero_documento": value = normalize_document_number(original)
                    elif field.startswith("participante.") and any(token in field for token in ("nombre", "apellido")): value = normalize_person_name(original)
                    canonical[field] = value or None
                    column = headers[column_id]
                    provenance[field] = {
                        "source_table": analysis["selected_table"], "source_row": number,
                        "original_header": column["original_header"], "normalized_header": column["normalized_header"],
                        "original_value": original, "normalized_value": value or None,
                        "canonical_field": field, "score": decision["score"], "rule": decision["reasons"],
                    }
                yield {"row_number": number, "original": raw, "canonical": canonical, "provenance": provenance}

    @staticmethod
    def detect_units(preview, mapping) -> dict[str, Any]:
        code = mapping["unidad.codigo"].selected; name = mapping["unidad.nombre"].selected
        if not code and not name: return {"count": 0, "missing_code": len(preview.rows), "missing_name": len(preview.rows), "items": []}
        by_id = {column.id: column.index for column in preview.columns}; units = {}
        missing_code = missing_name = 0
        for row in preview.rows:
            c = normalize_unit_code(row[by_id[code.column_id]]) if code and by_id[code.column_id] < len(row) else ""
            n = normalize_text(row[by_id[name.column_id]]) if name and by_id[name.column_id] < len(row) else ""
            missing_code += not bool(c); missing_name += not bool(n)
            if c or n:
                key = (c, n.casefold()); units.setdefault(key, {"code": c, "name": n, "records": 0}); units[key]["records"] += 1
        return {"count": len(units), "missing_code": missing_code, "missing_name": missing_name, "items": list(units.values())}


def file_sha256(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""): digest.update(chunk)
    return digest.hexdigest()
