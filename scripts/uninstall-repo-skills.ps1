param([string]$RepoPath = ".")
$ErrorActionPreference = "Stop"
python "$PSScriptRoot/package_manager.py" uninstall --scope repo --repo-path $RepoPath @args
