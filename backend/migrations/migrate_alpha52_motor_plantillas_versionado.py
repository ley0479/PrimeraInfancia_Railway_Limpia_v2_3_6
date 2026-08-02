from __future__ import annotations

import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATABASE = ROOT / 'database.sqlite3'


def main(database_path: str | Path = DATABASE) -> None:
    from modules.motor_plantillas.services import init_schema
    init_schema(str(database_path))
    conn = sqlite3.connect(database_path)
    cur = conn.cursor()
    # Asegurar que, si ya hay plantillas RPP activas anteriores, queden registradas como versiones históricas compatibles.
    cur.execute("SELECT id, nombre, tipo, version, ruta_archivo, nombre_original, estado FROM mp_plantillas WHERE UPPER(tipo)='RPP'")
    rows = cur.fetchall()
    for row in rows:
        mp_id, nombre, tipo, version, ruta, nombre_original, estado = row
        exists = cur.execute("SELECT id FROM plantillas_oficiales_versiones WHERE mp_plantilla_id=?", (mp_id,)).fetchone()
        if exists:
            continue
        oficial = cur.execute("SELECT id FROM plantillas_oficiales WHERE tipo_formato='RPP' AND COALESCE(codigo,'')='F21.MT1.PP' LIMIT 1").fetchone()
        if oficial:
            oficial_id = oficial[0]
        else:
            cur.execute("""
                INSERT INTO plantillas_oficiales(tipo_formato, codigo, nombre, descripcion, activo, created_at, updated_at)
                VALUES ('RPP', 'F21.MT1.PP', 'RPP oficial', 'Formato RPP versionado', 1, datetime('now'), datetime('now'))
            """)
            oficial_id = cur.lastrowid
        estado_v = 'vigente' if str(estado or '').upper() in {'ACTIVA','VIGENTE'} else 'historico'
        cur.execute("""
            INSERT INTO plantillas_oficiales_versiones
            (plantilla_oficial_id, mp_plantilla_id, tipo_formato, codigo, nombre, version, fecha_vigencia,
             estado, archivo_path, archivo_original, observaciones, mapeo_json, productos_json, usuario_carga, created_at, updated_at)
            VALUES (?, ?, 'RPP', 'F21.MT1.PP', ?, ?, '', ?, ?, ?, 'Migrado automáticamente ALPHA52', '[]', '[]', NULL, datetime('now'), datetime('now'))
        """, (oficial_id, mp_id, nombre or 'RPP oficial', version or '1.0', estado_v, ruta, nombre_original))
        version_id = cur.lastrowid
        cur.execute("UPDATE mp_plantillas SET plantilla_oficial_version_id=? WHERE id=?", (version_id, mp_id))
    conn.commit()
    conn.close()
    print('Migración ALPHA52 Motor de Plantillas Versionado aplicada correctamente.')


if __name__ == '__main__':
    main()
