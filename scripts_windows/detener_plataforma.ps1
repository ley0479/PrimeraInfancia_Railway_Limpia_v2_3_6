#requires -version 5.1
[CmdletBinding()]
param([switch]$ForcePortFallback)
$ErrorActionPreference='Stop'
[Console]::OutputEncoding=[Text.Encoding]::UTF8
$ScriptDir=Split-Path -Parent $MyInvocation.MyCommand.Path
$Root=(Resolve-Path (Split-Path -Parent $ScriptDir)).Path
$Runtime=Join-Path $Root '.runtime_windows'

function Stop-RecordedProcess([string]$PidFile,[string]$ExpectedName) {
    if (-not (Test-Path $PidFile)) { return $false }
    $raw=(Get-Content $PidFile -Raw -ErrorAction SilentlyContinue).Trim()
    if ($raw -notmatch '^\d+$') { Remove-Item $PidFile -Force -ErrorAction SilentlyContinue; return $false }
    $pidValue=[int]$raw
    $proc=Get-Process -Id $pidValue -ErrorAction SilentlyContinue
    if (-not $proc) { Remove-Item $PidFile -Force -ErrorAction SilentlyContinue; return $false }
    $cmd=''
    try { $cmd=[string](Get-CimInstance Win32_Process -Filter "ProcessId=$pidValue").CommandLine } catch { }
    $belongs=$cmd -and ($cmd.IndexOf($Root,[StringComparison]::OrdinalIgnoreCase) -ge 0)
    $nameOk=(-not $ExpectedName) -or ($proc.ProcessName -like $ExpectedName)
    if ($belongs -and $nameOk) {
        Write-Host "Cerrando $($proc.ProcessName), PID $pidValue..." -ForegroundColor Yellow
        Stop-Process -Id $pidValue -Force -ErrorAction SilentlyContinue
        Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
        return $true
    }
    Write-Warning "No se cerró PID $pidValue porque no se pudo confirmar que pertenezca a esta carpeta."
    return $false
}

Write-Host '============================================================'
Write-Host ' PRIMERA INFANCIA 2.7.0 - CIERRE SEGURO'
Write-Host '============================================================'
$stopped=$false
$stopped = (Stop-RecordedProcess (Join-Path $Runtime 'cloudflared_tunnel.pid') 'cloudflared*') -or $stopped
$stopped = (Stop-RecordedProcess (Join-Path $Runtime 'backend.pid') 'powershell*') -or $stopped
Start-Sleep -Milliseconds 600

$health=$null
try { $health=Invoke-RestMethod 'http://127.0.0.1:5000/api/health' -TimeoutSec 2 } catch { }
if ($health) {
    $expected=''
    $idFile=Join-Path $Runtime 'project_instance_id.txt'
    if (Test-Path $idFile) { $expected=(Get-Content $idFile -Raw).Trim() }
    if ($expected -and [string]$health.project_instance_id -eq $expected) {
        $pids=@(Get-NetTCPConnection -LocalPort 5000 -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique)
        foreach($id in $pids) {
            $cmd=''; try{$cmd=[string](Get-CimInstance Win32_Process -Filter "ProcessId=$id").CommandLine}catch{}
            if ($cmd -and $cmd.IndexOf($Root,[StringComparison]::OrdinalIgnoreCase) -ge 0) {
                Write-Host "Cerrando backend confirmado, PID $id..." -ForegroundColor Yellow
                Stop-Process -Id $id -Force -ErrorAction SilentlyContinue; $stopped=$true
            }
        }
    } elseif ($ForcePortFallback) {
        Write-Warning 'El puerto 5000 responde, pero no pertenece a esta instancia. No se cerrará automáticamente.'
    }
}
if ($stopped) { Write-Host 'Procesos de esta copia cerrados.' -ForegroundColor Green }
else { Write-Host 'No se encontraron procesos confirmados de esta copia.' -ForegroundColor DarkYellow }
exit 0
