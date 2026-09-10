$ErrorActionPreference = "Stop"
$mode = if ($env:CP_INSTALL_MODE) { $env:CP_INSTALL_MODE } else { "plugin" }
. "$PSScriptRoot/python-launcher.ps1"
Invoke-ValidatedPython -Script "$PSScriptRoot/package_manager.py" -Arguments (@("verify", "--scope", "user", "--mode", $mode) + @($args))
