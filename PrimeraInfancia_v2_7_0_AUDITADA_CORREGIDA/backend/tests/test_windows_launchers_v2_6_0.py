#!/usr/bin/env python3
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def require(ok,msg):
    if not ok: raise AssertionError(msg)
for name,mode in [('INICIAR_PLATAFORMA_LOCAL.bat','Local'),('INICIAR_PLATAFORMA_TUNEL_ONLINE.bat','Tunnel')]:
    data=(ROOT/name).read_bytes(); text=data.decode('ascii')
    require(b'\r\n' in data and b'\n' not in data.replace(b'\r\n',b''),f'{name} no usa CRLF uniforme')
    require(len(text.splitlines())<=12,f'{name} volvió a ser un BAT grande/frágil')
    require('iniciar_plataforma.ps1' in text and f'-Mode {mode}' in text,f'{name} no delega al launcher robusto')
    require('endloca' not in text.lower(),f'{name} contiene truncamiento')
ps=(ROOT/'scripts_windows/iniciar_plataforma.ps1').read_text(encoding='utf-8')
for token in ['backend\\app.py','frontend\\index.html','/api/health','DATABASE_URL','postgresql+psycopg://','backend.pid','TunnelBackend']:
    require(token in ps,f'launcher no contiene {token}')
tunnel=(ROOT/'scripts_windows/iniciar_tunel_cloudflare.ps1').read_text(encoding='utf-8')
require('-Mode TunnelBackend' in tunnel,'túnel no usa modo backend sin recursión')
argument=tunnel[tunnel.find('$cloudflaredArgs'):tunnel.find('# El proceso hereda')]
require('--config' not in argument,'Quick Tunnel usa --config')
for helper in ['CONFIGURAR_POSTGRESQL_LOCAL.bat','MIGRAR_SQLITE_A_POSTGRESQL.bat','RESPALDAR_POSTGRESQL.bat','RESTAURAR_POSTGRESQL.bat','DIAGNOSTICAR_INICIO_WINDOWS.bat']:
    require((ROOT/helper).is_file(),f'Falta {helper}')
print('Lanzadores Windows: PASS')

diag=(ROOT/'scripts_windows/diagnosticar_inicio_windows.ps1').read_text(encoding='utf-8')
for token in ['backend\\app.py','frontend\\index.html','puerto 5000','cloudflared.exe','pg_dump.exe','DIAGNOSTICO_INICIO_WINDOWS']:
    require(token in diag,f'diagnóstico Windows no contiene {token}')
