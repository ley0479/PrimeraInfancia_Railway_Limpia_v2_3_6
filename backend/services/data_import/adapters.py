from __future__ import annotations

import csv
import hashlib
import json
import mimetypes
from pathlib import Path
from typing import Any, Iterator

import pandas as pd
from openpyxl import load_workbook

from .catalog import CANONICAL_FIELDS
from .header_detector import detect_header
from .models import ColumnDescriptor, DataSourceAdapter, SourceInspection, TableDescriptor, TabularPreview
from .normalizers import normalize_header, normalize_text


def _columns(headers: list[Any]) -> list[ColumnDescriptor]:
    seen: dict[str, int] = {}
    result = []
    for index, raw in enumerate(headers):
        original = normalize_text(raw)
        normalized = normalize_header(original)
        base = normalized or f"columna {index + 1}"
        seen[base] = seen.get(base, 0) + 1
        unique = base if seen[base] == 1 else f"{base} #{seen[base]}"
        result.append(ColumnDescriptor(f"col_{index + 1}", index, original, normalized, unique))
    return result


class ExcelAdapter(DataSourceAdapter):
    EXTENSIONS = {".xlsx", ".xlsm", ".xls", ".ods"}

    def can_handle(self, source: str) -> bool:
        return Path(source).suffix.lower() in self.EXTENSIONS

    def _frames(self, source: str) -> dict[str, pd.DataFrame]:
        ext = Path(source).suffix.lower()
        engine = "odf" if ext == ".ods" else None
        return pd.read_excel(source, sheet_name=None, header=None, dtype=object, engine=engine)

    def inspect(self, source: str) -> SourceInspection:
        frames = self._frames(source)
        hidden: set[str] = set()
        if Path(source).suffix.lower() in {".xlsx", ".xlsm"}:
            wb = load_workbook(source, read_only=True, data_only=True, keep_links=False)
            hidden = {ws.title for ws in wb.worksheets if ws.sheet_state != "visible"}
            wb.close()
        tables = []
        for name, frame in frames.items():
            useful = frame.dropna(how="all").dropna(axis=1, how="all")
            sample = useful.head(50).values.tolist()
            header, _depth, headers = detect_header(sample)
            aliases = sum(normalize_header(h) in {normalize_header(a) for f in CANONICAL_FIELDS.values() for a in f["aliases"]} for h in headers)
            tables.append(TableDescriptor(name, name, int(useful.shape[0]), int(useful.shape[1]), name in hidden, useful.empty, aliases * 30 + useful.shape[1] + min(useful.shape[0], 100) - header))
        return SourceInspection("excel", mimetypes.guess_type(source)[0] or "application/octet-stream", Path(source).suffix.lower(), True, tables)

    def preview(self, source: str, table_id: str, limit: int = 50) -> TabularPreview:
        frame = self._frames(source)[table_id].dropna(how="all").dropna(axis=1, how="all")
        raw = frame.head(max(60, limit + 5)).values.tolist()
        header, depth, headers = detect_header(raw)
        rows = raw[header + depth:header + depth + limit]
        return TabularPreview(table_id, header + 1, depth, _columns(headers), rows)

    def read_chunks(self, source: str, table_id: str, chunk_size: int = 2000) -> Iterator[list[dict[str, Any]]]:
        preview = self.preview(source, table_id, 1)
        frame = self._frames(source)[table_id].iloc[preview.header_row - 1 + preview.header_depth:]
        headers = [c.id for c in preview.columns]
        for start in range(0, len(frame), chunk_size):
            yield [dict(zip(headers, row)) for row in frame.iloc[start:start + chunk_size].values.tolist()]

    def get_source_fingerprint(self, source: str, table_id: str) -> str:
        preview = self.preview(source, table_id, 10)
        signature = "|".join(c.normalized_header for c in preview.columns)
        return hashlib.sha256(f"excel|{table_id}|{signature}".encode()).hexdigest()


class CsvAdapter(DataSourceAdapter):
    EXTENSIONS = {".csv", ".tsv", ".txt", ".tab"}
    def can_handle(self, source: str) -> bool: return Path(source).suffix.lower() in self.EXTENSIONS
    def _read(self, source: str) -> pd.DataFrame:
        for encoding in ("utf-8-sig", "latin-1"):
            try:
                return pd.read_csv(source, sep=None, engine="python", header=None, dtype=object, encoding=encoding)
            except UnicodeDecodeError:
                continue
        raise ValueError("Codificación CSV no soportada")
    def inspect(self, source: str) -> SourceInspection:
        frame = self._read(source); useful = frame.dropna(how="all").dropna(axis=1, how="all")
        return SourceInspection("csv", mimetypes.guess_type(source)[0] or "text/plain", Path(source).suffix.lower(), True, [TableDescriptor("data", "data", len(useful), len(useful.columns), empty=useful.empty)])
    def preview(self, source: str, table_id: str, limit: int = 50) -> TabularPreview:
        raw = self._read(source).head(max(60, limit + 5)).values.tolist(); h, d, headers = detect_header(raw)
        return TabularPreview("data", h + 1, d, _columns(headers), raw[h + d:h + d + limit])
    def read_chunks(self, source: str, table_id: str, chunk_size: int = 2000):
        preview = self.preview(source, table_id, 1); frame = self._read(source).iloc[preview.header_row - 1 + preview.header_depth:]
        for start in range(0, len(frame), chunk_size): yield [dict(zip([c.id for c in preview.columns], row)) for row in frame.iloc[start:start + chunk_size].values.tolist()]
    def get_source_fingerprint(self, source: str, table_id: str) -> str:
        return hashlib.sha256("|".join(c.normalized_header for c in self.preview(source, table_id).columns).encode()).hexdigest()


class JsonAdapter(CsvAdapter):
    EXTENSIONS = {".json", ".ndjson"}
    def _read(self, source: str) -> pd.DataFrame:
        return pd.read_json(source, lines=Path(source).suffix.lower() == ".ndjson").pipe(lambda f: pd.concat([pd.DataFrame([list(f.columns)]), f], ignore_index=True))
    def inspect(self, source: str) -> SourceInspection:
        result = super().inspect(source); result.adapter = "json"; result.mime = "application/json"; return result


class RelationalDatabaseAdapter(DataSourceAdapter):
    """Contrato de extensión; requiere una configuración autorizada, no credenciales en archivos."""
    def can_handle(self, source: str) -> bool: return str(source).startswith(("postgresql://", "sqlite://", "mysql://", "mssql://"))
    def inspect(self, source: str) -> SourceInspection: raise PermissionError("La conexión relacional debe ser configurada y autorizada por un administrador.")
    preview = inspect
    read_chunks = inspect
    get_source_fingerprint = inspect


class DocumentExtractionAdapter(DataSourceAdapter):
    def can_handle(self, source: str) -> bool: return str(source).startswith("document-extraction://")
    def inspect(self, source: str) -> SourceInspection: raise ValueError("Se requiere un resultado tabular aprobado del módulo IDP; no se simula OCR.")
    preview = inspect
    read_chunks = inspect
    get_source_fingerprint = inspect
