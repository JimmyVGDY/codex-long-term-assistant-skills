[CmdletBinding()]
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$EvolutionArgs
)

$ErrorActionPreference = "Stop"
# 中文：共享启动器在导入本地模块前验证 Python 3.11+。
# English: The shared launcher validates Python 3.11+ before importing local modules.
. "$PSScriptRoot/python-launcher.ps1"
Invoke-ValidatedPython -Script "$PSScriptRoot/evolution.py" -Arguments $EvolutionArgs
