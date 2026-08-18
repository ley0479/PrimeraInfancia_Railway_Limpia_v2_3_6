#requires -version 5.1
[CmdletBinding()]
param(
    [string]$DatabaseUrl,
    [switch]$TruncateTarget,
    [switch]$VerifyExisting,
    [switch]$DoNotActivate
)
$ErrorActionPreference = 'Stop'
$target = Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) 'migrar_completo_postgresql.ps1'
& $target -DatabaseUrl $DatabaseUrl -TruncateTarget:$TruncateTarget -VerifyExisting:$VerifyExisting -DoNotActivate:$DoNotActivate
exit $LASTEXITCODE
