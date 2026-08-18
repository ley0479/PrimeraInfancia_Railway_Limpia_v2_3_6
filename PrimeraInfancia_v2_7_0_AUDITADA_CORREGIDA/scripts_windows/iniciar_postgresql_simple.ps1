#requires -version 5.1
$ErrorActionPreference = 'Stop'
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = (Resolve-Path (Split-Path -Parent $ScriptDir)).Path
$Python = Join-Path $Root 'backend\.venv\Scripts\python.exe'
$EnvFile = Join-Path $Root '.env'

if (-not (Test-Path $Python)) {
    throw 'No existe backend\.venv. Ejecuta una vez el instalador de dependencias del proyecto.'
}
if (-not (Test-Path $EnvFile)) { throw 'No existe el archivo .env.' }

$DatabaseLine = Get-Content $EnvFile | Where-Object { $_ -match '^\s*DATABASE_URL\s*=' } | Select-Object -First 1
if (-not $DatabaseLine) { throw 'Falta DATABASE_URL en .env.' }
$DatabaseUrl = ($DatabaseLine -split '=', 2)[1].Trim()
if ($DatabaseUrl -notmatch '^postgres(?:ql)?(?:\+psycopg)?://') {
    throw 'DATABASE_URL debe apuntar a PostgreSQL; SQLite está deshabilitado.'
}

$env:APP_ENV = 'development'
$env:FLASK_ENV = 'development'
$env:FLASK_HOST = '127.0.0.1'
$env:FLASK_PORT = '5000'
$env:DATABASE_URL = $DatabaseUrl
$Sha256 = [System.Security.Cryptography.SHA256]::Create()
$EnvStream = [System.IO.File]::OpenRead($EnvFile)
try {
    $env:PROJECT_ENV_SHA256 = ([System.BitConverter]::ToString($Sha256.ComputeHash($EnvStream))).Replace('-', '')
}
finally {
    $EnvStream.Dispose()
    $Sha256.Dispose()
}
$env:ENABLE_POSTGRESQL_RUNTIME = 'true'
$env:REQUIRE_POSTGRESQL_IN_PRODUCTION = 'true'
$env:SKIP_RUNTIME_SCHEMA_DDL = 'true'
$env:AUTH_LOGIN_DEBUG = 'true'
$env:FORCE_HTTPS = 'false'
$env:SESSION_COOKIE_SECURE = 'false'
$env:TRUSTED_PROXY_COUNT = '0'
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'

Write-Host 'Iniciando Primera Infancia con PostgreSQL...' -ForegroundColor Cyan
Write-Host 'URL local: http://127.0.0.1:5000/frontend/index.html' -ForegroundColor Green
Write-Host 'Cierra esta ventana para detener la plataforma.' -ForegroundColor Yellow
Push-Location (Join-Path $Root 'backend')
try { & $Python 'run_local_postgres.py' }
finally { Pop-Location }
