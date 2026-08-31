[CmdletBinding()]
param([string]$Backup,[switch]$DryRun)
$ErrorActionPreference="Stop"
function Invoke-PackagePython {
    param([string[]]$ManagerArgs)
    $Script = Join-Path $PSScriptRoot "package_manager.py"
    if (Get-Command python -ErrorAction SilentlyContinue) { & python $Script @ManagerArgs }
    elseif (Get-Command py -ErrorAction SilentlyContinue) { & py -3 $Script @ManagerArgs }
    elseif (Get-Command python3 -ErrorAction SilentlyContinue) { & python3 $Script @ManagerArgs }
    else { throw "Python 3 was not found. Install Python or use the WSL/Linux installer." }
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
$ManagerArgs=@("restore");if($Backup){$ManagerArgs+=@("--backup",$Backup)};if($DryRun){$ManagerArgs+="--dry-run"}
Invoke-PackagePython $ManagerArgs
