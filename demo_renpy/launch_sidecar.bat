@echo off
REM Convenient launcher for the Sonder sidecar (for the Ren'Py demo) on Windows.
REM
REM Double-click this file, or run from cmd:
REM   cd demo_renpy
REM   launch_sidecar.bat
REM
REM It will load .env from the project root (if present) and start the sidecar.

setlocal enabledelayedexpansion

REM Move to repo root (two levels up from demo_renpy)
set "SCRIPT_DIR=%~dp0"
set "REPO_ROOT=%SCRIPT_DIR%.."
cd /d "%REPO_ROOT%"

echo ==^> Working from: %CD%

REM Load .env variables (very basic parser — one KEY=VALUE per line)
if exist ".env" (
    echo ==^> Loading .env
    for /f "usebackq tokens=1,* delims==" %%a in (".env") do (
        set "key=%%a"
        set "val=%%b"
        REM Trim leading spaces
        for /f "tokens=* delims= " %%k in ("!key!") do set "key=%%k"
        for /f "tokens=* delims= " %%v in ("!val!") do set "val=%%v"
        if not "!key!"=="" if not "!key:~0,1!"=="#" (
            set "!key!=!val!"
        )
    )
) else (
    echo ==^> No .env found — using existing environment
)

set PORT=%SONDER_PORT%
if "%PORT%"=="" set PORT=8765

echo ==^> Starting Sonder sidecar on http://127.0.0.1:%PORT%
echo.
echo     Keep this window open!
echo     Then:
echo       1. Open the Ren'Py launcher
echo       2. Copy demo_renpy\game\*.rpy into a Ren'Py project's game\ folder
echo       3. Launch the project from Ren'Py
echo.
echo     Close this window or press Ctrl+C to stop the sidecar.
echo.

REM Try the nice entry point first (available after "pip install -e .")
where sonder-sidecar >nul 2>nul
if %ERRORLEVEL%==0 (
    echo ==^> Using sonder-sidecar command
    sonder-sidecar --host 127.0.0.1 --port %PORT%
    goto :end
)

REM Fall back to python. On modern systems this may be python or py
echo ==^> Trying python -m ...
python -m sonder_engram.service --host 127.0.0.1 --port %PORT% 2>nul
if %ERRORLEVEL% neq 0 (
    py -m sonder_engram.service --host 127.0.0.1 --port %PORT%
)

:end
pause
