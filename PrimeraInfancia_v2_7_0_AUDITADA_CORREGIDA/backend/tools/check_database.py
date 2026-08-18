#!/usr/bin/env python3
from __future__ import annotations
import argparse, time
from sqlalchemy import create_engine, text

def normalize(url: str) -> str:
    value = url.strip()
    if value.startswith('postgres://'):
        return 'postgresql+psycopg://' + value[len('postgres://'):]
    if value.startswith('postgresql://'):
        return 'postgresql+psycopg://' + value[len('postgresql://'):]
    return value

def main() -> int:
    parser=argparse.ArgumentParser(description='Prueba una conexión PostgreSQL sin imprimir secretos.')
    parser.add_argument('--url', required=True)
    args=parser.parse_args()
    url=normalize(args.url)
    if not url.startswith('postgresql+psycopg://'):
        raise SystemExit('La URL no es PostgreSQL/psycopg.')
    started=time.perf_counter()
    engine=create_engine(url,pool_pre_ping=True,connect_args={'connect_timeout':10},future=True)
    try:
        with engine.connect() as conn:
            row=conn.execute(text('SELECT current_database(), current_user, version()')).first()
        elapsed=round((time.perf_counter()-started)*1000,2)
        print(f'OK PostgreSQL: base={row[0]}, usuario={row[1]}, latencia_ms={elapsed}')
        return 0
    finally:
        engine.dispose()
if __name__=='__main__':
    raise SystemExit(main())
