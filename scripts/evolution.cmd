@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
where python >nul 2>nul
if %ERRORLEVEL% EQU 0 (
  python -B "%SCRIPT_DIR%evolution.py" %*
  exit /b %ERRORLEVEL%
)
where py >nul 2>nul
if %ERRORLEVEL% EQU 0 (
  py -3 -B "%SCRIPT_DIR%evolution.py" %*
  exit /b %ERRORLEVEL%
)
echo 未找到 Python。请安装 Python 3.11+ 并加入 PATH。 1>&2
exit /b 2
