param([string]$RepoPath = ".")
$ErrorActionPreference = "Stop"
. "$PSScriptRoot/python-launcher.ps1"
Invoke-ValidatedPython -Script "$PSScriptRoot/package_manager.py" -Arguments (@("install", "--scope", "repo", "--repo-path", $RepoPath) + @($args))
