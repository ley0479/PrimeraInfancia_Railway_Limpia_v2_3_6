from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from modules.talento_humano.repository import TalentoHumanoRepository


def main() -> None:
    repo = TalentoHumanoRepository.__new__(TalentoHumanoRepository)
    calls: dict[str, object] = {}
    repo.init_schema = lambda: None

    def fetch_one(sql, params):
        calls['lookup_sql'] = sql
        calls['lookup_params'] = params
        return {
            'id': 77,
            'documento': '11811380',
            'fundacion_id': 1,
            'unidad': 'UNIDAD ANTERIOR',
            'cargo': 'COORDINADOR TÉCNICO',
        }

    repo.fetch_one = fetch_one
    repo.execute_update = lambda sql, params: calls.update(update_sql=sql, update_params=params)
    repo.execute = lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError('No debe insertar un documento existente'))
    repo.audit = lambda *args, **kwargs: None

    talent_id, is_new = repo.upsert_base_record(
        {
            'documento': '11811380',
            'nombre': 'LEISON PALACIOS BLANDON',
            'unidad': 'NECORA3',
            'cargo': 'COORDINADOR TÉCNICO',
            'fundacion_id': 1,
        },
        {'fundacion_id': 1, 'usuario_id': 1},
    )

    assert talent_id == 77 and is_new is False
    assert calls['lookup_params'] == ['11811380', 1, 1]
    assert "COALESCE(unidad" not in str(calls['lookup_sql'])
    assert calls['update_params']['unidad'] == 'NECORA3'
    print('OK: documento repetido actualiza el registro y no intenta INSERT')


if __name__ == '__main__':
    main()
