[CmdletBinding(SupportsShouldProcess)]
param([switch]$Aplicar)
$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$Python = Join-Path $Root 'backend\.venv\Scripts\python.exe'
if (-not (Test-Path $Python)) { throw 'No existe backend\.venv. Ejecuta primero INICIAR_PLATAFORMA_LOCAL.bat.' }
$ReportDir = Join-Path $Root 'data\integrity'
New-Item -ItemType Directory -Force -Path $ReportDir | Out-Null
$Stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$ArgsList = @(
    (Join-Path $Root 'backend\tools\safe_repair.py'),
    '--root', $Root,
    '--report', (Join-Path $ReportDir "safe_repair_$Stamp.json")
)
if ($Aplicar) { $ArgsList += '--apply' }
& $Python @ArgsList
exit $LASTEXITCODE
