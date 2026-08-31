$ErrorActionPreference="Stop"
function Invoke-PackagePython {
    param([string[]]$ManagerArgs)
    $Script = Join-Path $PSScriptRoot "package_manager.py"
    if (Get-Command python -ErrorAction SilentlyContinue) { & python $Script @ManagerArgs }
    elseif (Get-Command py -ErrorAction SilentlyContinue) { & py -3 $Script @ManagerArgs }
    elseif (Get-Command python3 -ErrorAction SilentlyContinue) { & python3 $Script @ManagerArgs }
    else { throw "未找到 Python 3；请安装 Python 或使用 WSL/Linux 安装脚本。" }
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
Invoke-PackagePython @("verify")
