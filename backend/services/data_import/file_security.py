from __future__ import annotations

import json
import zipfile
from pathlib import Path

ZIP_EXTENSIONS = {".xlsx", ".xlsm", ".ods"}
TEXT_EXTENSIONS = {".csv", ".tsv", ".txt", ".json", ".ndjson"}


def validate_tabular_source(path: str, declared_extension: str, max_uncompressed_ratio: int = 100) -> dict:
    """Valida firma y estructura sin ejecutar macros, fórmulas ni enlaces."""
    source = Path(path); extension = str(declared_extension or source.suffix).lower(); size = source.stat().st_size
    if not size: raise ValueError("El archivo está vacío.")
    with source.open("rb") as stream: head = stream.read(8192)
    warnings = []
    if extension in ZIP_EXTENSIONS:
        if not head.startswith(b"PK") or not zipfile.is_zipfile(source):
            raise ValueError("La firma real no corresponde a un contenedor Office/ODS válido.")
        with zipfile.ZipFile(source) as archive:
            members = archive.infolist(); expanded = sum(item.file_size for item in members); names = set(archive.namelist())
            if len(members) > 20_000 or expanded > max(size * max_uncompressed_ratio, 50 * 1024 * 1024):
                raise ValueError("El archivo comprimido excede los límites de seguridad.")
            if extension in {".xlsx", ".xlsm"} and "[Content_Types].xml" not in names:
                raise ValueError("El archivo no contiene una estructura OpenXML válida.")
            if extension == ".ods" and "mimetype" not in names:
                raise ValueError("El archivo no contiene una estructura ODS válida.")
            if extension == ".xlsm": warnings.append("Las macros permanecen inertes y nunca se ejecutan.")
    elif extension == ".xls":
        if not head.startswith(bytes.fromhex("D0CF11E0A1B11AE1")):
            raise ValueError("La firma real no corresponde a un libro XLS válido.")
    elif extension in TEXT_EXTENSIONS:
        if b"\x00" in head: raise ValueError("La fuente declarada como texto contiene datos binarios.")
        if extension in {".json", ".ndjson"}:
            try:
                text = source.read_text(encoding="utf-8-sig")
                if extension == ".json": json.loads(text)
                else:
                    for line in text.splitlines()[:100]:
                        if line.strip(): json.loads(line)
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ValueError("El contenido JSON no es válido.") from exc
    else: raise ValueError("Extensión tabular no permitida.")
    return {"extension": extension, "size": size, "signature_valid": True, "warnings": warnings}
