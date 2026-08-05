#requires -version 5.1
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
if (Test-Path (Join-Path $ScriptDir 'backend')) { $Root = $ScriptDir } else { $Root = Split-Path -Parent $ScriptDir }
$Root = (Resolve-Path $Root).Path
$RuntimeDir = Join-Path $Root '.runtime_windows'
$LogDir = Join-Path $Root 'data\logs'
$LegacyLogDir = Join-Path $Root 'backend\logs'
$LinkFile = Join-Path $Root 'ENLACE_PUBLICO_TUNEL.txt'
New-Item -ItemType Directory -Force -Path $RuntimeDir, $LogDir | Out-Null
$Stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$ReportFile = Join-Path $RuntimeDir "DIAGNOSTICO_TUNEL_LOGIN_$Stamp.txt"
$Lines = New-Object System.Collections.Generic.List[string]

function Add-Report([string]$Text = '') {
    $Lines.Add($Text)
    Write-Host $Text
}

function Get-ProjectInstanceId([string]$ProjectRoot) {
    $normalized = [IO.Path]::GetFullPath($ProjectRoot).TrimEnd([char[]]'\/').ToLowerInvariant()
    $sha = [Security.Cryptography.SHA256]::Create()
    try {
        $bytes = [Text.Encoding]::UTF8.GetBytes($normalized)
        return ([BitConverter]::ToString($sha.ComputeHash($bytes))).Replace('-', '').Substring(0, 16).ToLowerInvariant()
    } finally { $sha.Dispose() }
}

function Get-Health([string]$Url) {
    try { return Invoke-RestMethod -Uri $Url -TimeoutSec 8 -MaximumRedirection 5 } catch { return $null }
}

function Get-HttpStatus([string]$Url, [string]$Method = 'GET', [string]$Body = '') {
    try {
        $params = @{ Uri = $Url; Method = $Method; TimeoutSec = 8; UseBasicParsing = $true; MaximumRedirection = 5 }
        if ($Method -eq 'POST') {
            $params['ContentType'] = 'application/json'
            $params['Body'] = $Body
            $params['Headers'] = @{ 'X-Client-Request-ID' = "diag-$Stamp" }
        }
        $response = Invoke-WebRequest @params
        return [int]$response.StatusCode
    } catch {
        try { return [int]$_.Exception.Response.StatusCode.value__ } catch { return 0 }
    }
}

function Find-PublicBase {
    if (-not (Test-Path $LinkFile)) { return $null }
    $raw = Get-Content -Path $LinkFile -Raw -ErrorAction SilentlyContinue
    if ($raw -match 'https://[a-zA-Z0-9-]+\.trycloudflare\.com') { return $Matches[0].TrimEnd('/') }
    return $null
}

$ExpectedId = Get-ProjectInstanceId $Root
Add-Report 'PRIMERA INFANCIA - DIAGNOSTICO DE LOGIN POR TUNEL'
Add-Report '================================================='
Add-Report "Fecha: $(Get-Date -Format s)"
Add-Report "Proyecto: $Root"
Add-Report "Instancia esperada: $ExpectedId"
Add-Report "Logs reales: $LogDir"
Add-Report ''

$LocalHealthUrl = 'http://127.0.0.1:5000/api/health'
$local = Get-Health $LocalHealthUrl
if (-not $local) {
    Add-Report '[FALLO] El backend local no responde en /api/health.'
} else {
    Add-Report "[OK] Health local: estado=$($local.status), version=$($local.version), instancia=$($local.project_instance_id), tunel=$($local.public_tunnel_mode)"
    if ([string]$local.project_instance_id -ne $ExpectedId) {
        Add-Report '[FALLO] El puerto 5000 pertenece a otra copia del proyecto.'
    } elseif ($local.public_tunnel_mode -ne $true) {
        Add-Report '[AVISO] La copia correcta esta en modo LOCAL, no en modo TUNEL_ONLINE.'
    } else {
        Add-Report '[OK] Copia local e instancia correctas para tunel.'
    }
    $localLoginStatus = Get-HttpStatus 'http://127.0.0.1:5000/api/auth/login' 'POST' '{}'
    Add-Report "Prueba segura de ruta login local (sin credenciales): HTTP $localLoginStatus; esperado=400."
}

$PublicBase = Find-PublicBase
if (-not $PublicBase) {
    Add-Report '[AVISO] No se encontro un enlace trycloudflare.com en ENLACE_PUBLICO_TUNEL.txt.'
} else {
    $public = Get-Health "$PublicBase/api/health"
    if (-not $public) {
        Add-Report "[FALLO] El enlace publico no responde: $PublicBase"
    } else {
        Add-Report "[OK] Health publico: estado=$($public.status), version=$($public.version), instancia=$($public.project_instance_id), tunel=$($public.public_tunnel_mode)"
        if ([string]$public.project_instance_id -ne $ExpectedId) {
            Add-Report '[FALLO] El tunel esta publicando otra copia del proyecto.'
        } elseif ($public.public_tunnel_mode -ne $true) {
            Add-Report '[FALLO] El enlace publica un backend que no esta en modo tunel.'
        } else {
            Add-Report '[OK] El enlace publica la copia y el modo correctos.'
        }
        $publicLoginStatus = Get-HttpStatus "$PublicBase/api/auth/login" 'POST' '{}'
        Add-Report "Prueba segura de ruta login publica (sin credenciales): HTTP $publicLoginStatus; esperado=400."
    }
}

$probe = Join-Path $LogDir ".diagnostic_probe_$PID"
try {
    Set-Content -Path $probe -Encoding UTF8 -Value 'ok'
    if ((Get-Item $probe).Length -gt 0) { Add-Report '[OK] data\logs es escribible.' } else { Add-Report '[FALLO] La prueba de escritura quedo vacia.' }
} catch {
    Add-Report "[FALLO] No se puede escribir en data\logs: $($_.Exception.Message)"
} finally {
    Remove-Item $probe -Force -ErrorAction SilentlyContinue
}

if (Test-Path $LegacyLogDir) {
    Add-Report '[INFO] backend\logs es un marcador del repositorio; los errores de ejecucion están en data\logs.'
}

$recent = Get-ChildItem -Path $LogDir -Filter 'error_api_*.log' -File -ErrorAction SilentlyContinue |
    Where-Object { $_.Length -gt 0 } | Sort-Object LastWriteTime -Descending | Select-Object -First 10
if ($recent) {
    Add-Report 'Errores API recientes no vacios:'
    foreach ($item in $recent) { Add-Report ("- {0} | {1} bytes | {2}" -f $item.Name, $item.Length, $item.LastWriteTime.ToString('s')) }
} else {
    Add-Report 'No hay reportes error_api no vacios en data\logs.'
}

$applicationLog = Join-Path $LogDir 'application.log'
if (Test-Path $applicationLog) {
    Add-Report "application.log: $((Get-Item $applicationLog).Length) bytes"
}

Add-Report ''
Add-Report "Reporte guardado en: $ReportFile"
$Lines | Set-Content -Path $ReportFile -Encoding UTF8
