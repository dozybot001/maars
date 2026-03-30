@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0"

:: Re-invoke under cmd /c so Ctrl+C exits cleanly (no "Terminate batch job?" prompt)
if not "%MAARS_STARTED%"=="1" (
    set "MAARS_STARTED=1"
    cmd /c "%~f0" %* <nul
    exit /b
)

:: ── Summary tracking ──
set "S_PYTHON=."
set "S_DEPS=."
set "S_APIKEY=."
set "S_FRONTEND=."
set "S_DOCKER=."

echo.
echo   [36m[1m    +---+  +---+  +---+  +---+  +---+[0m
echo   [36m[1m    ! M !  ! A !  ! A !  ! R !  ! S ![0m
echo   [36m[1m    +---+  +---+  +---+  +---+  +---+[0m
echo.
echo   [90mMulti-Agent Automated Research System[0m
echo   [90m--------------------------------------[0m
echo.

:: ══════════════════════════════════════════════════════════════
::  1. Check Python
:: ══════════════════════════════════════════════════════════════
echo   [90m[1/6][0m [1mChecking Python[0m
where python >nul 2>&1
if errorlevel 1 (
    echo     [31mX[0m  Python not found. Please install Python 3.10+.
    set "S_PYTHON=FAIL"
    pause
    exit /b 1
)
for /f "tokens=*" %%v in ('python --version 2^>^&1') do (
    echo     [32m√[0m  %%v
)
set "S_PYTHON=OK"
echo.

:: ══════════════════════════════════════════════════════════════
::  2. Setup venv & install dependencies
:: ══════════════════════════════════════════════════════════════
echo   [90m[2/6][0m [1mSetting up virtual environment[0m
if not exist .venv (
    echo     [36m~[0m  Creating virtual environment...
    python -m venv .venv
    echo     [32m√[0m  Virtual environment created
) else (
    echo     [32m√[0m  Virtual environment exists
)
call .venv\Scripts\activate.bat
echo     [36m~[0m  Installing Python dependencies...
python -m pip install -r requirements.txt -q
if errorlevel 1 (
    echo     [31mX[0m  Failed to install dependencies
    set "S_DEPS=FAIL"
    pause
    exit /b 1
)
echo     [32m√[0m  Dependencies installed
set "S_DEPS=OK"
echo.

:: ══════════════════════════════════════════════════════════════
::  3. Check .env
:: ══════════════════════════════════════════════════════════════
echo   [90m[3/6][0m [1mChecking configuration[0m
if not exist .env (
    echo     [33m![0m  .env not found — creating template...
    (
        echo # MAARS Configuration
        echo # At least one API key is required.
        echo.
        echo MAARS_GOOGLE_API_KEY=
        echo # MAARS_AGNO_MODEL_PROVIDER=google
        echo # MAARS_AGNO_MODEL_ID=
        echo # MAARS_OPENAI_API_KEY=
        echo # MAARS_ANTHROPIC_API_KEY=
        echo # MAARS_KAGGLE_API_TOKEN=
    ) > .env
    echo     [31mX[0m  Please edit .env and add your API key, then re-run.
    set "S_APIKEY=FAIL"
    pause
    exit /b 1
)

set HAS_KEY=0
for /f "usebackq tokens=1,* delims==" %%a in (".env") do (
    if "%%a"=="MAARS_GOOGLE_API_KEY" if not "%%b"=="" set HAS_KEY=1
    if "%%a"=="MAARS_OPENAI_API_KEY" if not "%%b"=="" set HAS_KEY=1
    if "%%a"=="MAARS_ANTHROPIC_API_KEY" if not "%%b"=="" set HAS_KEY=1
)
if %HAS_KEY%==0 (
    echo     [31mX[0m  No API key found in .env
    set "S_APIKEY=FAIL"
    pause
    exit /b 1
)
echo     [32m√[0m  API key configured
set "S_APIKEY=OK"
echo.

:: ══════════════════════════════════════════════════════════════
::  4. Build frontend
:: ══════════════════════════════════════════════════════════════
echo   [90m[4/6][0m [1mBuilding frontend[0m
where node >nul 2>&1
if errorlevel 1 (
    echo     [33m![0m  Node.js not found — using pre-built frontend
    set "S_FRONTEND=WARN"
    goto :docker
)
for /f "tokens=*" %%v in ('node --version 2^>^&1') do echo     [36m>[0m  Node %%v
echo     [36m~[0m  Installing ^& building...
pushd frontend
call npm install --silent 2>nul
call npm run build 2>nul
popd
echo     [32m√[0m  Frontend built
set "S_FRONTEND=OK"
echo.

:docker
:: ══════════════════════════════════════════════════════════════
::  5. Docker sandbox
:: ══════════════════════════════════════════════════════════════
echo   [90m[5/6][0m [1mChecking Docker sandbox[0m
where docker >nul 2>&1
if errorlevel 1 (
    echo     [31mX[0m  Docker CLI is required
    set "S_DOCKER=FAIL"
    pause
    exit /b 1
)
docker info >nul 2>&1
if errorlevel 1 (
    echo     [36m~[0m  Starting Docker Desktop...
    if exist "%ProgramFiles%\Docker\Docker\Docker Desktop.exe" (
        start "" "%ProgramFiles%\Docker\Docker\Docker Desktop.exe"
    ) else if exist "%LocalAppData%\Programs\Docker\Docker\Docker Desktop.exe" (
        start "" "%LocalAppData%\Programs\Docker\Docker\Docker Desktop.exe"
    )
    set "DOCKER_READY=0"
    for /L %%i in (1,1,60) do (
        docker info >nul 2>&1 && set "DOCKER_READY=1" && goto :docker_ready
        timeout /t 1 /nobreak >nul
    )
    echo     [31mX[0m  Docker did not become ready
    set "S_DOCKER=FAIL"
    pause
    exit /b 1
)
:docker_ready
docker image inspect maars-sandbox:latest >nul 2>&1
if errorlevel 1 (
    echo     [36m~[0m  Building sandbox image (first time)...
    docker build -f Dockerfile.sandbox -t maars-sandbox:latest . -q >nul
    echo     [32m√[0m  Sandbox image built
) else (
    echo     [32m√[0m  Sandbox image ready
)
set "S_DOCKER=OK"
echo.

:launch
:: ══════════════════════════════════════════════════════════════
::  6. Launch
:: ══════════════════════════════════════════════════════════════
echo   [90m[6/6][0m [1mStarting server[0m
echo.

:: ── Summary table ──
echo   [90m+--------------------------------------+[0m
echo   [90m^|[0m  [1mStatus Summary[0m                      [90m^|[0m

echo   [90m+--------------------------------------+[0m
if "%S_PYTHON%"=="OK"   ( echo   [90m^|[0m  [32m√[0m  Python                        [90m^|[0m
) else if "%S_PYTHON%"=="WARN" ( echo   [90m^|[0m  [33m![0m  Python                        [90m^|[0m
) else ( echo   [90m^|[0m  [31mX[0m  Python                        [90m^|[0m )
if "%S_DEPS%"=="OK"     ( echo   [90m^|[0m  [32m√[0m  Dependencies                  [90m^|[0m
) else if "%S_DEPS%"=="WARN" ( echo   [90m^|[0m  [33m![0m  Dependencies                  [90m^|[0m
) else ( echo   [90m^|[0m  [31mX[0m  Dependencies                  [90m^|[0m )
if "%S_APIKEY%"=="OK"   ( echo   [90m^|[0m  [32m√[0m  API Key                       [90m^|[0m
) else if "%S_APIKEY%"=="WARN" ( echo   [90m^|[0m  [33m![0m  API Key                       [90m^|[0m
) else ( echo   [90m^|[0m  [31mX[0m  API Key                       [90m^|[0m )
if "%S_FRONTEND%"=="OK" ( echo   [90m^|[0m  [32m√[0m  Frontend                      [90m^|[0m
) else if "%S_FRONTEND%"=="WARN" ( echo   [90m^|[0m  [33m![0m  Frontend                      [90m^|[0m
) else ( echo   [90m^|[0m  [31mX[0m  Frontend                      [90m^|[0m )
if "%S_DOCKER%"=="OK"   ( echo   [90m^|[0m  [32m√[0m  Docker Sandbox                [90m^|[0m
) else if "%S_DOCKER%"=="WARN" ( echo   [90m^|[0m  [33m![0m  Docker Sandbox                [90m^|[0m
) else ( echo   [90m^|[0m  [31mX[0m  Docker Sandbox                [90m^|[0m )
echo   [90m+--------------------------------------+[0m
echo.
echo   [32m[1m^> http://localhost:8000[0m
echo   [90mPress Ctrl+C to stop the server[0m
echo.

:: Open default browser after a short delay
start /b cmd /c "timeout /t 2 /nobreak >nul && start http://localhost:8000"
python -m uvicorn backend.main:app --reload --reload-include "*.py" --reload-dir backend --host 0.0.0.0 --port 8000 --timeout-graceful-shutdown 1
