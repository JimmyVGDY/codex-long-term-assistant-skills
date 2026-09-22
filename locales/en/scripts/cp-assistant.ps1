[CmdletBinding()]
param(
    [Parameter(Position = 0)][string]$Command = "help",
    [Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments = @()
)

$ErrorActionPreference = "Stop"
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
$root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path

function Write-CpAssistantHelp {
    Write-Output "Codex Cross Project Assistant daily entry"
    Write-Output "Usage: cp-assistant.ps1 <command> [options]"
    Write-Output "Commands: help, install-base, status, doctor, verify, inventory,"
    Write-Output "          install-enhancement, recover, resume (status supports --quick)"
    Write-Output "help and install-base do not require Python. Management commands require Python 3.11+."
}

if ($Command -in @("help", "--help", "-h")) {
    Write-CpAssistantHelp
    exit 0
}

if ($Command -eq "install-base") {
    if ($Arguments.Count -gt 0) {
        if ($Arguments.Count -eq 1 -and $Arguments[0] -in @('--help', '-h')) {
            Write-Output 'Usage: cp-assistant.ps1 install-base (writes the managed base installation)'
            exit 0
        }
        [Console]::Error.WriteLine('[ERROR] install-base does not accept extra arguments')
        exit 2
    }
    & (Join-Path $PSScriptRoot "install-base.ps1") @Arguments
    exit $LASTEXITCODE
}

if ($Command -notin @('status', 'doctor', 'verify', 'inventory', 'install-enhancement', 'recover', 'resume')) {
    [Console]::Error.WriteLine('[ERROR] unknown cp-assistant command')
    exit 2
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
