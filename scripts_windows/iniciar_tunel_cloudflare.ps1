#requires -version 5.1
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host '============================================================'
Write-Host '  PRIMERA INFANCIA v2.4.2 - TUNEL CLOUDFLARE VERIFICADO'
Write-Host '============================================================'
Write-Host ''

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
if (Test-Path (Join-Path $ScriptDir 'backend')) {
    $Root = $ScriptDir
} else {
    $Root = Split-Path -Parent $ScriptDir
}
$Root = (Resolve-Path $Root).Path
$LocalBase = 'http://127.0.0.1:5000'
$HealthUrl = "$LocalBase/api/health"
$LocalFrontend = "$LocalBase/frontend/index.html"
$RuntimeDir = Join-Path $Root '.runtime_windows'
$ApplicationLogDir = Join-Path $Root 'data\logs'
$TunnelLogDir = Join-Path $Root 'logs_tunel'
$ToolsDir = Join-Path $Root 'tools\cloudflared'
$LinkFile = Join-Path $Root 'ENLACE_PUBLICO_TUNEL.txt'
$PidFile = Join-Path $RuntimeDir 'cloudflared_tunnel.pid'
$QuickConfig = Join-Path $RuntimeDir 'cloudflared_quick_tunnel.yml'
New-Item -ItemType Directory -Force -Path $RuntimeDir, $ApplicationLogDir, $TunnelLogDir, $ToolsDir | Out-Null

function Get-ProjectInstanceId([string]$ProjectRoot) {
    $normalized = [IO.Path]::GetFullPath($ProjectRoot).TrimEnd([char[]]'\/').ToLowerInvariant()
    $sha = [Security.Cryptography.SHA256]::Create()
    try {
        $bytes = [Text.Encoding]::UTF8.GetBytes($normalized)
        return ([BitConverter]::ToString($sha.ComputeHash($bytes))).Replace('-', '').Substring(0, 16).ToLowerInvariant()
    } finally {
        $sha.Dispose()
    }
}

$ExpectedInstanceId = Get-ProjectInstanceId $Root
Set-Content -Path (Join-Path $RuntimeDir 'project_instance_id.txt') -Encoding ASCII -Value $ExpectedInstanceId

function Get-HealthInfo([string]$Url, [int]$TimeoutSeconds = 4) {
    try {
        return Invoke-RestMethod -Uri $Url -TimeoutSec $TimeoutSeconds -MaximumRedirection 5
    } catch {
        return $null
    }
}

function Test-HttpOk([string]$Url, [int]$TimeoutSeconds = 4) {
    try {
        $response = Invoke-WebRequest -UseBasicParsing -Uri $Url -TimeoutSec $TimeoutSeconds -MaximumRedirection 5
        return ($response.StatusCode -ge 200 -and $response.StatusCode -lt 400)
    } catch {
        return $false
    }
}

function Test-ExpectedBackend($Info, [bool]$RequireTunnelMode = $true) {
    if (-not $Info) { return $false }
    if ([string]$Info.status -ne 'ok') { return $false }
    if ([string]$Info.project_instance_id -ne $ExpectedInstanceId) { return $false }
    if ($RequireTunnelMode -and $Info.public_tunnel_mode -ne $true) { return $false }
    return $true
}

function Get-Port5000Pids {
    $values = New-Object System.Collections.Generic.List[int]
    try {
        $listeners = Get-NetTCPConnection -LocalPort 5000 -State Listen -ErrorAction SilentlyContinue
        foreach ($listener in $listeners) {
            if ($listener.OwningProcess -gt 0 -and -not $values.Contains([int]$listener.OwningProcess)) {
                $values.Add([int]$listener.OwningProcess)
            }
        }
    } catch { }
    if ($values.Count -eq 0) {
        $lines = netstat -ano 2>$null | Select-String -Pattern ':5000\s+.*LISTENING\s+(\d+)$'
        foreach ($line in $lines) {
            $pidValue = [int]$line.Matches[0].Groups[1].Value
            if ($pidValue -gt 0 -and -not $values.Contains($pidValue)) { $values.Add($pidValue) }
        }
    }
    return @($values)
}

function Stop-Port5000Backend {
    $stopped = $false
    foreach ($pidValue in (Get-Port5000Pids)) {
        Write-Host "Cerrando backend verificado en puerto 5000 (PID $pidValue)..." -ForegroundColor Yellow
        Stop-Process -Id $pidValue -Force -ErrorAction SilentlyContinue
        $stopped = $true
    }
    if ($stopped) { Start-Sleep -Seconds 2 }
}

function Stop-VerifiedLocalBackend {
    # Alias conservado para regresión: solo se usa tras identificar /api/health.
    Stop-Port5000Backend
}

function Wait-ExpectedBackend([int]$Seconds = 100) {
    for ($i = 1; $i -le $Seconds; $i++) {
        $info = Get-HealthInfo $HealthUrl 3
        if (Test-ExpectedBackend $info $true) { return $info }
        Start-Sleep -Seconds 1
    }
    return $null
}

function Stop-PreviousProjectTunnel {
    if (-not (Test-Path $PidFile)) { return }
    $raw = (Get-Content -Path $PidFile -Raw -ErrorAction SilentlyContinue).Trim()
    $pidValue = 0
    if ([int]::TryParse($raw, [ref]$pidValue) -and $pidValue -gt 0) {
        $old = Get-Process -Id $pidValue -ErrorAction SilentlyContinue
        if ($old -and $old.ProcessName -like 'cloudflared*') {
            Write-Host "Cerrando tunel anterior de este proyecto (PID $pidValue)..." -ForegroundColor Yellow
            Stop-Process -Id $pidValue -Force -ErrorAction SilentlyContinue
            Start-Sleep -Seconds 1
        }
    }
    Remove-Item -Path $PidFile -Force -ErrorAction SilentlyContinue
}

function Stop-ActiveTunnel($Process) {
    if ($Process -and -not $Process.HasExited) {
        Stop-Process -Id $Process.Id -Force -ErrorAction SilentlyContinue
        try { $Process.WaitForExit(5000) | Out-Null } catch { }
    }
    Remove-Item -Path $PidFile -Force -ErrorAction SilentlyContinue
}

function Get-TunnelUrl([string[]]$Files) {
    $regex = 'https://[a-zA-Z0-9-]+\.trycloudflare\.com'
    foreach ($file in $Files) {
        if (-not (Test-Path $file)) { continue }
        $content = Get-Content -Path $file -Raw -ErrorAction SilentlyContinue
        if ($content -and $content -match $regex) {
            return $Matches[0].TrimEnd('/')
        }
    }
    return $null
}

function Show-LogTail([string[]]$Files) {
    foreach ($file in $Files) {
        if (-not (Test-Path $file)) { continue }
        Write-Host ''
        Write-Host "Ultimas lineas de $file" -ForegroundColor DarkGray
        Get-Content -Path $file -Tail 20 -ErrorAction SilentlyContinue | ForEach-Object { Write-Host $_ }
    }
}

Write-Host "Proyecto: $Root"
Write-Host "Instancia esperada: $ExpectedInstanceId"
Write-Host "URL local unificada: $LocalFrontend"
Write-Host "Logs de la aplicacion: $ApplicationLogDir"
Write-Host ''

# Es posible tener varias copias de PrimeraInfancia en el computador. Un health
# 200 no basta: se exige la misma huella de proyecto y el modo TUNEL_ONLINE.
$backendInfo = Get-HealthInfo $HealthUrl 4
if ($backendInfo) {
    $currentId = [string]$backendInfo.project_instance_id
    $currentVersion = [string]$backendInfo.version
    if ($currentId -ne $ExpectedInstanceId) {
        Write-Host '[AVISO] El puerto 5000 pertenece a otra copia de Primera Infancia.' -ForegroundColor Yellow
        Write-Host "        Instancia activa: $currentId  Version: $currentVersion"
        Write-Host "        Instancia solicitada: $ExpectedInstanceId"
        Write-Host 'Se cerrara únicamente ese backend para no publicar la base equivocada.' -ForegroundColor Yellow
        Stop-VerifiedLocalBackend
        $backendInfo = $null
    } elseif ($backendInfo.public_tunnel_mode -ne $true) {
        Write-Host 'La copia correcta esta abierta en modo LOCAL.' -ForegroundColor Yellow
        Write-Host 'Se reiniciara en modo TUNEL para usar la configuracion segura de proxy.' -ForegroundColor Yellow
        Stop-VerifiedLocalBackend
        $backendInfo = $null
    }
}

if (-not (Test-ExpectedBackend $backendInfo $true)) {
    Write-Host '[1/5] Iniciando esta copia en modo tunel...' -ForegroundColor Yellow
    $StartBat = Join-Path $Root 'INICIAR_PLATAFORMA_LOCAL.bat'
    if (-not (Test-Path $StartBat)) { throw "No existe $StartBat" }

    $oldNoPause = $env:PI_NO_PAUSE
    $oldTunnelMode = $env:PI_TUNNEL_MODE
    try {
        $env:PI_NO_PAUSE = '1'
        $env:PI_TUNNEL_MODE = '1'
        Start-Process -FilePath 'cmd.exe' -ArgumentList @('/c', "`"$StartBat`"") -WorkingDirectory $Root -Wait
    } finally {
        if ($null -eq $oldNoPause) { Remove-Item Env:\PI_NO_PAUSE -ErrorAction SilentlyContinue } else { $env:PI_NO_PAUSE = $oldNoPause }
        if ($null -eq $oldTunnelMode) { Remove-Item Env:\PI_TUNNEL_MODE -ErrorAction SilentlyContinue } else { $env:PI_TUNNEL_MODE = $oldTunnelMode }
    }

    Write-Host 'Esperando /api/health de la misma copia y en modo tunel...'
    $backendInfo = Wait-ExpectedBackend 100
    if (-not $backendInfo) {
        $seen = Get-HealthInfo $HealthUrl 3
        if ($seen) {
            throw "El puerto responde, pero no coincide con esta copia o no esta en modo tunel. Esperada=$ExpectedInstanceId, activa=$([string]$seen.project_instance_id), modo=$([string]$seen.public_tunnel_mode)."
        }
        throw "El backend local no respondio en $HealthUrl. Revisa la ventana del backend y $ApplicationLogDir."
    }
} else {
    Write-Host '[1/5] Backend correcto y en modo tunel.' -ForegroundColor Green
}

if (-not (Test-HttpOk $LocalFrontend 5)) {
    throw "El backend correcto responde, pero no pude abrir el frontend local en $LocalFrontend."
}
Write-Host "[2/5] Frontend local verificado. Version: $([string]$backendInfo.version)" -ForegroundColor Green

Write-Host '[3/5] Buscando cloudflared...'
$Cloudflared = $null
$cmd = Get-Command cloudflared -ErrorAction SilentlyContinue
if ($cmd) {
    $Cloudflared = $cmd.Source
} else {
    $Cloudflared = Join-Path $ToolsDir 'cloudflared.exe'
}

if (-not (Test-Path $Cloudflared)) {
    Write-Host 'cloudflared no esta instalado. Descargando el ejecutable oficial portable...' -ForegroundColor Yellow
    $downloadArch = if ($env:PROCESSOR_ARCHITECTURE -eq 'ARM64') { 'arm64' } else { 'amd64' }
    $DownloadUrl = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-$downloadArch.exe"
    try {
        Invoke-WebRequest -UseBasicParsing -Uri $DownloadUrl -OutFile $Cloudflared -TimeoutSec 120
        if ((Get-Item $Cloudflared).Length -lt 1MB) {
            Remove-Item $Cloudflared -Force -ErrorAction SilentlyContinue
            throw 'La descarga quedo incompleta.'
        }
    } catch {
        throw "No pude descargar cloudflared. Descargalo manualmente y ubicalo en: $Cloudflared`nDetalle: $($_.Exception.Message)"
    }
}

try {
    $CloudflaredVersion = (& $Cloudflared --version 2>&1 | Select-Object -First 1)
    if (-not $CloudflaredVersion) { throw 'No se recibio informacion de version.' }
    Write-Host "cloudflared: $CloudflaredVersion" -ForegroundColor Green
} catch {
    throw "El archivo cloudflared no se puede ejecutar: $($_.Exception.Message)"
}

Stop-PreviousProjectTunnel

# Una configuracion explicita y vacia impide que un config.yml personal del
# usuario convierta accidentalmente esta prueba en un tunel nombrado diferente.
Set-Content -Path $QuickConfig -Encoding ASCII -Value "{}"
$defaultConfigs = @(
    (Join-Path $HOME '.cloudflared\config.yml'),
    (Join-Path $HOME '.cloudflared\config.yaml')
) | Where-Object { Test-Path $_ }
if ($defaultConfigs.Count -gt 0) {
    Write-Host 'Se detecto una configuracion Cloudflare del usuario.' -ForegroundColor Yellow
    Write-Host 'Se usara una configuracion aislada sin modificar tus archivos.' -ForegroundColor Yellow
}

$Stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$CloudflaredLog = Join-Path $TunnelLogDir "cloudflared_$Stamp.log"
$StdOutLog = Join-Path $TunnelLogDir "cloudflared_$Stamp.stdout.log"
$StdErrLog = Join-Path $TunnelLogDir "cloudflared_$Stamp.stderr.log"
$allLogs = @($CloudflaredLog, $StdOutLog, $StdErrLog)

Set-Content -Path $LinkFile -Encoding UTF8 -Value "Generando enlace publico...`nFecha: $(Get-Date -Format s)`nLocal: $LocalFrontend`nInstancia: $ExpectedInstanceId`n"

Write-Host '[4/5] Iniciando Quick Tunnel Cloudflare hacia el puerto 5000...'
Write-Host '      Frontend y API quedaran bajo el mismo origen HTTPS.'
Write-Host ''

$args = @(
    'tunnel',
    '--config', ('"{0}"' -f $QuickConfig),
    '--url', $LocalBase,
    '--no-autoupdate',
    '--logfile', ('"{0}"' -f $CloudflaredLog),
    '--loglevel', 'info'
)

try {
    $proc = Start-Process -FilePath $Cloudflared -ArgumentList $args -PassThru -WindowStyle Hidden `
        -RedirectStandardOutput $StdOutLog -RedirectStandardError $StdErrLog
} catch {
    throw "No se pudo iniciar cloudflared: $($_.Exception.Message)"
}
Set-Content -Path $PidFile -Encoding ASCII -Value $proc.Id

$Url = $null
for ($i = 1; $i -le 120; $i++) {
    $proc.Refresh()
    $Url = Get-TunnelUrl $allLogs
    if ($Url) { break }
    if ($proc.HasExited) { break }
    Start-Sleep -Seconds 1
}

if (-not $Url) {
    Show-LogTail $allLogs
    Stop-ActiveTunnel $proc
    throw 'Cloudflare no genero el enlace trycloudflare.com. Revisa internet, antivirus, fecha/hora de Windows o bloqueo de la red.'
}

$PublicHealth = "$Url/api/health"
$FrontendPublic = "$Url/frontend/index.html"
$publicReady = $false
$publicInfo = $null
for ($i = 1; $i -le 60; $i++) {
    $publicInfo = Get-HealthInfo $PublicHealth 8
    if ((Test-ExpectedBackend $publicInfo $true) -and (Test-HttpOk $FrontendPublic 8)) {
        $publicReady = $true
        break
    }
    $proc.Refresh()
    if ($proc.HasExited) { break }
    Start-Sleep -Seconds 1
}

if (-not $publicReady) {
    Show-LogTail $allLogs
    Stop-ActiveTunnel $proc
    if ($publicInfo) {
        throw "El enlace publico responde, pero expone otra copia o modo. Esperada=$ExpectedInstanceId, publica=$([string]$publicInfo.project_instance_id), modo=$([string]$publicInfo.public_tunnel_mode)."
    }
    throw "Se genero $Url, pero /api/health y /frontend/index.html no quedaron disponibles."
}

$text = @"
ENLACE PUBLICO DE PRUEBAS
Fecha: $(Get-Date -Format s)
Frontend: $FrontendPublic
Base: $Url
Health: $PublicHealth
Local: $LocalFrontend
Instancia verificada: $ExpectedInstanceId
Version: $([string]$publicInfo.version)
PID cloudflared: $($proc.Id)
Logs aplicacion: $ApplicationLogDir
Logs tunel: $TunnelLogDir

IMPORTANTE:
- Comparte el enlace Frontend, nunca http://127.0.0.1:5000.
- El enlace es temporal y cambia al reiniciar el tunel.
- Mantén abiertas esta ventana y la ventana del backend.
- No compartas credenciales SUPERADMIN. Crea un usuario individual de pruebas.
- Si aparece un Error API, abre data\logs; backend\logs no es la carpeta operativa.
"@
Set-Content -Path $LinkFile -Encoding UTF8 -Value $text

try { Set-Clipboard -Value $FrontendPublic -ErrorAction Stop } catch { }

Write-Host '[5/5] Tunel listo, modo e instancia verificados.' -ForegroundColor Green
Write-Host ''
Write-Host "ENLACE PUBLICO: $FrontendPublic" -ForegroundColor Cyan
Write-Host "Instancia: $ExpectedInstanceId"
Write-Host "Guardado en: $LinkFile"
Write-Host "Logs de aplicacion: $ApplicationLogDir"
Write-Host "Logs de cloudflared: $TunnelLogDir"
Write-Host ''
Start-Process $FrontendPublic

Write-Host 'Mantén esta ventana abierta mientras estes probando el tunel.' -ForegroundColor Yellow
Write-Host 'Para cerrarlo, presiona Ctrl+C o ejecuta DETENER_PLATAFORMA_LOCAL.bat.'
Write-Host ''

try {
    Wait-Process -Id $proc.Id
} finally {
    Stop-ActiveTunnel $proc
}
