param([string]$RepoPath = ".")
$ErrorActionPreference = "Stop"
python "$PSScriptRoot/package_manager.py" install --scope repo --repo-path $RepoPath @args
