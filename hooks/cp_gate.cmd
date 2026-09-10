@echo off
setlocal EnableExtensions DisableDelayedExpansion

set "CP_GATE_SCRIPT=%~dp0cp_gate.py"
set "CP_PYTHON_EXE="
set "CP_PYTHON_PREFIX="

rem 中文：文件门禁使用独立轻量启动器；解释器查找顺序与生命周期 Hook 一致。
rem English: The file gate has a lightweight launcher with the lifecycle Hook interpreter order.
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

>&2 echo [cp-assistant] Python 3.11+ was not found for the Windows file gate.
exit /b 127

:run_python
"%CP_PYTHON_EXE%" %CP_PYTHON_PREFIX% -B "%CP_GATE_SCRIPT%" "%~1"

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
