#requires -version 5.1
[CmdletBinding()]
param()
$ErrorActionPreference = 'Continue'
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = (Resolve-Path (Split-Path -Parent $ScriptDir)).Path
$Runtime = Join-Path $Root '.runtime_windows'
$Data = Join-Path $Root 'data'
New-Item -ItemType Directory -Force -Path $Runtime,$Data | Out-Null
$Report = Join-Path $Runtime ("DIAGNOSTICO_INICIO_WINDOWS_{0}.txt" -f (Get-Date -Format 'yyyyMMdd_HHmmss'))
$lines = New-Object System.Collections.Generic.List[string]
function Add-Line([string]$Text='') { $lines.Add($Text); Write-Host $Text }
function State([bool]$Ok,[string]$Label,[string]$Detail='') {
    $mark = if($Ok){'OK'}else{'FALLO'}
    Add-Line ("[{0}] {1}{2}" -f $mark,$Label,$(if($Detail){": $Detail"}else{''}))
}
function Mask-DatabaseUrl([string]$Url) {
    if([string]::IsNullOrWhiteSpace($Url)){ return '' }
    return ($Url -replace '://([^:@/]+):([^@/]+)@','://$1:***@')
}
Add-Line 'PRIMERA INFANCIA 2.6.0 - DIAGNOSTICO DE INICIO WINDOWS'
Add-Line ("Fecha: {0}" -f (Get-Date -Format s))
Add-Line ("Proyecto: {0}" -f $Root)
Add-Line ''
State (Test-Path (Join-Path $Root 'backend\app.py')) 'backend\app.py'
State (Test-Path (Join-Path $Root 'frontend\index.html')) 'frontend\index.html'
State (Test-Path (Join-Path $Root 'scripts_windows\iniciar_plataforma.ps1')) 'lanzador PowerShell'

$pythonFound=$false
foreach($candidate in @(@('py.exe','-3.12'),@('py.exe','-3.11'),@('python.exe',''))){
    try {
        $args=@(); if($candidate[1]){$args+=$candidate[1]}; $args+='--version'
        $value=& $candidate[0] @args 2>&1 | Select-Object -First 1
        if($LASTEXITCODE -eq 0 -and $value -match 'Python 3\.(11|12)\.'){
            State $true 'Python recomendado' ([string]$value); $pythonFound=$true; break
        }
    } catch { }
}
if(-not $pythonFound){State $false 'Python recomendado' 'Instala Python 3.11 o 3.12 y marca Add Python to PATH.'}
$VenvPython=Join-Path $Root 'backend\.venv\Scripts\python.exe'
State (Test-Path $VenvPython) 'entorno virtual' $VenvPython
$req=Join-Path $Root 'backend\requirements-production.txt'
State (Test-Path $req) 'requirements-production.txt'
try {
    $probe=Join-Path $Data ('.write_test_'+[guid]::NewGuid().ToString('N')+'.tmp')
    Set-Content -Path $probe -Encoding ASCII -Value 'ok'; Remove-Item $probe -Force
    State $true 'escritura en data'
} catch { State $false 'escritura en data' $_.Exception.Message }

$dbUrl=[string]$env:DATABASE_URL
$dbFile=Join-Path $Runtime 'database_url.local.txt'
if([string]::IsNullOrWhiteSpace($dbUrl) -and (Test-Path $dbFile)){$dbUrl=(Get-Content $dbFile -Raw).Trim()}
if([string]::IsNullOrWhiteSpace($dbUrl)){
    State $true 'base configurada' ('SQLite: '+(Join-Path $Data 'database.sqlite3'))
}else{
    State ($dbUrl -match '^postgres(ql)?(\+psycopg)?://') 'base configurada' (Mask-DatabaseUrl $dbUrl)
}

$pids=@()
try{$pids=@(Get-NetTCPConnection -LocalPort 5000 -State Listen -ErrorAction SilentlyContinue|Select-Object -ExpandProperty OwningProcess -Unique)}catch{}
if($pids.Count -eq 0){State $true 'puerto 5000' 'libre'}else{
    foreach($pidValue in $pids){
        $proc=Get-CimInstance Win32_Process -Filter "ProcessId=$pidValue" -ErrorAction SilentlyContinue
        State $false 'puerto 5000 ocupado' ("PID={0}; Ejecutable={1}; Comando={2}" -f $pidValue,$proc.ExecutablePath,$proc.CommandLine)
    }
}
try {
    $health=Invoke-RestMethod -Uri 'http://127.0.0.1:5000/api/health' -TimeoutSec 3
    State ([string]$health.status -eq 'ok') 'health local' ("version={0}; db={1}; instancia={2}; tunel={3}" -f $health.version,$health.database_backend,$health.project_instance_id,$health.public_tunnel_mode)
} catch { State $false 'health local' 'El backend no está respondiendo; esto es normal si aún no se ha iniciado.' }

$cloud=Join-Path $Root 'tools\cloudflared\cloudflared.exe'
if(Test-Path $cloud){
    try{$v=& $cloud --version 2>&1|Select-Object -First 1; State ($LASTEXITCODE -eq 0) 'cloudflared.exe' ([string]$v)}catch{State $false 'cloudflared.exe' $_.Exception.Message}
}else{State $false 'cloudflared.exe' 'Se descargará automáticamente al iniciar el túnel.'}
foreach($tool in @('pg_dump.exe','pg_restore.exe')){
    $cmd=Get-Command $tool -ErrorAction SilentlyContinue
    State ($null -ne $cmd) $tool $(if($cmd){$cmd.Source}else{'Solo es necesario para respaldo/restauración PostgreSQL local.'})
}
$latestLogs=@()
foreach($folder in @(Join-Path $Data 'logs', Join-Path $Root 'logs_tunel')){
    if(Test-Path $folder){$latestLogs+=Get-ChildItem $folder -File -ErrorAction SilentlyContinue|Where-Object Length -gt 0|Sort-Object LastWriteTime -Descending|Select-Object -First 5}
}
Add-Line ''
Add-Line 'Logs recientes no vacíos:'
if($latestLogs.Count){$latestLogs|ForEach-Object{Add-Line ("- {0} ({1} bytes, {2})" -f $_.FullName,$_.Length,$_.LastWriteTime)}}else{Add-Line '- Ninguno.'}
$lines | Set-Content -Path $Report -Encoding UTF8
Add-Line ''
Write-Host "Diagnóstico guardado en: $Report" -ForegroundColor Cyan
