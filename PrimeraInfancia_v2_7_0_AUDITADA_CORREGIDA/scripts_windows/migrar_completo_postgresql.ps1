#requires -version 5.1
[CmdletBinding()]
param(
    [string]$DatabaseUrl,
    [switch]$VerifyExisting,
    [switch]$TruncateTarget,
    [switch]$DoNotActivate
)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = (Resolve-Path (Split-Path -Parent $ScriptDir)).Path
$Runtime = Join-Path $Root '.runtime_windows'
$Python = Join-Path $Root 'backend\.venv\Scripts\python.exe'
$Sqlite = Join-Path $Root 'data\database.sqlite3'
$UrlFile = Join-Path $Runtime 'database_url.local.txt'

if (-not (Test-Path $Python)) { throw 'Primero ejecuta INICIAR_PLATAFORMA_LOCAL.bat para crear backend\.venv.' }
if (-not (Test-Path $Sqlite)) { throw "No existe la base SQLite de origen: $Sqlite" }
New-Item -ItemType Directory -Force -Path $Runtime | Out-Null

if ([string]::IsNullOrWhiteSpace($DatabaseUrl) -and (Test-Path $UrlFile)) {
    $DatabaseUrl = (Get-Content $UrlFile -Raw).Trim()
}
if ([string]::IsNullOrWhiteSpace($DatabaseUrl)) {
    $DatabaseUrl = Read-Host 'Pega la URL PostgreSQL de destino'
}
$DatabaseUrl = $DatabaseUrl.Trim()
if ($DatabaseUrl.StartsWith('postgres://')) { $DatabaseUrl = 'postgresql+psycopg://' + $DatabaseUrl.Substring(11) }
elseif ($DatabaseUrl.StartsWith('postgresql://')) { $DatabaseUrl = 'postgresql+psycopg://' + $DatabaseUrl.Substring(13) }
if (-not $DatabaseUrl.StartsWith('postgresql+psycopg://')) { throw 'La URL debe ser PostgreSQL.' }

$confirmation = if ($VerifyExisting) { 'VERIFICAR' } elseif ($TruncateTarget) { 'TRUNCAR Y MIGRAR' } else { 'MIGRAR COMPLETO' }
$answer = Read-Host "Escribe exactamente '$confirmation' para continuar"
if ($answer -cne $confirmation) { throw 'Operación cancelada.' }

$ReportDir = Join-Path $Runtime ('cutover_postgresql_' + (Get-Date -Format 'yyyyMMdd_HHmmss'))
$args = @(
    (Join-Path $Root 'backend\tools\postgresql_cutover.py'),
    '--sqlite', $Sqlite,
    '--postgres', $DatabaseUrl,
    '--report-dir', $ReportDir
)
if ($VerifyExisting) { $args += '--verify-existing' }
if ($TruncateTarget) { $args += '--truncate-target' }
if (-not $DoNotActivate -and -not $VerifyExisting) { $args += @('--activate-env-file', $UrlFile) }

& $Python @args
if ($LASTEXITCODE -ne 0) {
    throw "El corte quedó BLOQUEADO. La base SQLite no fue eliminada. Revisa: $ReportDir"
}
Write-Host "PostgreSQL quedó verificado. Reportes: $ReportDir" -ForegroundColor Green
if (-not $DoNotActivate -and -not $VerifyExisting) {
    Write-Host 'La URL verificada quedó activa para esta copia local en .runtime_windows\database_url.local.txt.' -ForegroundColor Green
}
Write-Host 'Conserva data\database.sqlite3 hasta aprobar respaldo, restauración y pruebas funcionales.' -ForegroundColor Yellow
