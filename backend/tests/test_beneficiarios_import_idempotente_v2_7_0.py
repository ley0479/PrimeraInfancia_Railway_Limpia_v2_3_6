"""Regresión real de sincronización idempotente por (documento, unidad)."""
import ast
import sqlite3
import tempfile
import threading
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

BACKEND = Path(__file__).resolve().parents[1]


def _load_sync(db_path, events):
    source = (BACKEND / "app.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "guardar_beneficiarios_actuales")

    def connect():
        conn = sqlite3.connect(db_path, timeout=20)
        conn.row_factory = sqlite3.Row
        return conn

    ns = {
        "database_connection": connect,
        "fundacion_actual_id": lambda: 7,
        "usuario_actual_id": lambda: 99,
        "datetime": __import__("datetime").datetime,
        "EstadoUsuario": SimpleNamespace(ACTIVO="ACTIVO", RETIRADO="RETIRADO", FALLECIDO="FALLECIDO", ESTADOS_VALIDOS={"ACTIVO", "RETIRADO", "FALLECIDO"}),
        "ConfiguracionSistema": SimpleNamespace(UNIDADES=[]),
        "normalize_unidad": lambda value: " ".join(str(value or "").strip().upper().split()),
        "limpiar_valor": lambda value: str(value or "").strip(),
        "dividir_nombre": lambda value: (str(value or "SIN NOMBRE").split()[0], " ".join(str(value or "").split()[1:])),
        "unir_partes": lambda *values: " ".join(str(v).strip() for v in values if str(v or "").strip()),
        "log_procesamiento_base_maestra": lambda event, **data: events.append({"event": event, **data}),
        "log_beneficiarios_sincronizacion_batch": lambda records: events.extend(dict(record) for record in records),
    }
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(BACKEND / "app.py"), "exec"), ns)
    return ns["guardar_beneficiarios_actuales"]


def _create_db(path):
    columns = [
        "documento TEXT NOT NULL", "nombres TEXT", "apellidos TEXT", "fecha_nacimiento TEXT", "sexo TEXT",
        "unidad TEXT NOT NULL", "estado TEXT", "tipo_beneficiario TEXT", "fecha_ingreso TEXT", "fecha_carga TEXT",
        "nui TEXT", "tipo_documento TEXT", "primer_nombre TEXT", "segundo_nombre TEXT", "primer_apellido TEXT",
        "segundo_apellido TEXT", "nombre_acudiente TEXT", "documento_acudiente TEXT", "tipo_documento_acudiente TEXT",
        "parentesco TEXT", "primer_nombre_acudiente TEXT", "segundo_nombre_acudiente TEXT",
        "primer_apellido_acudiente TEXT", "segundo_apellido_acudiente TEXT", "fecha_modificacion_cuentame TEXT",
        "edad_meses INTEGER", "grupo_edad TEXT", "telefono TEXT", "regional TEXT", "centro_zonal TEXT",
        "municipio TEXT", "modalidad TEXT", "numero_contrato TEXT", "vigencia TEXT", "nombre_eas TEXT", "nit_eas TEXT",
        "servicio_atencion TEXT", "direccion_unidad TEXT", "codigo_unidad_servicio TEXT", "fundacion_id INTEGER",
        "usuario_creador_id INTEGER", "fecha_creacion TEXT", "fecha_actualizacion TEXT",
    ]
    conn = sqlite3.connect(path)
    conn.execute(f"CREATE TABLE beneficiarios(id INTEGER PRIMARY KEY AUTOINCREMENT,{','.join(columns)},CONSTRAINT beneficiarios_documento_unidad_key UNIQUE(documento,unidad))")
    conn.execute("CREATE TABLE unidades(id INTEGER PRIMARY KEY AUTOINCREMENT,nombre TEXT,total_usuarios INTEGER,total_gestantes INTEGER,fecha_actualizacion TEXT,fundacion_id INTEGER,UNIQUE(fundacion_id,nombre))")
    conn.commit()
    conn.close()


def _row(document="1077493011", unit="TIGRE", name="ANA UNO"):
    return {"documento": document, "unidad": unit, "nombre": name, "estado": "ACTIVO", "edad_meses": 24}


def _count(path, document="1077493011", unit="TIGRE"):
    conn = sqlite3.connect(path)
    result = conn.execute("SELECT COUNT(*) FROM beneficiarios WHERE documento=? AND unidad=?", (document, unit)).fetchone()[0]
    conn.close()
    return result


def test_nuevo_repetido_preexistente_y_duplicado_interno():
    path = Path(tempfile.mkdtemp()) / "sync.sqlite3"
    _create_db(path)
    events = []
    sync = _load_sync(path, events)
    sync(pd.DataFrame([_row()]), "primero.xlsx")
    assert _count(path) == 1
    sync(pd.DataFrame([_row(name="ANA DOS")]), "repetido.xlsx")
    assert _count(path) == 1
    sync(pd.DataFrame([_row(name="ANA TRES"), _row(name="ANA FINAL")]), "duplicado.xlsx")
    assert _count(path) == 1
    conn = sqlite3.connect(path)
    assert conn.execute("SELECT nombres FROM beneficiarios WHERE documento='1077493011' AND unidad='TIGRE'").fetchone()[0] == "ANA"
    schema = conn.execute("SELECT sql FROM sqlite_master WHERE name='beneficiarios'").fetchone()[0]
    conn.close()
    assert "UNIQUE(documento,unidad)" in schema.replace(" ", "")
    assert any(e.get("operacion") == "CONSOLIDADO_ULTIMO_REGISTRO" for e in events)
    assert not any(e.get("event", "").lower().startswith("error") for e in events)


def test_dos_procesos_concurrentes_no_duplican():
    path = Path(tempfile.mkdtemp()) / "concurrent.sqlite3"
    _create_db(path)
    events = []
    errors = []
    barrier = threading.Barrier(2)

    def worker(name):
        try:
            sync = _load_sync(path, events)
            barrier.wait(timeout=5)
            sync(pd.DataFrame([_row(name=name)]), f"{name}.xlsx")
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(name,)) for name in ("PROCESO A", "PROCESO B")]
    for thread in threads: thread.start()
    for thread in threads: thread.join(timeout=30)
    assert errors == []
    assert _count(path) == 1


if __name__ == "__main__":
    test_nuevo_repetido_preexistente_y_duplicado_interno()
    test_dos_procesos_concurrentes_no_duplican()
    print("Beneficiarios import idempotente v2.7.0: PASS")
