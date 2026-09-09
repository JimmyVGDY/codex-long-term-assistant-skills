@echo off
setlocal EnableExtensions DisableDelayedExpansion

set "CP_GATE_SCRIPT=%~dp0cp_gate.py"
set "CP_PYTHON_EXE="

rem 中文：文件门禁使用独立轻量启动器；解释器查找顺序与生命周期 Hook 一致。
rem English: The file gate has a lightweight launcher with the lifecycle Hook interpreter order.
if defined LOCALAPPDATA if exist "%LOCALAPPDATA%\Programs\Python" (
  for /f "delims=" %%D in ('dir /b /ad /o-n "%LOCALAPPDATA%\Programs\Python\Python*" 2^>nul') do (
    if exist "%LOCALAPPDATA%\Programs\Python\%%D\python.exe" (
      set "CP_PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\%%D\python.exe"
      goto run_python
    )
  )
)

for %%P in (python.exe) do if not "%%~$PATH:P"=="" (
  set "CP_PYTHON_EXE=%%~$PATH:P"
  goto run_python
)

if defined LOCALAPPDATA if exist "%LOCALAPPDATA%\Programs\Python\Launcher\py.exe" (
  "%LOCALAPPDATA%\Programs\Python\Launcher\py.exe" -3 -B "%CP_GATE_SCRIPT%" "%~1"
  goto finish_python
)

for %%P in (py.exe) do if not "%%~$PATH:P"=="" (
  "%%~$PATH:P" -3 -B "%CP_GATE_SCRIPT%" "%~1"
  goto finish_python
)

>&2 echo [cp-assistant] Python 3 was not found for the Windows file gate.
exit /b 127

:run_python
"%CP_PYTHON_EXE%" -B "%CP_GATE_SCRIPT%" "%~1"

:finish_python
set "CP_HOOK_EXIT=%ERRORLEVEL%"
exit /b %CP_HOOK_EXIT%
