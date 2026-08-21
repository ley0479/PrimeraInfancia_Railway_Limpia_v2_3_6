from __future__ import annotations

from modules.dbapi_compat import sqlite3


def _limit(value, maximum=100) -> int:
    try: parsed=int(value)
    except (TypeError,ValueError): parsed=25
    return max(1,min(parsed,maximum))


def search_participants(database_path: str, tenant: int, query: str = "", unit: str = "", limit: int = 25, offset: int = 0) -> dict:
    connection=sqlite3.connect(str(database_path)); connection.row_factory=sqlite3.Row
    where=["fundacion_id=?","activo=1"]; params=[tenant]
    if unit: where.append("unidad_servicio=?"); params.append(unit)
    if query:
        where.append("(LOWER(COALESCE(nombre_completo,'')) LIKE ? OR COALESCE(documento,'') LIKE ? OR COALESCE(nui,'') LIKE ?)")
        token=f"%{query.strip().lower()}%"; params.extend([token,token,token])
    take=_limit(limit); skip=max(0,int(offset or 0))
    sql=f"SELECT id,documento,nui,nombre_completo,fecha_nacimiento,grupo_etario,sexo,unidad_servicio,codigo_unidad,estado FROM master_ninos WHERE {' AND '.join(where)} ORDER BY nombre_completo LIMIT ? OFFSET ?"
    try: rows=connection.execute(sql,(*params,take,skip)).fetchall()
    except Exception: rows=[]
    connection.close()
    return {"participantes":[dict(row) for row in rows],"limit":take,"offset":skip}


def search_professionals(database_path: str, tenant: int, query: str = "", unit: str = "", limit: int = 25) -> dict:
    connection=sqlite3.connect(str(database_path)); connection.row_factory=sqlite3.Row
    where=["fundacion_id=?","COALESCE(activo,1)=1"]; params=[tenant]
    if unit: where.append("COALESCE(unidad,'')=?"); params.append(unit)
    if query: where.append("(LOWER(COALESCE(nombre,'')) LIKE ? OR LOWER(COALESCE(cargo,'')) LIKE ?)"); token=f"%{query.strip().lower()}%"; params.extend([token,token])
    try: rows=connection.execute(f"SELECT id,nombre,cargo,rol_normalizado,unidad,estado FROM th_personas WHERE {' AND '.join(where)} ORDER BY nombre LIMIT ?",(*params,_limit(limit))).fetchall()
    except Exception: rows=[]
    connection.close()
    return {"profesionales":[dict(row) for row in rows],"limit":_limit(limit)}
