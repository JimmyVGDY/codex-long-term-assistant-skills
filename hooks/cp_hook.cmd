@echo off
setlocal EnableExtensions DisableDelayedExpansion

set "CP_HOOK_SCRIPT=%~dp0cp_hook.py"
set "CP_PYTHON_EXE="

rem 中文：Codex 0.152.1 可能以精简 PATH 启动 Windows Hook，先定位账户级 CPython，再回退到 PATH 或 py.exe。
rem English: Codex 0.152.1 may launch Windows Hooks with a reduced PATH; resolve account-local CPython before falling back to PATH or py.exe.
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
  "%LOCALAPPDATA%\Programs\Python\Launcher\py.exe" -3 "%CP_HOOK_SCRIPT%" "%~1"
  goto finish_python
)

for %%P in (py.exe) do if not "%%~$PATH:P"=="" (
  "%%~$PATH:P" -3 "%CP_HOOK_SCRIPT%" "%~1"
  goto finish_python
)

>&2 echo [cp-assistant] Python 3 was not found for the Windows hook.
exit /b 127

:run_python
"%CP_PYTHON_EXE%" "%CP_HOOK_SCRIPT%" "%~1"

:finish_python
set "CP_HOOK_EXIT=%ERRORLEVEL%"
exit /b %CP_HOOK_EXIT%
