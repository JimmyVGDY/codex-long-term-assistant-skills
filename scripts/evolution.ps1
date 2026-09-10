[CmdletBinding()]
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$EvolutionArgs
)

$ErrorActionPreference = "Stop"
. "$PSScriptRoot/python-launcher.ps1"
Invoke-ValidatedPython -Script "$PSScriptRoot/evolution.py" -Arguments $EvolutionArgs
