#requires -version 5.1
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
try {
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
} catch { }

Write-Host '============================================================'
Write-Host '  PRIMERA INFANCIA v2.7.0 - TUNEL CLOUDFLARE Y POSTGRESQL'
Write-Host '  Genera un enlace temporal HTTPS en trycloudflare.com'
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
$CloudflaredHome = Join-Path $RuntimeDir 'cloudflared_home_aislado'
$CloudflaredConfigDir = Join-Path $CloudflaredHome '.cloudflared'
New-Item -ItemType Directory -Force -Path $RuntimeDir, $ApplicationLogDir, $TunnelLogDir, $ToolsDir, $CloudflaredConfigDir | Out-Null

# Quick Tunnel no necesita ni admite la configuración de un túnel nombrado.
# Se usa un perfil aislado, sin --config, y se eliminan únicamente archivos
# config.yml/config.yaml generados dentro de este proyecto.
Remove-Item -Path (Join-Path $CloudflaredConfigDir 'config.yml') -Force -ErrorAction SilentlyContinue
Remove-Item -Path (Join-Path $CloudflaredConfigDir 'config.yaml') -Force -ErrorAction SilentlyContinue
Remove-Item -Path $LinkFile -Force -ErrorAction SilentlyContinue
$PersonalCloudflaredConfigs = @(
    (Join-Path ([Environment]::GetFolderPath('UserProfile')) '.cloudflared\config.yml'),
    (Join-Path ([Environment]::GetFolderPath('UserProfile')) '.cloudflared\config.yaml')
) | Where-Object { $_ -and (Test-Path $_) }

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

function Invoke-CurlText([string]$Url, [int]$TimeoutSeconds = 8) {
    $curl = Get-Command curl.exe -ErrorAction SilentlyContinue
    if (-not $curl) { return $null }
    try {
        $output = & $curl.Source '--silent' '--show-error' '--fail' '--location' '--max-time' ([string]$TimeoutSeconds) $Url 2>$null
        if ($LASTEXITCODE -eq 0 -and $output) {
            return ($output -join "`n")
        }
    } catch { }
    return $null
}

function Invoke-CurlDownload([string]$Url, [string]$Destination, [int]$TimeoutSeconds = 180) {
    $curl = Get-Command curl.exe -ErrorAction SilentlyContinue
    if (-not $curl) { return $false }
    try {
        & $curl.Source '--fail' '--location' '--show-error' '--silent' '--max-time' ([string]$TimeoutSeconds) '--output' $Destination $Url
        return ($LASTEXITCODE -eq 0 -and (Test-Path $Destination))
    } catch {
        return $false
    }
}

function Get-HealthInfo([string]$Url, [int]$TimeoutSeconds = 4) {
    try {
        return Invoke-RestMethod -Uri $Url -TimeoutSec $TimeoutSeconds -MaximumRedirection 5
    } catch {
        $raw = Invoke-CurlText $Url $TimeoutSeconds
        if ($raw) {
            try { return $raw | ConvertFrom-Json } catch { }
        }
        return $null
    }
}

function Test-HttpOk([string]$Url, [int]$TimeoutSeconds = 4) {
    try {
        $response = Invoke-WebRequest -UseBasicParsing -Uri $Url -TimeoutSec $TimeoutSeconds -MaximumRedirection 5
        return ($response.StatusCode -ge 200 -and $response.StatusCode -lt 400)
    } catch {
        $raw = Invoke-CurlText $Url $TimeoutSeconds
        return [bool]$raw
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
        Get-Content -Path $file -Tail 30 -ErrorAction SilentlyContinue | ForEach-Object { Write-Host $_ }
    }
}

function Get-LogText([string[]]$Files) {
    $parts = New-Object System.Collections.Generic.List[string]
    foreach ($file in $Files) {
        if (Test-Path $file) {
            $raw = Get-Content -Path $file -Raw -ErrorAction SilentlyContinue
            if ($raw) { $parts.Add($raw) }
        }
    }
    return ($parts -join "`n")
}

function Show-NetworkHints([string[]]$Files) {
    $raw = Get-LogText $Files
    if ($raw -match '(?i)failed to dial a quic connection|quic.*timeout|handshake did not complete') {
        Write-Host '[DIAGNOSTICO] La red parece bloquear QUIC/UDP 7844. Se intentara HTTP/2/TCP.' -ForegroundColor Yellow
    }
    if ($raw -match '(?i)connection refused|unable to reach the origin service|connectex.*refused') {
        Write-Host '[DIAGNOSTICO] Cloudflare no puede llegar a http://127.0.0.1:5000. Verifica que el backend siga abierto.' -ForegroundColor Yellow
    }
    if ($raw -match '(?i)no such host|server misbehaving|dns|lookup .* failed') {
        Write-Host '[DIAGNOSTICO] Hay un problema de DNS. Prueba otra red o configura DNS 1.1.1.1/8.8.8.8.' -ForegroundColor Yellow
    }
    if ($raw -match '(?i)config\.ya?ml|configuration file') {
        Write-Host '[DIAGNOSTICO] Se detecto interferencia de configuracion. Esta version usa un perfil aislado sin config.yaml.' -ForegroundColor Yellow
    }
}

function Test-Port7844Tcp {
    try {
        $command = Get-Command Test-NetConnection -ErrorAction SilentlyContinue
        if (-not $command) { return $null }
        return [bool](Test-NetConnection -ComputerName 'region1.v2.argotunnel.com' -Port 7844 -InformationLevel Quiet -WarningAction SilentlyContinue)
    } catch {
        return $null
    }
}

function Start-QuickTunnelAttempt([string]$CloudflaredPath, [string]$Protocol, [string]$Label) {
    $stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
    $stdout = Join-Path $TunnelLogDir "cloudflared_${stamp}_${Label}.stdout.log"
    $stderr = Join-Path $TunnelLogDir "cloudflared_${stamp}_${Label}.stderr.log"
    $cloudflaredArgs = @(
        'tunnel',
        '--url', $LocalBase,
        '--no-autoupdate',
        '--protocol', $Protocol,
        '--loglevel', 'info'
    )

    $commandTrace = @(
        "Ejecutable: $CloudflaredPath",
        "Argumentos: " + ($cloudflaredArgs -join ' '),
        "Perfil aislado: $CloudflaredHome",
        "Fecha: " + (Get-Date -Format s)
    )
    $commandTrace | Set-Content -Path (Join-Path $RuntimeDir 'ULTIMO_COMANDO_CLOUDFLARED.txt') -Encoding UTF8

    # El proceso hereda un HOME/USERPROFILE aislado. Así cloudflared no ve un
    # config.yaml personal, pero tampoco se pasa --config: Quick Tunnel no lo admite.
    $oldHome = $env:HOME
    $oldUserProfile = $env:USERPROFILE
    $oldTunnelConfig = $env:TUNNEL_CONFIG
    try {
        $env:HOME = $CloudflaredHome
        $env:USERPROFILE = $CloudflaredHome
        Remove-Item Env:\TUNNEL_CONFIG -ErrorAction SilentlyContinue
        $proc = Start-Process -FilePath $CloudflaredPath -ArgumentList $cloudflaredArgs -PassThru -WindowStyle Hidden `
            -RedirectStandardOutput $stdout -RedirectStandardError $stderr
    } finally {
        if ($null -eq $oldHome) { Remove-Item Env:\HOME -ErrorAction SilentlyContinue } else { $env:HOME = $oldHome }
        if ($null -eq $oldUserProfile) { Remove-Item Env:\USERPROFILE -ErrorAction SilentlyContinue } else { $env:USERPROFILE = $oldUserProfile }
        if ($null -eq $oldTunnelConfig) { Remove-Item Env:\TUNNEL_CONFIG -ErrorAction SilentlyContinue } else { $env:TUNNEL_CONFIG = $oldTunnelConfig }
    }

    return [PSCustomObject]@{
        Process = $proc
        Protocol = $Protocol
        Label = $Label
        Logs = @($stdout, $stderr)
    }
}

function Wait-TunnelUrl($Attempt, [int]$Seconds) {
    for ($i = 1; $i -le $Seconds; $i++) {
        $Attempt.Process.Refresh()
        $url = Get-TunnelUrl $Attempt.Logs
        if ($url) { return $url }
        if ($Attempt.Process.HasExited) { return $null }
        Start-Sleep -Seconds 1
    }
    return $null
}

function Wait-PublicReady([string]$Url, $Attempt, [int]$Seconds = 90) {
    $health = "$Url/api/health"
    $frontend = "$Url/frontend/index.html"
    for ($i = 1; $i -le $Seconds; $i++) {
        $publicInfo = Get-HealthInfo $health 8
        if ((Test-ExpectedBackend $publicInfo $true) -and (Test-HttpOk $frontend 8)) {
            return $publicInfo
        }
        $Attempt.Process.Refresh()
        if ($Attempt.Process.HasExited) { return $null }
        Start-Sleep -Seconds 1
    }
    return $null
}

Write-Host "Proyecto: $Root"
Write-Host "Instancia esperada: $ExpectedInstanceId"
Write-Host "URL local unificada: $LocalFrontend"
Write-Host "Logs de la aplicacion: $ApplicationLogDir"
Write-Host "Logs del tunel: $TunnelLogDir"
if ($PersonalCloudflaredConfigs.Count -gt 0) {
    Write-Host 'Se detectó config.yml/config.yaml personal de Cloudflare; no se modificará.' -ForegroundColor Yellow
    Write-Host 'Esta versión usa un perfil aislado para que no interfiera con Quick Tunnel.' -ForegroundColor Yellow
}
Write-Host ''

$backendInfo = Get-HealthInfo $HealthUrl 4
if ($backendInfo) {
    $currentId = [string]$backendInfo.project_instance_id
    $currentVersion = [string]$backendInfo.version
    if ($currentId -ne $ExpectedInstanceId) {
        Write-Host '[AVISO] El puerto 5000 pertenece a otra copia de Primera Infancia.' -ForegroundColor Yellow
        Write-Host "        Instancia activa: $currentId  Version: $currentVersion"
        Write-Host "        Instancia solicitada: $ExpectedInstanceId"
        Write-Host 'Se cerrara ese backend para no publicar la base equivocada.' -ForegroundColor Yellow
        Stop-VerifiedLocalBackend
        $backendInfo = $null
    } elseif ($backendInfo.public_tunnel_mode -ne $true) {
        Write-Host 'La copia correcta esta abierta en modo LOCAL.' -ForegroundColor Yellow
        Write-Host 'Se reiniciara en modo TUNEL para usar cookies y proxy seguros.' -ForegroundColor Yellow
        Stop-VerifiedLocalBackend
        $backendInfo = $null
    }
}

if (-not (Test-ExpectedBackend $backendInfo $true)) {
    Write-Host '[1/5] Iniciando esta copia en modo tunel...' -ForegroundColor Yellow
    $Launcher = Join-Path $ScriptDir 'iniciar_plataforma.ps1'
    if (-not (Test-Path $Launcher)) { throw "No existe $Launcher" }
    & $Launcher -Mode TunnelBackend -NoBrowser
    if ($LASTEXITCODE -ne 0) { throw "El lanzador del backend terminó con código $LASTEXITCODE." }

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

Write-Host '[3/5] Preparando cloudflared portable...'
$Cloudflared = Join-Path $ToolsDir 'cloudflared.exe'
$RefreshRequested = ($env:PI_REFRESH_CLOUDFLARED -eq '1')
if ($RefreshRequested -and (Test-Path $Cloudflared)) {
    Remove-Item $Cloudflared -Force -ErrorAction SilentlyContinue
}

if (-not (Test-Path $Cloudflared)) {
    Write-Host 'Descargando el ejecutable oficial más reciente...' -ForegroundColor Yellow
    $downloadArch = if ($env:PROCESSOR_ARCHITECTURE -eq 'ARM64') { 'arm64' } else { 'amd64' }
    $DownloadUrl = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-$downloadArch.exe"
    $downloadError = $null
    try {
        Invoke-WebRequest -UseBasicParsing -Uri $DownloadUrl -OutFile $Cloudflared -TimeoutSec 180
    } catch {
        $downloadError = $_.Exception.Message
        Remove-Item $Cloudflared -Force -ErrorAction SilentlyContinue
        Write-Host 'Invoke-WebRequest no pudo descargar cloudflared; probando curl.exe...' -ForegroundColor Yellow
        if (-not (Invoke-CurlDownload $DownloadUrl $Cloudflared 180)) {
            Remove-Item $Cloudflared -Force -ErrorAction SilentlyContinue
        }
    }

    if (Test-Path $Cloudflared) {
        Unblock-File -Path $Cloudflared -ErrorAction SilentlyContinue
        if ((Get-Item $Cloudflared).Length -lt 1MB) {
            Remove-Item $Cloudflared -Force -ErrorAction SilentlyContinue
            $downloadError = 'La descarga quedó incompleta.'
        }
    }

    if (-not (Test-Path $Cloudflared)) {
        $globalCmd = Get-Command cloudflared -ErrorAction SilentlyContinue
        if ($globalCmd) {
            Write-Host 'No se pudo descargar; se usara cloudflared instalado en el sistema.' -ForegroundColor Yellow
            $Cloudflared = $globalCmd.Source
        } else {
            throw "No pude descargar cloudflared. Descargalo manualmente y ubicalo en: $Cloudflared`nDetalle: $downloadError"
        }
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
Set-Content -Path $LinkFile -Encoding UTF8 -Value "Generando enlace publico...`nFecha: $(Get-Date -Format s)`nLocal: $LocalFrontend`nInstancia: $ExpectedInstanceId`n"

Write-Host '[4/5] Iniciando Quick Tunnel Cloudflare...'
Write-Host '      Intento 1: protocolo automatico (QUIC con fallback oficial).'
Write-Host ''

$SelectedAttempt = $null
$Url = $null
$PublicInfo = $null
$attemptSpecs = @(
    [PSCustomObject]@{ Protocol = 'auto'; Label = 'auto'; UrlWait = 45 },
    [PSCustomObject]@{ Protocol = 'http2'; Label = 'http2'; UrlWait = 75 }
)

foreach ($spec in $attemptSpecs) {
    if ($spec.Protocol -eq 'http2') {
        Write-Host ''
        Write-Host 'Intento 2: HTTP/2/TCP, útil cuando la red bloquea UDP/QUIC.' -ForegroundColor Yellow
    }
    $attempt = Start-QuickTunnelAttempt $Cloudflared $spec.Protocol $spec.Label
    Set-Content -Path $PidFile -Encoding ASCII -Value $attempt.Process.Id
    $candidateUrl = Wait-TunnelUrl $attempt $spec.UrlWait

    if (-not $candidateUrl) {
        Show-NetworkHints $attempt.Logs
        Show-LogTail $attempt.Logs
        Stop-ActiveTunnel $attempt.Process
        continue
    }

    Write-Host "Enlace generado: $candidateUrl" -ForegroundColor Cyan
    Write-Host 'Verificando que el enlace publique esta misma copia...'
    $candidateInfo = Wait-PublicReady $candidateUrl $attempt 90
    if ($candidateInfo) {
        $SelectedAttempt = $attempt
        $Url = $candidateUrl
        $PublicInfo = $candidateInfo
        break
    }

    Write-Host 'El enlace se genero, pero no supero la verificacion publica.' -ForegroundColor Yellow
    Show-NetworkHints $attempt.Logs
    Show-LogTail $attempt.Logs
    Stop-ActiveTunnel $attempt.Process
}

if (-not $SelectedAttempt -or -not $Url -or -not $PublicInfo) {
    $tcp7844 = Test-Port7844Tcp
    if ($tcp7844 -eq $false) {
        Write-Host '[DIAGNOSTICO] La prueba TCP al puerto 7844 fallo. Revisa firewall, antivirus, router o red institucional.' -ForegroundColor Yellow
    } elseif ($tcp7844 -eq $true) {
        Write-Host '[DIAGNOSTICO] El puerto TCP 7844 responde; revisa los logs por DNS, origen o antivirus.' -ForegroundColor Yellow
    }
    throw "Cloudflare no pudo producir un enlace verificado. Revisa $TunnelLogDir y ejecuta DIAGNOSTICAR_LOGIN_TUNEL.bat."
}

$PublicHealth = "$Url/api/health"
$FrontendPublic = "$Url/frontend/index.html"
$text = @"
ENLACE PUBLICO DE PRUEBAS
Fecha: $(Get-Date -Format s)
Estado: VERIFICADO
Frontend: $FrontendPublic
Base: $Url
Health: $PublicHealth
Local: $LocalFrontend
Instancia verificada: $ExpectedInstanceId
Version: $([string]$PublicInfo.version)
Protocolo cloudflared: $($SelectedAttempt.Protocol)
PID cloudflared: $($SelectedAttempt.Process.Id)
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

Write-Host '[5/5] Tunel listo, protocolo, modo e instancia verificados.' -ForegroundColor Green
Write-Host ''
Write-Host "ENLACE PUBLICO: $FrontendPublic" -ForegroundColor Cyan
Write-Host "Protocolo: $($SelectedAttempt.Protocol)"
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
    Wait-Process -Id $SelectedAttempt.Process.Id
} finally {
    Stop-ActiveTunnel $SelectedAttempt.Process
}
