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
        throw "未找到 Python。请安装 Python 3.11+ 并加入 PATH。"
    }
    & $Python.Source -3 -B $Entry @EvolutionArgs
} else {
    & $Python.Source -B $Entry @EvolutionArgs
}
exit $LASTEXITCODE
