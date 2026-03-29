@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0"

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
:: Open browser after a short delay
start "" cmd /c "timeout /t 2 /nobreak >nul && start http://localhost:8000"
python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
pause
