from __future__ import annotations

import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from modules.integraciones_configuracion.repository import IntegracionesConfiguracionRepository


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="pi-cleanup-") as tmp:
        db = Path(tmp) / "cleanup.sqlite3"
        raw = sqlite3.connect(db)
        raw.executescript("""
        CREATE TABLE master_ninos(id INTEGER PRIMARY KEY,fundacion_id INTEGER,nombre TEXT);
        CREATE TABLE th_personas(id INTEGER PRIMARY KEY,fundacion_id INTEGER,nombre TEXT);
        CREATE TABLE sn_valoraciones(id INTEGER PRIMARY KEY,fundacion_id INTEGER,detalle TEXT);
        CREATE TABLE usuarios_app(id INTEGER PRIMARY KEY,fundacion_id INTEGER,username TEXT);
        INSERT INTO master_ninos VALUES(1,1,'A'),(2,2,'B');
        INSERT INTO th_personas VALUES(1,1,'A'),(2,2,'B');
        INSERT INTO sn_valoraciones VALUES(1,1,'A'),(2,2,'B');
        INSERT INTO usuarios_app VALUES(1,1,'admin-a'),(2,2,'admin-b');
        """)
        raw.commit();raw.close()

        repo = IntegracionesConfiguracionRepository(str(db), ROOT, Path(tmp))
        opened = []
        def connect():
            conn = sqlite3.connect(db)
            conn.row_factory = sqlite3.Row
            opened.append(conn)
            return conn
        repo.connect = connect
        before = repo.operational_reset_preview(1)
        assert before["total"] == 3
        try:
            repo.reset_operational_data(1, {"id": 1, "username": "qa"}, "NO")
            raise AssertionError("La confirmación incorrecta fue aceptada")
        except ValueError:
            pass
        result = repo.reset_operational_data(1, {"id": 1, "username": "qa"}, "LIMPIAR DATOS")
        assert result["despues"]["total"] == 0
        conn = connect()
        assert conn.execute("SELECT COUNT(*) FROM master_ninos WHERE fundacion_id=2").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM th_personas WHERE fundacion_id=2").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM sn_valoraciones WHERE fundacion_id=2").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM usuarios_app").fetchone()[0] == 2
        assert conn.execute("SELECT COUNT(*) FROM ic_auditoria WHERE accion='LIMPIAR_DATOS_OPERATIVOS'").fetchone()[0] == 1
        conn.close()
        for connection in opened:
            try:
                connection.close()
            except Exception:
                pass

    routes = (ROOT / "backend/modules/integraciones_configuracion/routes.py").read_text(encoding="utf-8")
    frontend = (ROOT / "frontend/js/modules/integraciones-configuracion.js").read_text(encoding="utf-8")
    assert "@require_roles('SUPERADMIN')" in routes and "LIMPIAR DATOS" in frontend
    print("OK: limpieza operativa aislada, confirmada y auditada")


if __name__ == "__main__":
    main()
