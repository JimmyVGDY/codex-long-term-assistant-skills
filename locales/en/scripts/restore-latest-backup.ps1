[CmdletBinding()]
param([string]$Backup,[switch]$DryRun)
$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "python-launcher.ps1")
if ($Backup -or $DryRun) {
    throw 'This entry recovers the current managed transaction. It does not select a backup or support dry-run.'
}
Invoke-ValidatedPython -Script (Join-Path $PSScriptRoot "package_manager.py") -Arguments @("recover","--scope","user")
