@echo off
setlocal EnableExtensions DisableDelayedExpansion

set "CP_HOOK_SCRIPT=%~dp0cp_hook.py"
set "CP_PYTHON_EXE="
set "CP_PYTHON_PREFIX="

rem 中文：Codex 0.152.1 可能以精简 PATH 启动 Windows Hook，先定位账户级 CPython，再回退到 PATH 或 py.exe。
rem English: Codex 0.152.1 may launch Windows Hooks with a reduced PATH; resolve account-local CPython before falling back to PATH or py.exe.
if defined LOCALAPPDATA if exist "%LOCALAPPDATA%\Programs\Python" (
  for /f "delims=" %%D in ('dir /b /ad /o-n "%LOCALAPPDATA%\Programs\Python\Python*" 2^>nul') do (
    if exist "%LOCALAPPDATA%\Programs\Python\%%D\python.exe" (
      call :select_python "%LOCALAPPDATA%\Programs\Python\%%D\python.exe"
      if not errorlevel 1 goto run_python
    )
  )
)

for %%P in (python.exe) do if not "%%~$PATH:P"=="" (
  call :select_python "%%~$PATH:P"
  if not errorlevel 1 goto run_python
)

if defined LOCALAPPDATA if exist "%LOCALAPPDATA%\Programs\Python\Launcher\py.exe" (
  call :select_py "%LOCALAPPDATA%\Programs\Python\Launcher\py.exe"
  if not errorlevel 1 goto run_python
)

for %%P in (py.exe) do if not "%%~$PATH:P"=="" (
  call :select_py "%%~$PATH:P"
  if not errorlevel 1 goto run_python
)

>&2 echo [cp-assistant] Python 3.11+ was not found for the Windows hook.
exit /b 127

:run_python
"%CP_PYTHON_EXE%" %CP_PYTHON_PREFIX% -B "%CP_HOOK_SCRIPT%" "%~1"

:finish_python
set "CP_HOOK_EXIT=%ERRORLEVEL%"
exit /b %CP_HOOK_EXIT%

:select_python
"%~1" -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 3)" >nul 2>nul
if errorlevel 1 exit /b 1
set "CP_PYTHON_EXE=%~1"
set "CP_PYTHON_PREFIX="
exit /b 0

:select_py
"%~1" -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 3)" >nul 2>nul
if errorlevel 1 exit /b 1
set "CP_PYTHON_EXE=%~1"
set "CP_PYTHON_PREFIX=-3"
exit /b 0
