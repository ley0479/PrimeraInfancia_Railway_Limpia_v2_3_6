#requires -version 5.1
[CmdletBinding()]
param([string]$DatabaseUrl,[switch]$TruncateTarget)
$ErrorActionPreference='Stop'
[Console]::OutputEncoding=[Text.Encoding]::UTF8
$ScriptDir=Split-Path -Parent $MyInvocation.MyCommand.Path
$Root=(Resolve-Path (Split-Path -Parent $ScriptDir)).Path
$Runtime=Join-Path $Root '.runtime_windows'
$VenvPython=Join-Path $Root 'backend\.venv\Scripts\python.exe'
$Sqlite=Join-Path $Root 'data\database.sqlite3'
if (-not (Test-Path $VenvPython)) { throw 'Primero ejecuta el inicio local para crear backend\.venv.' }
if (-not (Test-Path $Sqlite)) { throw "No existe la base SQLite de origen: $Sqlite" }
if ([string]::IsNullOrWhiteSpace($DatabaseUrl)) {
  $urlFile=Join-Path $Runtime 'database_url.local.txt'
  if (Test-Path $urlFile) { $DatabaseUrl=(Get-Content $urlFile -Raw).Trim() }
}
if ([string]::IsNullOrWhiteSpace($DatabaseUrl)) { $DatabaseUrl=Read-Host 'Pega la URL PostgreSQL de destino' }
if ($DatabaseUrl.StartsWith('postgres://')) { $DatabaseUrl='postgresql+psycopg://'+$DatabaseUrl.Substring(11) }
elseif ($DatabaseUrl.StartsWith('postgresql://')) { $DatabaseUrl='postgresql+psycopg://'+$DatabaseUrl.Substring(13) }
$answer=Read-Host 'Escribe MIGRAR para crear respaldo y copiar SQLite a PostgreSQL'
if ($answer -cne 'MIGRAR') { throw 'Migración cancelada.' }
$report=Join-Path $Runtime ("migracion_sqlite_postgresql_{0}.json" -f (Get-Date -Format 'yyyyMMdd_HHmmss'))
$args=@((Join-Path $Root 'backend\tools\migrate_sqlite_to_postgresql.py'),'--sqlite',$Sqlite,'--postgres',$DatabaseUrl,'--report',$report)
if ($TruncateTarget) { $args += '--truncate-target' }
& $VenvPython @args
if ($LASTEXITCODE -ne 0) { throw 'La migración terminó con error. Revisa el reporte y no cambies el origen.' }
Write-Host "Migración terminada. Reporte: $report" -ForegroundColor Green
