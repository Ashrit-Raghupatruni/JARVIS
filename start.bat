@echo off
setlocal

:: Resolve the project root directory (where this .bat lives)
pushd "%~dp0"
set "PROJECT_ROOT=%CD%"
set "PYTHONPATH=%PROJECT_ROOT%"

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

:: Check Python Virtual Environment
if not exist "%PROJECT_ROOT%\backend\venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment missing at backend\venv. Run setup.bat first.
    pause
    exit /b 1
)

:: Check AI Engine Status
echo [1/4] Checking AI Engine status...
echo   - Primary Local Engine: Prash Engine - Embedded in Python backend
curl -s --connect-timeout 2 http://localhost:11434/api/tags >nul 2>&1
if %errorlevel% neq 0 (
    echo   - Secondary Local Fallback Ollama: Offline - Optional
    echo     JARVIS uses Prash natively. Cloud providers active.
) else (
    echo   - Secondary Local Fallback Ollama: Online - qwen2.5-coder:3b ready
)
echo.

:: Free port 8000 if occupied by dead/orphaned process
echo [2/4] Verifying port 8000 availability...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8000.*LISTENING" 2^>nul') do (
    echo   Releasing orphaned process PID %%a on port 8000...
    taskkill /F /PID %%a >nul 2>&1
)
echo [OK] Port 8000 ready.
echo.

:: Launch Python AI Engine
echo [3/4] Launching Python AI Engine (FastAPI backend on port 8000)...
start "JARVIS Backend" /B /D "%PROJECT_ROOT%\backend" "%PROJECT_ROOT%\backend\venv\Scripts\python.exe" -m uvicorn main:app --host 0.0.0.0 --port 8000

:: Wait for Backend to become fully healthy before starting frontend
echo   Waiting for backend to initialize and bind socket...
set /a ATTEMPTS=0
:WAIT_LOOP
set /a ATTEMPTS+=1
timeout /t 1 /nobreak >nul
curl -s --connect-timeout 1 http://127.0.0.1:8000/api/health >nul 2>&1
if %errorlevel% equ 0 goto BACKEND_READY
if %ATTEMPTS% geq 30 goto BACKEND_TIMEOUT
echo   - Initializing core services (attempt %ATTEMPTS%/30)...
goto WAIT_LOOP

:BACKEND_TIMEOUT
echo [WARNING] Backend did not report health within 30s. Launching frontend anyway...
goto LAUNCH_FRONTEND

:BACKEND_READY
echo [OK] Backend is healthy and listening on http://127.0.0.1:8000!
echo.

:LAUNCH_FRONTEND
:: Clear ELECTRON_RUN_AS_NODE to prevent Electron from running as plain Node.js
set ELECTRON_RUN_AS_NODE=

:: Launch Electron Frontend
echo [4/4] Launching JARVIS Desktop UI...
cd /d "%PROJECT_ROOT%\frontend"
call npm run dev
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] JARVIS exited with error code %errorlevel%.
)

:: Clean up background backend process when Electron quits
echo.
echo Shutting down background backend processes...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8000.*LISTENING" 2^>nul') do (
    taskkill /F /PID %%a >nul 2>&1
)
echo [OK] JARVIS shutdown complete.

popd
endlocal
