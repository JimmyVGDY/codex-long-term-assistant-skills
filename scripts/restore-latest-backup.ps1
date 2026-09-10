[CmdletBinding()]
param([string]$Backup,[switch]$DryRun)
$ErrorActionPreference="Stop"
. "$PSScriptRoot/python-launcher.ps1"
if ($Backup -or $DryRun) {
    throw "此兼容入口现在统一转到 recover；recover 只恢复当前持久事务，不接受手选备份或 dry-run。"
}
Invoke-ValidatedPython -Script "$PSScriptRoot/package_manager.py" -Arguments @("recover", "--scope", "user")
