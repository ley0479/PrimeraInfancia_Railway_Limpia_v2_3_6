#!/usr/bin/env python3
"""Auditoría estática del SQL runtime antes de desplegar PostgreSQL.

Analiza únicamente literales que parecen sentencias SQL. Distingue el legado
SQLite cubierto por ``modules.dbapi_compat`` de construcciones que aún no tienen
traducción segura. No modifica código ni datos.
"""
from __future__ import annotations

import argparse
import ast
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

SQL_PREFIX = re.compile(r"^\s*(?:SELECT|INSERT|UPDATE|DELETE|CREATE|ALTER|DROP|PRAGMA|WITH|BEGIN|COMMIT|ROLLBACK)\b", re.I)
DIRECT_SQLITE_IMPORT = re.compile(r"(^|\n)\s*(?:import\s+sqlite3\b|from\s+sqlite3\s+import\b)", re.I)
APPROVED_NATIVE_SQLITE = {
    "database.py",
    "modules/dbapi_compat.py",
    "modules/seguridad/tenant_sql_guard.py",
}
SUPPORTED_LEGACY: dict[str, re.Pattern[str]] = {
    "pragma": re.compile(r"\bPRAGMA\b", re.I),
    "sqlite_master": re.compile(r"\bsqlite_master\b", re.I),
    "autoincrement": re.compile(r"\bAUTOINCREMENT\b", re.I),
    "insert_or_ignore": re.compile(r"\bINSERT\s+OR\s+IGNORE\b", re.I),
    "ifnull": re.compile(r"\bIFNULL\s*\(", re.I),
    "group_concat": re.compile(r"\bGROUP_CONCAT\s*\(", re.I),
    "strftime": re.compile(r"\bstrftime\s*\(", re.I),
    "julianday": re.compile(r"\bjulianday\s*\(", re.I),
    "printf_integer": re.compile(r"\bprintf\s*\(\s*['\"]%0\d+d['\"]", re.I),
    "last_insert_rowid": re.compile(r"\blast_insert_rowid\s*\(", re.I),
    "collate_nocase": re.compile(r"\bCOLLATE\s+NOCASE\b", re.I),
    "date_now": re.compile(r"\bdate\s*\(\s*['\"]now['\"]\s*\)", re.I),
    "datetime_now": re.compile(r"\bdatetime\s*\(\s*['\"]now['\"]\s*\)", re.I),
}
UNSUPPORTED: dict[str, re.Pattern[str]] = {
    "insert_or_replace": re.compile(r"\bINSERT\s+OR\s+REPLACE\b", re.I),
    "replace_into": re.compile(r"\bREPLACE\s+INTO\b", re.I),
    "glob": re.compile(r"\bGLOB\b", re.I),
    "regexp": re.compile(r"\bREGEXP\b", re.I),
    "json_extract": re.compile(r"\bjson_(?:extract|each|tree|set|insert|replace|remove)\s*\(", re.I),
    "iif": re.compile(r"\bIIF\s*\(", re.I),
    "total": re.compile(r"\bTOTAL\s*\(", re.I),
    "instr": re.compile(r"\bINSTR\s*\(", re.I),
    "vacuum_into": re.compile(r"\bVACUUM\s+INTO\b", re.I),
    "without_rowid": re.compile(r"\bWITHOUT\s+ROWID\b", re.I),
    "limit_comma": re.compile(r"\bLIMIT\s+[^;\n]+,\s*[^;\n]+", re.I),
    "date_modifier": re.compile(r"\b(?:date|datetime)\s*\([^)]*,\s*['\"][+-]\d+\s+(?:day|days|month|months|year|years)", re.I),
    "datetime_type": re.compile(r"\b(?:CAST\s*\([^)]*\s+AS\s+DATETIME\b|\bDATETIME\s+(?:NOT\s+NULL|DEFAULT|,|\)))", re.I),
}


def _string_literals(path: Path) -> Iterable[tuple[int, str]]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"), filename=str(path))
    except SyntaxError:
        return []
    rows: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            value = node.value.strip()
            if SQL_PREFIX.search(value):
                rows.append((getattr(node, "lineno", 0), value))
    return rows


def audit_runtime_sql(root: Path) -> dict[str, Any]:
    root = root.resolve()
    backend = root / "backend"
    direct_imports: list[str] = []
    supported_hits: list[dict[str, Any]] = []
    unsupported_hits: list[dict[str, Any]] = []
    sql_literals = 0

    excluded_parts = {".venv", "venv", "site-packages", "__pycache__"}
    for path in sorted(backend.rglob("*.py")):
        rel = path.relative_to(backend).as_posix()
        if excluded_parts.intersection(path.relative_to(backend).parts):
            continue
        if rel.startswith(("tests/", "tools/", "migrations/")):
            continue
        source = path.read_text(encoding="utf-8", errors="ignore")
        if rel not in APPROVED_NATIVE_SQLITE and DIRECT_SQLITE_IMPORT.search(source):
            direct_imports.append(rel)
        for line, sql in _string_literals(path):
            sql_literals += 1
            compact = re.sub(r"\s+", " ", sql)[:280]
            for name, pattern in SUPPORTED_LEGACY.items():
                if pattern.search(sql):
                    supported_hits.append({"file": rel, "line": line, "construct": name, "sql": compact})
            for name, pattern in UNSUPPORTED.items():
                if pattern.search(sql):
                    unsupported_hits.append({"file": rel, "line": line, "construct": name, "sql": compact})

    translator = (backend / "modules/dbapi_compat.py").read_text(encoding="utf-8", errors="ignore")
    translator_contract = {
        "julianday": "_translate_julianday" in translator,
        "group_concat": "_translate_group_concat" in translator,
        "sqlite_master": "def _sqlite_master" in translator,
        "pragma": "def _pragma" in translator,
        "qmark": "def _convert_qmark" in translator,
        "insert_or_ignore": "ON CONFLICT DO NOTHING" in translator,
        "last_insert_rowid": "LAST_INSERT_ROWID" in translator.upper(),
    }
    missing_contract = sorted(name for name, ok in translator_contract.items() if not ok)
    status = "PASS" if not direct_imports and not unsupported_hits and not missing_contract else "BLOCKED"
    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "status": status,
        "sql_literals_scanned": sql_literals,
        "direct_sqlite_imports": direct_imports,
        "supported_legacy_constructs": supported_hits,
        "unsupported_constructs": unsupported_hits,
        "translator_contract": translator_contract,
        "translator_contract_missing": missing_contract,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Auditar SQL runtime para PostgreSQL")
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[2]))
    parser.add_argument("--report", default="data/integrity/postgresql_runtime_audit.json")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    report = audit_runtime_sql(root)
    target = (root / args.report).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "status": report["status"],
        "sql_literals_scanned": report["sql_literals_scanned"],
        "direct_sqlite_imports": len(report["direct_sqlite_imports"]),
        "unsupported_constructs": len(report["unsupported_constructs"]),
        "report": str(target),
    }, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
