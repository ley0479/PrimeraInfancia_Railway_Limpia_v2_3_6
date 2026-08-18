"""Quality Gate de la migración global: dos ejecuciones y una sola fila activa."""
from pathlib import Path
import sys
import tempfile

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from migrations.migrate_identidad_global_v7 import migrate
from modules.dbapi_compat import sqlite3


def main():
    with tempfile.TemporaryDirectory() as tmp:
        database = str(Path(tmp) / "identity.db")
        first = migrate(database)
        second = migrate(database)
        assert first["status"] == second["status"] == "PASS"
        conn = sqlite3.connect(database)
        try:
            assert conn.execute("SELECT COUNT(*) FROM configuracion_global_plataforma").fetchone()[0] == 1
            row = conn.execute("SELECT id, identity_version FROM configuracion_global_plataforma").fetchone()
            assert tuple(row) == (1, 1)
            assert conn.execute("SELECT version FROM identidad_schema_version WHERE componente='identidad_global'").fetchone()[0] == 1
        finally:
            conn.close()
    print("Migración identidad global v7 RUN 1/RUN 2: PASS")


if __name__ == "__main__":
    main()
