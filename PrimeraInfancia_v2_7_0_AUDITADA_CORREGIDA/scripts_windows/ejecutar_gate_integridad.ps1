[CmdletBinding()]
param(
    [switch]$Rapido,
    [switch]$SinManifiesto
)
$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$Python = Join-Path $Root 'backend\.venv\Scripts\python.exe'
if (-not (Test-Path $Python)) { throw 'No existe backend\.venv. Ejecuta primero INICIAR_PLATAFORMA_LOCAL.bat.' }
$ReportDir = Join-Path $Root 'data\integrity'
New-Item -ItemType Directory -Force -Path $ReportDir | Out-Null
$Stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$ArgsList = @(
    (Join-Path $Root 'backend\tools\integrity_gate.py'),
    '--root', $Root,
    '--report', (Join-Path $ReportDir "integrity_gate_$Stamp.json")
)
if ($Rapido) { $ArgsList += '--skip-tests' }
if ($SinManifiesto) { $ArgsList += '--skip-manifest' }
& $Python @ArgsList
exit $LASTEXITCODE
