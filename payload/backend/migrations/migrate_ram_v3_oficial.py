"""Migración idempotente: registra RAM V3 sin eliminar versiones ni datos existentes."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

try:
    from modules.motor_plantillas.services import init_schema
    from services.ram_v3_service import sha256_file
except ImportError:  # ejecución directa desde otra carpeta
    import sys
    BACKEND = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(BACKEND))
    from modules.motor_plantillas.services import init_schema
    from services.ram_v3_service import sha256_file


MAPPING = [
    {"field": "consecutivo", "sheet": "FORMATO RAM", "col_letter": "A", "col": 1, "data_start_row": 15, "fila_fin": 34, "obligatorio": True},
    {"field": "tipo_documento", "sheet": "FORMATO RAM", "col_letter": "B", "col": 2, "data_start_row": 15, "fila_fin": 34, "obligatorio": True, "allowed": ["RC", "TI", "CC", "CE", "PA", "SD"]},
    {"field": "documento_beneficiario", "sheet": "FORMATO RAM", "col_letter": "C", "col": 3, "data_start_row": 15, "fila_fin": 34, "obligatorio": True},
    {"field": "primer_nombre", "sheet": "FORMATO RAM", "col_letter": "D", "col": 4, "data_start_row": 15, "fila_fin": 34, "obligatorio": True},
    {"field": "segundo_nombre", "sheet": "FORMATO RAM", "col_letter": "E", "col": 5, "data_start_row": 15, "fila_fin": 34, "obligatorio": False},
    {"field": "primer_apellido", "sheet": "FORMATO RAM", "col_letter": "F", "col": 6, "data_start_row": 15, "fila_fin": 34, "obligatorio": True},
    {"field": "segundo_apellido", "sheet": "FORMATO RAM", "col_letter": "G", "col": 7, "data_start_row": 15, "fila_fin": 34, "obligatorio": False},
    {"field": "edad_anios", "sheet": "FORMATO RAM", "col_letter": "H", "col": 8, "data_start_row": 15, "fila_fin": 34, "obligatorio": True, "calculo": "edad_al_primer_dia_del_mes"},
    {"field": "edad_meses", "sheet": "FORMATO RAM", "col_letter": "I", "col": 9, "data_start_row": 15, "fila_fin": 34, "obligatorio": True, "calculo": "meses_adicionales_al_primer_dia_del_mes"},
    {"field": "control_asistencia", "sheet": "FORMATO RAM", "col_letter": "J:AH", "col": 10, "data_start_row": 15, "fila_fin": 34, "obligatorio": True, "allowed": ["A", "I", "/", ""]},
    {"field": "total_asistencias", "sheet": "FORMATO RAM", "col_letter": "AI", "col": 35, "data_start_row": 15, "fila_fin": 34, "obligatorio": True},
    {"field": "total_inasistencias", "sheet": "FORMATO RAM", "col_letter": "AJ", "col": 36, "data_start_row": 15, "fila_fin": 34, "obligatorio": True},
    {"field": "causa_retiro", "sheet": "FORMATO RAM", "col_letter": "AK", "col": 37, "data_start_row": 15, "fila_fin": 34, "obligatorio": False, "allowed": ["D", "V", "T", "S", "I", "M", "O"]}
]


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    """Agrega columnas operativas sin borrar, renombrar ni reescribir datos existentes."""
    existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in existing:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def migrate(database_path: str | Path | None = None) -> dict:
    backend = Path(__file__).resolve().parents[1]
    db = Path(database_path) if database_path else backend / "database.sqlite3"
    template = backend / "templates_originales" / "oficiales" / "plantilla_ram_oficial_v3.xlsx"
    rules = backend / "config" / "ram_v3_instrucciones.json"
    if not template.exists():
        raise FileNotFoundError(template)
    if not rules.exists():
        raise FileNotFoundError(rules)
    init_schema(str(db))
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    # Compatibilidad incremental para los nuevos metadatos oficiales del encabezado RAM V3.
    for table in ("usuarios", "beneficiarios"):
        ensure_column(conn, table, "nit_eas", "TEXT")
        ensure_column(conn, table, "servicio_atencion", "TEXT")
        ensure_column(conn, table, "fecha_ingreso", "TEXT")
    stamp = now()
    template_rel = "templates_originales/oficiales/plantilla_ram_oficial_v3.xlsx"
    rules_rel = "config/ram_v3_instrucciones.json"
    digest = sha256_file(template)
    rules_json = rules.read_text(encoding="utf-8")

    row = conn.execute("SELECT id FROM mp_plantillas WHERE tipo='RAM' AND version='3' AND COALESCE(codigo,'')='F27.MT1.PP' ORDER BY id DESC LIMIT 1").fetchone()
    if row:
        mp_id = int(row["id"])
        conn.execute("""
            UPDATE mp_plantillas SET nombre=?, nombre_original=?, nombre_guardado=?, ruta_archivo=?, estado='PROGRAMADO',
                hoja_principal='FORMATO RAM', total_hojas=2, metadata_json=?, fecha_vigencia='2026-08-01',
                observaciones=?, fecha_actualizacion=? WHERE id=?
        """, (
            "Formato Asistencia Registro Mensual RAM V3",
            "F27.MT1_.PP Formato Asistencia Registro Mensual v3.xlsx",
            "plantilla_ram_oficial_v3.xlsx", template_rel,
            json.dumps({"codigo": "F27.MT1.PP", "version": "3", "hojas": ["FORMATO RAM", "INSTRUCCIONES DILIGENCIAMIENTO"], "hash_sha256": digest}, ensure_ascii=False),
            "RAM V3 oficial programado con vigencia 2026-08-01; plantilla maestra inmutable.", stamp, mp_id
        ))
    else:
        cur = conn.execute("""
            INSERT INTO mp_plantillas
            (nombre,tipo,nombre_original,nombre_guardado,ruta_archivo,version,estado,hoja_principal,total_hojas,metadata_json,
             fundacion_id,usuario_creador_id,fecha_creacion,fecha_actualizacion,codigo,fecha_vigencia,observaciones)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            "Formato Asistencia Registro Mensual RAM V3", "RAM",
            "F27.MT1_.PP Formato Asistencia Registro Mensual v3.xlsx", "plantilla_ram_oficial_v3.xlsx",
            template_rel, "3", "PROGRAMADO", "FORMATO RAM", 2,
            json.dumps({"codigo": "F27.MT1.PP", "version": "3", "hojas": ["FORMATO RAM", "INSTRUCCIONES DILIGENCIAMIENTO"], "hash_sha256": digest}, ensure_ascii=False),
            1, None, stamp, stamp, "F27.MT1.PP", "2026-08-01",
            "RAM V3 oficial programado con vigencia 2026-08-01; plantilla maestra inmutable."
        ))
        mp_id = int(cur.lastrowid)

    official = conn.execute("SELECT id FROM plantillas_oficiales WHERE tipo_formato='RAM' AND codigo='F27.MT1.PP' LIMIT 1").fetchone()
    if official:
        official_id = int(official["id"])
        conn.execute("UPDATE plantillas_oficiales SET nombre=?, descripcion=?, activo=1, updated_at=? WHERE id=?", (
            "Formato Asistencia Registro Mensual RAM", "Formato oficial RAM versionado por fecha de vigencia.", stamp, official_id
        ))
    else:
        cur = conn.execute("""
            INSERT INTO plantillas_oficiales(tipo_formato,codigo,nombre,descripcion,activo,created_at,updated_at)
            VALUES('RAM','F27.MT1.PP',?,?,1,?,?)
        """, ("Formato Asistencia Registro Mensual RAM", "Formato oficial RAM versionado por fecha de vigencia.", stamp, stamp))
        official_id = int(cur.lastrowid)

    version = conn.execute("SELECT id FROM plantillas_oficiales_versiones WHERE tipo_formato='RAM' AND codigo='F27.MT1.PP' AND version='3' LIMIT 1").fetchone()
    if version:
        version_id = int(version["id"])
        conn.execute("""
            UPDATE plantillas_oficiales_versiones SET plantilla_oficial_id=?,mp_plantilla_id=?,nombre=?,fecha_vigencia='2026-08-01',
                fecha_vigencia_fin='',estado='programado',estado_publicacion='programado',archivo_path=?,hash_sha256=?,manual_path=?,
                reglas_json=?,archivo_original=?,observaciones=?,mapeo_json=?,updated_at=? WHERE id=?
        """, (
            official_id, mp_id, "Formato Asistencia Registro Mensual RAM V3", template_rel, digest, rules_rel, rules_json,
            "F27.MT1_.PP Formato Asistencia Registro Mensual v3.xlsx",
            "Versión oficial 3 aplicable a reportes desde agosto de 2026. Conserva instrucciones y estructura original.",
            json.dumps(MAPPING, ensure_ascii=False), stamp, version_id
        ))
    else:
        cur = conn.execute("""
            INSERT INTO plantillas_oficiales_versiones
            (plantilla_oficial_id,mp_plantilla_id,tipo_formato,codigo,nombre,version,fecha_vigencia,fecha_vigencia_fin,
             estado,estado_publicacion,archivo_path,hash_sha256,manual_path,reglas_json,archivo_original,observaciones,
             mapeo_json,productos_json,usuario_carga,created_at,updated_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            official_id, mp_id, "RAM", "F27.MT1.PP", "Formato Asistencia Registro Mensual RAM V3", "3",
            "2026-08-01", "", "programado", "programado", template_rel, digest, rules_rel, rules_json,
            "F27.MT1_.PP Formato Asistencia Registro Mensual v3.xlsx",
            "Versión oficial 3 aplicable a reportes desde agosto de 2026. Conserva instrucciones y estructura original.",
            json.dumps(MAPPING, ensure_ascii=False), "[]", None, stamp, stamp
        ))
        version_id = int(cur.lastrowid)

    conn.execute("UPDATE mp_plantillas SET plantilla_oficial_version_id=? WHERE id=?", (version_id, mp_id))
    conn.execute("DELETE FROM plantillas_oficiales_mapeos WHERE version_id=?", (version_id,))
    for item in MAPPING:
        conn.execute("""
            INSERT INTO plantillas_oficiales_mapeos
            (version_id,campo,hoja,columna,col_index,fila_inicio,fila_fin,obligatorio,config_json,created_at,updated_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?)
        """, (
            version_id, item["field"], item["sheet"], item["col_letter"], item["col"], item["data_start_row"],
            item["fila_fin"], 1 if item.get("obligatorio") else 0, json.dumps(item, ensure_ascii=False), stamp, stamp
        ))
    validation_json = json.dumps({"valido": True, "errores": [], "advertencias": ["Las inasistencias requieren fuente de novedades para diligenciar I automáticamente."]}, ensure_ascii=False)
    mapping_row = conn.execute("SELECT id FROM mp_mapeos WHERE plantilla_id=? AND nombre='Mapeo oficial RAM V3' AND version='3' ORDER BY id LIMIT 1", (mp_id,)).fetchone()
    conn.execute("UPDATE mp_mapeos SET activo=0, fecha_actualizacion=? WHERE plantilla_id=?", (stamp, mp_id))
    if mapping_row:
        mapping_id = int(mapping_row["id"])
        conn.execute("""
            UPDATE mp_mapeos SET mapeo_json=?,validacion_json=?,activo=1,fecha_actualizacion=? WHERE id=?
        """, (json.dumps(MAPPING, ensure_ascii=False), validation_json, stamp, mapping_id))
    else:
        cur = conn.execute("""
            INSERT INTO mp_mapeos(plantilla_id,nombre,version,mapeo_json,validacion_json,activo,usuario_creador_id,fecha_creacion,fecha_actualizacion)
            VALUES(?,?,?,?,?,1,NULL,?,?)
        """, (mp_id, "Mapeo oficial RAM V3", "3", json.dumps(MAPPING, ensure_ascii=False), validation_json, stamp, stamp))
        mapping_id = int(cur.lastrowid)
    audit_row = conn.execute("SELECT id FROM plantillas_oficiales_auditoria WHERE accion='REGISTRAR_RAM_V3' AND version_id=? LIMIT 1", (version_id,)).fetchone()
    audit_detail = json.dumps({"hash_sha256": digest, "fecha_vigencia": "2026-08-01", "mapeo_id": mapping_id}, ensure_ascii=False)
    if audit_row:
        conn.execute("UPDATE plantillas_oficiales_auditoria SET detalle_json=?,created_at=? WHERE id=?", (audit_detail, stamp, int(audit_row["id"])))
    else:
        conn.execute("""
            INSERT INTO plantillas_oficiales_auditoria(accion,tipo_formato,version_id,mp_plantilla_id,usuario_id,detalle_json,created_at)
            VALUES('REGISTRAR_RAM_V3','RAM',?,?,NULL,?,?)
        """, (version_id, mp_id, audit_detail, stamp))
    conn.commit()
    conn.close()
    return {"ok": True, "mp_plantilla_id": mp_id, "version_id": version_id, "mapeo_id": mapping_id, "hash_sha256": digest}


if __name__ == "__main__":
    print(json.dumps(migrate(), ensure_ascii=False, indent=2))
