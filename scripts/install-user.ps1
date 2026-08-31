$ErrorActionPreference = "Stop"
$mode = if ($env:CP_INSTALL_MODE) { $env:CP_INSTALL_MODE } else { "plugin" }
python "$PSScriptRoot/package_manager.py" install --scope user --mode $mode @args
