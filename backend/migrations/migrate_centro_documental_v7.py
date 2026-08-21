from __future__ import annotations

import os

from modules.dbapi_compat import sqlite3
from modules.centro_documental.schema import DOCUMENTS_SCHEMA_SQL, DOCUMENTS_SCHEMA_VERSION

BASE_CATALOGS = {
    "PARTICIPACION_PEDAGOGICA": ("PARTICIPACION", "PEDAGOGICO", [
        ("ACTIVA", "Participó activamente durante la experiencia.", 10, []),
        ("PREGUNTAS", "Realizó preguntas relacionadas con el tema.", 20, []),
        ("PARCIAL", "Participó parcialmente.", 30, []),
        ("NO_PARTICIPO", "No participó.", 40, ["ACTIVA"]),
    ]),
    "LOGROS_PEDAGOGICOS": ("LOGRO", "PEDAGOGICO", [
        ("OBJETIVO_COMPLETO", "Se cumplió el objetivo planteado.", 10, ["ACTIVIDAD_NO_REALIZADA"]),
        ("OBJETIVO_PARCIAL", "El objetivo se alcanzó parcialmente.", 20, []),
        ("SIN_LOGROS_COMPROBABLES", "No fue posible comprobar logros.", 30, ["OBJETIVO_COMPLETO"]),
    ]),
    "DIFICULTADES_PEDAGOGICAS": ("DIFICULTAD", "PEDAGOGICO", [
        ("SIN_DIFICULTADES", "No se presentaron dificultades.", 10, ["BAJA_PARTICIPACION","REPROGRAMACION"]),
        ("TIEMPO_LIMITADO", "El tiempo disponible fue limitado.", 20, []),
        ("BAJA_PARTICIPACION", "Se presentó baja participación.", 30, ["SIN_DIFICULTADES"]),
        ("REPROGRAMACION", "La actividad requirió reprogramación.", 40, ["SIN_DIFICULTADES"]),
    ]),
    "COMPROMISOS_PEDAGOGICOS": ("COMPROMISO", "PEDAGOGICO", [("CONTINUAR_PRACTICA", "Continuar la práctica acordada en el entorno familiar.", 10, [])]),
    "PARTICIPACION_PSICOSOCIAL": ("PARTICIPACION", "PSICOSOCIAL", [("DIALOGO_FAMILIAR", "La familia participó en el diálogo orientado.", 10, [])]),
    "RECOMENDACIONES_PSICOSOCIAL": ("RECOMENDACION", "PSICOSOCIAL", [("CONTINUAR_ACOMPANAMIENTO", "Continuar el acompañamiento familiar acordado.", 10, [])]),
    "PARTICIPACION_NUTRICION": ("PARTICIPACION", "SALUD_NUTRICION", [("COMPRENSION_HABITOS", "Se evidenció comprensión de las orientaciones sobre hábitos alimentarios.", 10, [])]),
    "RECOMENDACIONES_NUTRICION": ("RECOMENDACION", "SALUD_NUTRICION", [("CONTINUAR_ORIENTACIONES", "Continuar las prácticas de cuidado y alimentación orientadas.", 10, [])]),
}


def _seed_catalogs(connection) -> None:
    import json
    from datetime import datetime
    now=datetime.now().isoformat(timespec="seconds")
    for code,(category,component,options) in BASE_CATALOGS.items():
        row=connection.execute("SELECT id FROM doc_catalogos_respuesta WHERE codigo=? AND scope='GLOBAL' AND fundacion_id IS NULL",(code,)).fetchone()
        if row:
            catalog_id = int(row[0])
        else:
            # ``lastrowid`` is not portable through the PostgreSQL DB-API
            # compatibility layer (it can legitimately be 0).  The catalog
            # has a stable natural key, so resolve the generated identity
            # explicitly after inserting it.  This also remains compatible
            # with SQLite and keeps the migration idempotent.
            connection.execute(
                "INSERT INTO doc_catalogos_respuesta(codigo,categoria,componente,scope,fundacion_id,activo,creado_en,actualizado_en) VALUES(?,?,?,'GLOBAL',NULL,1,?,?)",
                (code, category, component, now, now),
            )
            row = connection.execute(
                "SELECT id FROM doc_catalogos_respuesta WHERE codigo=? AND scope='GLOBAL' AND fundacion_id IS NULL",
                (code,),
            ).fetchone()
            if not row:
                raise RuntimeError(f"No fue posible resolver el catálogo documental {code}")
            catalog_id = int(row[0])
        for option_code,text,order,contradictions in options:
            exists=connection.execute("SELECT id FROM doc_opciones_respuesta WHERE catalogo_id=? AND codigo=?",(catalog_id,option_code)).fetchone()
            if not exists: connection.execute("INSERT INTO doc_opciones_respuesta(catalogo_id,codigo,texto,orden,activo,requiere_justificacion,contradice_json,creado_en,actualizado_en) VALUES(?,?,?,?,1,0,?,?,?)",(catalog_id,option_code,text,order,json.dumps(contradictions),now,now))


def migrate(database_path: str) -> dict:
    previous = os.environ.get("APP_SCHEMA_MIGRATION_MODE")
    os.environ["APP_SCHEMA_MIGRATION_MODE"] = "1"
    try:
        connection = sqlite3.connect(str(database_path))
        try:
            connection.executescript(DOCUMENTS_SCHEMA_SQL)
            _seed_catalogs(connection)
            connection.commit()
        finally:
            connection.close()
    finally:
        if previous is None:
            os.environ.pop("APP_SCHEMA_MIGRATION_MODE", None)
        else:
            os.environ["APP_SCHEMA_MIGRATION_MODE"] = previous
    return {"ok": True, "documents_schema_version": DOCUMENTS_SCHEMA_VERSION}


if __name__ == "__main__":
    from config import Config
    print(migrate(str(Config.DATABASE_PATH)))
