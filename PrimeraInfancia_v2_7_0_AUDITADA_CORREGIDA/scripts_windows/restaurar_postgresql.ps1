#requires -version 5.1
[CmdletBinding()]
param([string]$DatabaseUrl,[string]$BackupFile)
$ErrorActionPreference='Stop'
$ScriptDir=Split-Path -Parent $MyInvocation.MyCommand.Path
$Root=(Resolve-Path (Split-Path -Parent $ScriptDir)).Path
$Runtime=Join-Path $Root '.runtime_windows'
if ([string]::IsNullOrWhiteSpace($DatabaseUrl)) { $f=Join-Path $Runtime 'database_url.local.txt'; if(Test-Path $f){$DatabaseUrl=(Get-Content $f -Raw).Trim()} }
if ([string]::IsNullOrWhiteSpace($DatabaseUrl)) { $DatabaseUrl=Read-Host 'Pega DATABASE_URL de PostgreSQL de destino' }
if ([string]::IsNullOrWhiteSpace($BackupFile)) { $BackupFile=Read-Host 'Ruta completa del archivo .dump' }
if (-not (Test-Path $BackupFile)) { throw "No existe $BackupFile" }
$DatabaseUrl=$DatabaseUrl -replace '^postgresql\+psycopg://','postgresql://'
$pgRestore=(Get-Command pg_restore.exe -ErrorAction SilentlyContinue)
if (-not $pgRestore) { throw 'No se encontró pg_restore.exe. Instala PostgreSQL Client Tools y agrégalo al PATH.' }
$answer=Read-Host 'Escribe RESTAURAR para reemplazar objetos de la base destino'
if ($answer -cne 'RESTAURAR') { throw 'Restauración cancelada.' }
& $pgRestore.Source --dbname=$DatabaseUrl --clean --if-exists --no-owner --no-acl --exit-on-error $BackupFile
if ($LASTEXITCODE -ne 0) { throw 'pg_restore terminó con error.' }
Write-Host 'Restauración terminada. Ejecuta init_hosting.py y las pruebas funcionales.' -ForegroundColor Green
