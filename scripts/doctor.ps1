$ErrorActionPreference = "Stop"
. "$PSScriptRoot/python-launcher.ps1"
Invoke-ValidatedPython -Script "$PSScriptRoot/package_manager.py" -Arguments (@("doctor") + @($args))
