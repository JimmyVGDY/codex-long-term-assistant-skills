[CmdletBinding()]
param(
    [Parameter(Position = 0)][string]$Command = "help",
    [Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments = @()
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path

function Write-CpAssistantHelp {
    Write-Output "Codex Cross Project Assistant daily entry"
    Write-Output "Usage: cp-assistant.ps1 <command> [options]"
    Write-Output "Commands: help, install-base, status, doctor, verify, inventory,"
    Write-Output "          install-enhancement, recover, resume"
    Write-Output "help and install-base do not require Python. Management commands require Python 3.11+."
}

if ($Command -in @("help", "--help", "-h")) {
    Write-CpAssistantHelp
    exit 0
}

if ($Command -eq "install-base") {
    & (Join-Path $PSScriptRoot "install-base.ps1") @Arguments
    exit $LASTEXITCODE
}

try {
    . (Join-Path $PSScriptRoot "python-launcher.ps1")
    Invoke-ValidatedPython -Script (Join-Path $PSScriptRoot "cp-assistant.py") -Arguments (@($Command) + @($Arguments))
    exit $LASTEXITCODE
} catch {
    $message = 'Python 3.11+ is required for this diagnostic command; the installed base Skill remains usable. Run codex plugin list --json for native readback.'
    if (@($Arguments) -contains '--json') {
        [Console]::Out.WriteLine('{"schema":"cp-assistant/1","overall":"UNKNOWN","reason":"PYTHON_REQUIRED","available":"Base Skill availability was not checked by this entry","next_action":"codex plugin list --json"}')
    } else {
        [Console]::Error.WriteLine('[ERROR] ' + $message)
    }
    exit 2
}
