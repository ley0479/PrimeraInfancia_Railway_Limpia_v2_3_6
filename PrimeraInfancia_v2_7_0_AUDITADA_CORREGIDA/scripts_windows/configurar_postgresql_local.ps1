#requires -version 5.1
[CmdletBinding()]
param([string]$DatabaseUrl)
$ErrorActionPreference='Stop'
[Console]::OutputEncoding=[Text.Encoding]::UTF8
$ScriptDir=Split-Path -Parent $MyInvocation.MyCommand.Path
$Root=(Resolve-Path (Split-Path -Parent $ScriptDir)).Path
$Runtime=Join-Path $Root '.runtime_windows'
$VenvPython=Join-Path $Root 'backend\.venv\Scripts\python.exe'
if (-not (Test-Path $VenvPython)) { throw 'Primero ejecuta INICIAR_PLATAFORMA_LOCAL.bat para crear backend\.venv.' }
if ([string]::IsNullOrWhiteSpace($DatabaseUrl)) { $DatabaseUrl=Read-Host 'Pega DATABASE_URL de PostgreSQL (no se mostrará después en los logs)' }
$DatabaseUrl=$DatabaseUrl.Trim()
if ($DatabaseUrl.StartsWith('postgres://')) { $DatabaseUrl='postgresql+psycopg://'+$DatabaseUrl.Substring(11) }
elseif ($DatabaseUrl.StartsWith('postgresql://')) { $DatabaseUrl='postgresql+psycopg://'+$DatabaseUrl.Substring(13) }
if (-not $DatabaseUrl.StartsWith('postgresql+psycopg://')) { throw 'La URL debe comenzar con postgresql:// o postgresql+psycopg://.' }
New-Item -ItemType Directory -Force -Path $Runtime | Out-Null
$old=$env:DATABASE_URL
try {
  $env:DATABASE_URL=$DatabaseUrl
  & $VenvPython (Join-Path $Root 'backend\tools\check_database.py') --url $DatabaseUrl
  if ($LASTEXITCODE -ne 0) { throw 'No se pudo conectar a PostgreSQL.' }
  Set-Content -Path (Join-Path $Runtime 'database_url.local.txt') -Encoding UTF8 -NoNewline -Value $DatabaseUrl
  Write-Host 'PostgreSQL quedó configurado para esta copia local.' -ForegroundColor Green
  Write-Host 'Archivo privado: .runtime_windows\database_url.local.txt' -ForegroundColor DarkGray
} finally { if ($null -eq $old){Remove-Item Env:\DATABASE_URL -ErrorAction SilentlyContinue}else{$env:DATABASE_URL=$old} }
