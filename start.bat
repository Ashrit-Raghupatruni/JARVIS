@echo off
setlocal

:: Resolve the project root directory (where this .bat lives)
pushd "%~dp0"
set "PROJECT_ROOT=%CD%"

echo ============================================
echo   JARVIS AI Desktop Assistant - Launcher
echo ============================================
echo.

:: Check for .env
if not exist "%PROJECT_ROOT%\.env" (
    echo [ERROR] No .env file found. Run setup.bat first.
    pause
    exit /b 1
)

:: Kill any orphaned backend processes on port 8000 before starting
echo [0/2] Cleaning up any orphaned backend processes...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8000.*LISTENING" 2^>nul') do (
    echo   Killing orphaned process PID %%a on port 8000...
    taskkill /F /PID %%a >nul 2>&1
)
echo [OK] Port 8000 is free

:: Check Python Virtual Environment
if not exist "%PROJECT_ROOT%\backend\venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment missing at backend\venv. Run setup.bat first.
    pause
    exit /b 1
)

:: Check AI Engine Status
echo.
echo [1/2] Checking AI Engine status...
echo   - Primary Local Engine: Prash Engine - Embedded in Python backend
curl -s http://localhost:11434/api/tags >nul 2>&1
if %errorlevel% neq 0 (
    echo   - Secondary Local Fallback Ollama: Offline - Optional
    echo     JARVIS uses Prash natively. Cloud providers active.
    echo.
) else (
    echo   - Secondary Local Fallback Ollama: Online - qwen2.5-coder:3b ready
    echo.
)

:: Clear ELECTRON_RUN_AS_NODE to prevent Electron from running as plain Node.js
:: (This variable is often set by VS Code and other Electron-based IDEs)
set ELECTRON_RUN_AS_NODE=
:: Start Python AI Engine
echo.
echo [2/3] Launching Python AI Engine (FastAPI backend on port 8000)...
start "JARVIS Backend" /B /D "%PROJECT_ROOT%\backend" "%PROJECT_ROOT%\backend\venv\Scripts\python.exe" -m uvicorn main:app --host 0.0.0.0 --port 8000

:: Launch Electron Frontend
echo.
echo [3/3] Launching JARVIS Desktop UI...
cd /d "%PROJECT_ROOT%\frontend"
call npm run dev
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] JARVIS exited with error code %errorlevel%.
    pause
)

popd
endlocal
