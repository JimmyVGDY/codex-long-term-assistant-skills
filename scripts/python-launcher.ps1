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
        $python = Get-Command python -ErrorAction SilentlyContinue
        if ($python) { $candidates += [pscustomobject]@{ Command = $python.Source; Prefix = @(); Source = "python" } }
        $py = Get-Command py -ErrorAction SilentlyContinue
        if ($py) { $candidates += [pscustomobject]@{ Command = $py.Source; Prefix = @("-3"); Source = "py -3" } }
        $python3 = Get-Command python3 -ErrorAction SilentlyContinue
        if ($python3) { $candidates += [pscustomobject]@{ Command = $python3.Source; Prefix = @(); Source = "python3" } }
    }
    $observed = @()
    foreach ($candidate in $candidates) {
        $probe = @($candidate.Prefix) + @("-c", "import sys; print('.'.join(map(str, sys.version_info[:3]))); raise SystemExit(0 if sys.version_info >= (3, 11) else 3)")
        $version = & $candidate.Command @probe 2>$null
        $code = $LASTEXITCODE
        $observed += "$($candidate.Source)=$version"
        if ($code -eq 0) {
            & $candidate.Command @($candidate.Prefix) -B $Script @Arguments
            exit $LASTEXITCODE
        }
        if ($env:CP_ASSISTANT_PYTHON) { break }
    }
    throw "Python 3.11+ was not found. Checked: $($observed -join ', ')"
}
