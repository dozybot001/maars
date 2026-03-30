@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0"

:: Re-invoke under cmd /c so Ctrl+C exits cleanly (no "Terminate batch job?" prompt)
if not "%MAARS_STARTED%"=="1" (
    set "MAARS_STARTED=1"
    cmd /c "%~f0" %* <nul
    :: After server stops, close the MAARS app window (try both browsers)
    taskkill /fi "WINDOWTITLE eq MAARS*" /im chrome.exe >nul 2>&1
    taskkill /fi "WINDOWTITLE eq MAARS*" /im msedge.exe >nul 2>&1
    exit /b
)

echo ========================================
echo          MAARS - One-Click Start
echo ========================================
echo.

:: --- 1. Check Python ---
echo [1/4] Checking Python...
where python >nul 2>&1
if errorlevel 1 (
    echo   [ERROR] Python not found. Please install Python 3.10+.
    pause
    exit /b 1
)
for /f "tokens=*" %%v in ('python --version 2^>^&1') do echo   Found: %%v

:: --- 2. Install dependencies ---
echo [2/4] Installing Python dependencies...
python -m pip install -r requirements.txt -q
if errorlevel 1 (
    echo   [ERROR] Failed to install dependencies.
    pause
    exit /b 1
)
echo   Dependencies installed.

:: --- 3. Check .env ---
echo [3/4] Checking .env configuration...
if not exist .env (
    echo   .env not found. Creating template...
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
    echo   [ERROR] Please edit .env and add your API key, then re-run this script.
    pause
    exit /b 1
)

:: Check for at least one API key
set HAS_KEY=0
for /f "usebackq tokens=1,* delims==" %%a in (".env") do (
    if "%%a"=="MAARS_GOOGLE_API_KEY" if not "%%b"=="" set HAS_KEY=1
    if "%%a"=="MAARS_OPENAI_API_KEY" if not "%%b"=="" set HAS_KEY=1
    if "%%a"=="MAARS_ANTHROPIC_API_KEY" if not "%%b"=="" set HAS_KEY=1
)
if %HAS_KEY%==0 (
    echo   [ERROR] No API key found in .env. Please add at least one API key.
    pause
    exit /b 1
)
echo   .env configured.

:: --- 4. Docker sandbox ---
echo [4/4] Checking Docker sandbox image...
where docker >nul 2>&1
if errorlevel 1 (
    echo   [WARN] Docker not found. Code execution in sandbox will be unavailable.
    goto :start
)
docker image inspect maars-sandbox:latest >nul 2>&1
if errorlevel 1 (
    echo   Building sandbox image (first time only^)...
    docker build -f Dockerfile.sandbox -t maars-sandbox:latest .
    echo   Sandbox image built.
) else (
    echo   Sandbox image already exists.
)

:start
echo.
echo ========================================
echo   Starting MAARS on http://localhost:8000
echo   Press Ctrl+C to stop.
echo ========================================
echo.
:: Open browser in app mode (Chrome > Edge > default)
:: App mode = standalone window, auto-closed on exit
set "MAARS_BROWSER="
where chrome >nul 2>&1 && set "MAARS_BROWSER=chrome"
if not defined MAARS_BROWSER (
    if exist "%ProgramFiles%\Google\Chrome\Application\chrome.exe" set "MAARS_BROWSER=%ProgramFiles%\Google\Chrome\Application\chrome.exe"
)
if not defined MAARS_BROWSER (
    if exist "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe" set "MAARS_BROWSER=%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"
)
if not defined MAARS_BROWSER (
    if exist "%LocalAppData%\Google\Chrome\Application\chrome.exe" set "MAARS_BROWSER=%LocalAppData%\Google\Chrome\Application\chrome.exe"
)
if not defined MAARS_BROWSER (
    where msedge >nul 2>&1 && set "MAARS_BROWSER=msedge"
)
if defined MAARS_BROWSER (
    start /b cmd /c "timeout /t 2 /nobreak >nul && start "" "%MAARS_BROWSER%" --app=http://localhost:8000"
) else (
    start /b cmd /c "timeout /t 2 /nobreak >nul && start http://localhost:8000"
)
python -m uvicorn backend.main:app --reload --reload-include "*.py" --reload-dir backend --host 0.0.0.0 --port 8000 --timeout-graceful-shutdown 1
