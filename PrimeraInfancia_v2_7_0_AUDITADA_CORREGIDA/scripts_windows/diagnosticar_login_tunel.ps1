#requires -version 5.1
$ErrorActionPreference = 'Continue'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
try { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 } catch { }

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
if (Test-Path (Join-Path $ScriptDir 'backend')) { $Root = $ScriptDir } else { $Root = Split-Path -Parent $ScriptDir }
$Root = (Resolve-Path $Root).Path
$RuntimeDir = Join-Path $Root '.runtime_windows'
$LogDir = Join-Path $Root 'data\logs'
$LegacyLogDir = Join-Path $Root 'backend\logs'
$TunnelLogDir = Join-Path $Root 'logs_tunel'
$ToolsDir = Join-Path $Root 'tools\cloudflared'
$LinkFile = Join-Path $Root 'ENLACE_PUBLICO_TUNEL.txt'
$PidFile = Join-Path $RuntimeDir 'cloudflared_tunnel.pid'
New-Item -ItemType Directory -Force -Path $RuntimeDir, $LogDir, $TunnelLogDir | Out-Null
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

function Invoke-CurlText([string]$Url, [int]$TimeoutSeconds = 8) {
    $curl = Get-Command curl.exe -ErrorAction SilentlyContinue
    if (-not $curl) { return $null }
    try {
        $output = & $curl.Source '--silent' '--show-error' '--fail' '--location' '--max-time' ([string]$TimeoutSeconds) $Url 2>$null
        if ($LASTEXITCODE -eq 0 -and $output) { return ($output -join "`n") }
    } catch { }
    return $null
}

function Get-Health([string]$Url) {
    try { return Invoke-RestMethod -Uri $Url -TimeoutSec 8 -MaximumRedirection 5 } catch {
        $raw = Invoke-CurlText $Url 8
        if ($raw) { try { return $raw | ConvertFrom-Json } catch { } }
        return $null
    }
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

function Get-CloudflaredPath {
    $portable = Join-Path $ToolsDir 'cloudflared.exe'
    if (Test-Path $portable) { return $portable }
    $global = Get-Command cloudflared -ErrorAction SilentlyContinue
    if ($global) { return $global.Source }
    return $null
}

function Add-TunnelLogAnalysis {
    $recentLogs = Get-ChildItem -Path $TunnelLogDir -Filter 'cloudflared_*.log' -File -ErrorAction SilentlyContinue |
        Where-Object { $_.Length -gt 0 } | Sort-Object LastWriteTime -Descending | Select-Object -First 6
    if (-not $recentLogs) {
        Add-Report '[AVISO] No hay logs no vacíos de cloudflared en logs_tunel.'
        return
    }
    Add-Report 'Logs recientes de cloudflared:'
    foreach ($item in $recentLogs) { Add-Report ("- {0} | {1} bytes | {2}" -f $item.Name, $item.Length, $item.LastWriteTime.ToString('s')) }
    $raw = ($recentLogs | ForEach-Object { Get-Content $_.FullName -Raw -ErrorAction SilentlyContinue }) -join "`n"
    if ($raw -match 'https://[a-zA-Z0-9-]+\.trycloudflare\.com') { Add-Report "[OK] cloudflared generó URL: $($Matches[0])" }
    if ($raw -match '(?i)failed to dial a quic connection|quic.*timeout|handshake did not complete') { Add-Report '[DIAGNOSTICO] QUIC/UDP parece bloqueado; la versión 2.5.4 reintenta con HTTP/2/TCP.' }
    if ($raw -match '(?i)connection refused|unable to reach the origin service|connectex.*refused') { Add-Report '[DIAGNOSTICO] cloudflared no pudo llegar al origen http://127.0.0.1:5000.' }
    if ($raw -match '(?i)no such host|server misbehaving|lookup .* failed') { Add-Report '[DIAGNOSTICO] Fallo de DNS al contactar Cloudflare.' }
    if ($raw -match '(?i)config\.ya?ml|configuration file') { Add-Report '[DIAGNOSTICO] Interferencia de config.yml/config.yaml. Use la versión 2.5.4, que aísla el perfil y no pasa --config.' }
}

$ExpectedId = Get-ProjectInstanceId $Root
Add-Report 'PRIMERA INFANCIA 2.7.0 - DIAGNOSTICO DE TUNEL Y LOGIN'
Add-Report '=========================================================='
Add-Report "Fecha: $(Get-Date -Format s)"
Add-Report "Proyecto: $Root"
Add-Report "Instancia esperada: $ExpectedId"
Add-Report "Logs aplicación: $LogDir"
Add-Report "Logs cloudflared: $TunnelLogDir"
Add-Report ''

$cloudflared = Get-CloudflaredPath
if (-not $cloudflared) {
    Add-Report '[FALLO] No se encontró cloudflared.exe portable ni una instalación global.'
} else {
    try {
        $version = (& $cloudflared --version 2>&1 | Select-Object -First 1)
        Add-Report "[OK] cloudflared: $version"
    } catch { Add-Report "[FALLO] cloudflared no se puede ejecutar: $($_.Exception.Message)" }
}

$personalConfig = @(
    (Join-Path ([Environment]::GetFolderPath('UserProfile')) '.cloudflared\config.yml'),
    (Join-Path ([Environment]::GetFolderPath('UserProfile')) '.cloudflared\config.yaml')
) | Where-Object { $_ -and (Test-Path $_) }
if ($personalConfig.Count -gt 0) {
    Add-Report '[INFO] Existe una configuración personal de Cloudflare. La versión 2.5.4 no la modifica y usa HOME/USERPROFILE aislado.'
    foreach ($item in $personalConfig) { Add-Report "- $item" }
}

if (Test-Path $PidFile) {
    $pidText = (Get-Content $PidFile -Raw -ErrorAction SilentlyContinue).Trim()
    $process = $null
    if ($pidText -match '^\d+$') { $process = Get-Process -Id ([int]$pidText) -ErrorAction SilentlyContinue }
    if ($process -and $process.ProcessName -like 'cloudflared*') { Add-Report "[OK] Proceso cloudflared activo: PID $pidText" }
    else { Add-Report '[AVISO] El archivo PID existe, pero el proceso cloudflared ya no está activo.' }
} else {
    Add-Report '[AVISO] No existe PID de un túnel activo para esta copia.'
}

try {
    $tcp7844 = Test-NetConnection -ComputerName 'region1.v2.argotunnel.com' -Port 7844 -InformationLevel Quiet -WarningAction SilentlyContinue
    if ($tcp7844) { Add-Report '[OK] Salida TCP al puerto 7844 disponible.' } else { Add-Report '[AVISO] No respondió la prueba TCP 7844; revisa firewall, antivirus o red.' }
} catch { Add-Report '[INFO] Test-NetConnection no estuvo disponible para comprobar TCP 7844.' }

$LocalHealthUrl = 'http://127.0.0.1:5000/api/health'
$local = Get-Health $LocalHealthUrl
if (-not $local) {
    Add-Report '[FALLO] El backend local no responde en /api/health.'
} else {
    Add-Report "[OK] Health local: estado=$($local.status), version=$($local.version), instancia=$($local.project_instance_id), tunel=$($local.public_tunnel_mode)"
    if ([string]$local.project_instance_id -ne $ExpectedId) { Add-Report '[FALLO] El puerto 5000 pertenece a otra copia del proyecto.' }
    elseif ($local.public_tunnel_mode -ne $true) { Add-Report '[AVISO] La copia correcta está en modo LOCAL, no en TUNEL_ONLINE.' }
    else { Add-Report '[OK] Copia local e instancia correctas para túnel.' }
    $localLoginStatus = Get-HttpStatus 'http://127.0.0.1:5000/api/auth/login' 'POST' '{}'
    Add-Report "Prueba segura de ruta login local sin credenciales: HTTP $localLoginStatus; esperado=400."
}

$PublicBase = Find-PublicBase
if (-not $PublicBase) {
    Add-Report '[AVISO] No se encontró enlace trycloudflare.com verificado en ENLACE_PUBLICO_TUNEL.txt.'
} else {
    Add-Report "Enlace registrado: $PublicBase"
    $public = Get-Health "$PublicBase/api/health"
    if (-not $public) {
        Add-Report "[FALLO] El enlace público no responde: $PublicBase"
    } else {
        Add-Report "[OK] Health público: estado=$($public.status), version=$($public.version), instancia=$($public.project_instance_id), tunel=$($public.public_tunnel_mode)"
        if ([string]$public.project_instance_id -ne $ExpectedId) { Add-Report '[FALLO] El túnel está publicando otra copia del proyecto.' }
        elseif ($public.public_tunnel_mode -ne $true) { Add-Report '[FALLO] El enlace publica un backend que no está en modo túnel.' }
        else { Add-Report '[OK] El enlace publica la copia y el modo correctos.' }
        $publicLoginStatus = Get-HttpStatus "$PublicBase/api/auth/login" 'POST' '{}'
        Add-Report "Prueba segura de ruta login pública sin credenciales: HTTP $publicLoginStatus; esperado=400."
    }
}

$probe = Join-Path $LogDir ".diagnostic_probe_$PID"
try {
    Set-Content -Path $probe -Encoding UTF8 -Value 'ok'
    if ((Get-Item $probe).Length -gt 0) { Add-Report '[OK] data\logs es escribible.' } else { Add-Report '[FALLO] La prueba de escritura quedó vacía.' }
} catch { Add-Report "[FALLO] No se puede escribir en data\logs: $($_.Exception.Message)" }
finally { Remove-Item $probe -Force -ErrorAction SilentlyContinue }

if (Test-Path $LegacyLogDir) { Add-Report '[INFO] backend\logs es un marcador; los errores de ejecución están en data\logs.' }
$recent = Get-ChildItem -Path $LogDir -Filter 'error_api_*.log' -File -ErrorAction SilentlyContinue |
    Where-Object { $_.Length -gt 0 } | Sort-Object LastWriteTime -Descending | Select-Object -First 10
if ($recent) {
    Add-Report 'Errores API recientes no vacíos:'
    foreach ($item in $recent) { Add-Report ("- {0} | {1} bytes | {2}" -f $item.Name, $item.Length, $item.LastWriteTime.ToString('s')) }
} else { Add-Report 'No hay reportes error_api no vacíos en data\logs.' }

Add-TunnelLogAnalysis
Add-Report ''
Add-Report 'Recomendación: ejecuta INICIAR_PLATAFORMA_TUNEL_ONLINE.bat desde esta misma carpeta. No uses un enlace de una ejecución anterior.'
Add-Report "Reporte guardado en: $ReportFile"
$Lines | Set-Content -Path $ReportFile -Encoding UTF8
