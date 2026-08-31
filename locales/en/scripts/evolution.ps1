[CmdletBinding()]
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$EvolutionArgs
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Entry = Join-Path $ScriptDir "evolution.py"

$Python = Get-Command python -ErrorAction SilentlyContinue
if (-not $Python) {
    $Python = Get-Command py -ErrorAction SilentlyContinue
    if (-not $Python) {
        throw "Python was not found. Install Python 3.8+ and add it to PATH."
    }
    & $Python.Source -3 -B $Entry @EvolutionArgs
} else {
    & $Python.Source -B $Entry @EvolutionArgs
}
exit $LASTEXITCODE
