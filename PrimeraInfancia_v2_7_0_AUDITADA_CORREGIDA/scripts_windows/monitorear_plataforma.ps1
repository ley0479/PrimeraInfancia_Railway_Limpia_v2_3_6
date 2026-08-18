[CmdletBinding()]
param([string]$Url='http://127.0.0.1:5000/api/ready',[int]$Intervalo=0)
$ErrorActionPreference='Stop'
$Root=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$Python=Join-Path $Root 'backend\.venv\Scripts\python.exe'
if(-not(Test-Path $Python)){throw 'No existe backend\.venv. Inicia la plataforma primero.'}
& $Python (Join-Path $Root 'backend\tools\runtime_monitor.py') --url $Url --interval $Intervalo --log (Join-Path $Root 'data\integrity\runtime_monitor.jsonl')
exit $LASTEXITCODE
