#requires -version 5.1
[CmdletBinding()]
param([string]$DatabaseUrl)
$ErrorActionPreference='Stop'
$ScriptDir=Split-Path -Parent $MyInvocation.MyCommand.Path
$Root=(Resolve-Path (Split-Path -Parent $ScriptDir)).Path
$Runtime=Join-Path $Root '.runtime_windows'; $Backups=Join-Path $Root 'data\backups'
New-Item -ItemType Directory -Force -Path $Backups | Out-Null
if ([string]::IsNullOrWhiteSpace($DatabaseUrl)) { $f=Join-Path $Runtime 'database_url.local.txt'; if(Test-Path $f){$DatabaseUrl=(Get-Content $f -Raw).Trim()} }
if ([string]::IsNullOrWhiteSpace($DatabaseUrl)) { $DatabaseUrl=Read-Host 'Pega DATABASE_URL de PostgreSQL' }
$DatabaseUrl=$DatabaseUrl -replace '^postgresql\+psycopg://','postgresql://'
$pgDump=(Get-Command pg_dump.exe -ErrorAction SilentlyContinue)
if (-not $pgDump) { throw 'No se encontró pg_dump.exe. Instala PostgreSQL Client Tools y agrégalo al PATH.' }
$out=Join-Path $Backups ("postgresql_{0}.dump" -f (Get-Date -Format 'yyyyMMdd_HHmmss'))
& $pgDump.Source --dbname=$DatabaseUrl --format=custom --no-owner --no-acl --file=$out
if ($LASTEXITCODE -ne 0) { throw 'pg_dump terminó con error.' }
$hash=(Get-FileHash $out -Algorithm SHA256).Hash.ToLowerInvariant(); Set-Content "$out.sha256" -Encoding ASCII -Value "$hash  $([IO.Path]::GetFileName($out))"
Write-Host "Respaldo creado: $out" -ForegroundColor Green
