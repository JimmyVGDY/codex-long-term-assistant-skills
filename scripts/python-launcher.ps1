$ErrorActionPreference = "Stop"

function Invoke-ValidatedPython {
    param(
        [Parameter(Mandatory = $true)][string]$Script,
        [string[]]$Arguments = @()
    )
    $candidates = @()
    if ($env:CP_ASSISTANT_PYTHON) {
        $explicit = Get-Command $env:CP_ASSISTANT_PYTHON -ErrorAction SilentlyContinue
        if (-not $explicit) { throw "CP_ASSISTANT_PYTHON is not executable; select Python 3.11+." }
        $candidates += [pscustomobject]@{ Command = $explicit.Source; Prefix = @(); Source = "CP_ASSISTANT_PYTHON" }
    } else {
        foreach ($name in @('python','py','python3')) {
            $prefix = @()
            if ($name -eq 'py') { $prefix = @('-3') }
            foreach ($program in @(Get-Command -Name $name -All -CommandType Application -ErrorAction SilentlyContinue)) {
                $candidates += [pscustomobject]@{ Command = $program.Source; Prefix = $prefix; Source = $name }
            }
        }
    }
    $observed = @()
    foreach ($candidate in $candidates) {
        $probe = @($candidate.Prefix) + @("-c", "import sys; print('.'.join(map(str, sys.version_info[:3]))); raise SystemExit(0 if sys.version_info >= (3, 11) else 3)")
        try {
            $version = & $candidate.Command @probe 2>$null
            $code = $LASTEXITCODE
        } catch {
            $version = 'unavailable'
            $code = 1
        }
        $observed += "$($candidate.Source)=$version"
        if ($code -eq 0 -and "$version" -match '^\d+\.\d+\.\d+$') {
            $commandArgs = @($candidate.Prefix) + @('-B', $Script) + @($Arguments)
            & $candidate.Command @commandArgs
            exit $LASTEXITCODE
        }
        if ($env:CP_ASSISTANT_PYTHON) { break }
    }
    throw "Python 3.11+ was not found. Checked: $($observed -join ', ')"
}
