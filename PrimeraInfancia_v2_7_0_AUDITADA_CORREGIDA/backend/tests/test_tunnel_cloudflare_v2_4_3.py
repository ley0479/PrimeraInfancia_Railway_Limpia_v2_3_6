#!/usr/bin/env python3
"""Regresión estática del Quick Tunnel Cloudflare corregido en 2.4.3.

No abre una conexión real a Cloudflare. Comprueba que el lanzador Windows use el
contrato oficial de Quick Tunnel, no cargue config.yml/config.yaml del usuario y
aplique fallback de red y verificación de la misma instancia.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8-sig", errors="strict")


def require(text: str, *needles: str) -> None:
    for needle in needles:
        if needle not in text:
            raise AssertionError(f"No se encontró {needle!r}")


def strip_powershell_literals(text: str) -> str:
    # Elimina here-strings, comentarios y cadenas para una comprobación simple
    # de delimitadores. No sustituye el parser de PowerShell en Windows.
    text = re.sub(r'(?ms)@".*?^"@\s*$', '', text)
    text = re.sub(r"(?ms)@'.*?^'@\s*$", '', text)
    text = re.sub(r'(?m)#.*$', '', text)
    text = re.sub(r"'(?:''|[^'])*'", "''", text)
    text = re.sub(r'"(?:`.|[^"`])*"', '""', text)
    return text


def main() -> None:
    tunnel = read("scripts_windows/iniciar_tunel_cloudflare.ps1")
    require(
        tunnel,
        "PRIMERA INFANCIA v2.7.0 - TUNEL CLOUDFLARE Y POSTGRESQL",
        "[Net.ServicePointManager]::SecurityProtocol",
        "Tls12",
        "cloudflared_home_aislado",
        "$env:HOME = $CloudflaredHome",
        "$env:USERPROFILE = $CloudflaredHome",
        "Invoke-CurlDownload",
        "ULTIMO_COMANDO_CLOUDFLARED.txt",
        "Protocol = 'auto'",
        "Protocol = 'http2'",
        "Test-Port7844Tcp",
        "Wait-PublicReady",
        "project_instance_id",
        "public_tunnel_mode",
    )

    start = tunnel.index("$cloudflaredArgs = @(")
    end = tunnel.index("# El proceso hereda", start)
    argument_block = tunnel[start:end]
    require(
        argument_block,
        "'tunnel'",
        "'--url', $LocalBase",
        "'--no-autoupdate'",
        "'--protocol', $Protocol",
        "'--loglevel', 'info'",
    )
    if "--config" in argument_block or "$QuickConfig" in tunnel:
        raise AssertionError("Quick Tunnel no debe recibir --config ni crear QuickConfig")

    # No debe modificar ni renombrar la configuración personal del usuario.
    if re.search(r"(?i)(Remove-Item|Move-Item|Rename-Item)[^\n]+PersonalCloudflaredConfigs", tunnel):
        raise AssertionError("El lanzador modifica la configuración personal de Cloudflare")

    stripped = strip_powershell_literals(tunnel)
    for opening, closing, name in [("{", "}", "llaves"), ("(", ")", "paréntesis")]:
        if stripped.count(opening) != stripped.count(closing):
            raise AssertionError(f"Desbalance de {name} en PowerShell")

    local_bat = read("INICIAR_PLATAFORMA_LOCAL.bat")
    require(local_bat, "iniciar_plataforma.ps1", "-Mode Local")
    launcher = read("scripts_windows/iniciar_plataforma.ps1")
    require(
        launcher,
        "PRIMERA INFANCIA 2.7.0",
        "$env:APP_VERSION = '2.7.0-centro-planeacion-psicosocial'",
        "/api/health",
        "PROJECT_INSTANCE_ID",
    )
    if "/api/acceso/ping" in launcher:
        raise AssertionError("El inicio local volvió a usar un endpoint autenticado")

    tunnel_bat = read("INICIAR_PLATAFORMA_TUNEL_ONLINE.bat")
    require(tunnel_bat, "iniciar_plataforma.ps1", "-Mode Tunnel")

    diagnostic = read("scripts_windows/diagnosticar_login_tunel.ps1")
    require(
        diagnostic,
        "DIAGNOSTICO DE TUNEL Y LOGIN",
        "logs_tunel",
        "region1.v2.argotunnel.com",
        "Port 7844",
        "HTTP/2/TCP",
        "config.yml/config.yaml",
        "ENLACE_PUBLICO_TUNEL.txt",
    )
    require(read("DIAGNOSTICAR_TUNEL_CLOUDFLARE.bat"), "diagnosticar_login_tunel.ps1")

    env = read(".env.example")
    require(env, "APP_VERSION=2.7.0-centro-planeacion-psicosocial")

    print("PASS test_tunnel_cloudflare_v2_4_3")


if __name__ == "__main__":
    main()
