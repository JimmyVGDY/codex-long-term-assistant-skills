$ErrorActionPreference = "Stop"
$mode = if ($env:CP_INSTALL_MODE) { $env:CP_INSTALL_MODE } else { "plugin" }
python "$PSScriptRoot/package_manager.py" uninstall --scope user --mode $mode @args
