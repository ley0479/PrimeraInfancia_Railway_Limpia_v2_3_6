from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Iterator


@dataclass
class TableDescriptor:
    id: str
    name: str
    rows: int
    columns: int
    hidden: bool = False
    empty: bool = False
    score: float = 0


@dataclass
class SourceInspection:
    adapter: str
    mime: str
    extension: str
    signature_valid: bool
    tables: list[TableDescriptor]
    warnings: list[str] = field(default_factory=list)


@dataclass
class ColumnDescriptor:
    id: str
    index: int
    original_header: str
    normalized_header: str
    flattened_header: str


@dataclass
class TabularPreview:
    table_id: str
    header_row: int
    header_depth: int
    columns: list[ColumnDescriptor]
    rows: list[list[Any]]


@dataclass
class CandidateScore:
    canonical_field: str
    column_id: str
    original_header: str
    score: float
    confidence: str
    reasons: list[str]


@dataclass
class MappingDecision:
    canonical_field: str
    selected: CandidateScore | None
    alternatives: list[CandidateScore]
    rejected: list[CandidateScore]
    status: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class DataSourceAdapter:
    def can_handle(self, source: str) -> bool:  # pragma: no cover - contract
        raise NotImplementedError

    def inspect(self, source: str) -> SourceInspection:
        raise NotImplementedError

    def list_tables(self, source: str) -> list[TableDescriptor]:
        return self.inspect(source).tables

    def preview(self, source: str, table_id: str, limit: int = 50) -> TabularPreview:
        raise NotImplementedError

    def read_chunks(self, source: str, table_id: str, chunk_size: int = 2000) -> Iterator[list[dict[str, Any]]]:
        raise NotImplementedError

    def get_source_fingerprint(self, source: str, table_id: str) -> str:
        raise NotImplementedError
