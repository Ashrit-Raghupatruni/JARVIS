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

:: Check if Ollama is running and the model is available
echo.
echo [1/2] Checking Ollama status...
curl -s http://localhost:11434/api/tags >nul 2>&1
if %errorlevel% neq 0 (
    echo [WARNING] Ollama is not running!
    echo   Please start Ollama first: ollama serve
    echo   Then pull the model: ollama pull qwen2.5-coder:3b
    echo.
    echo   JARVIS will still launch but will fall back to Gemini/OpenAI.
    echo.
) else (
    echo [OK] Ollama is running
    echo   Starting qwen2.5-coder:3b model...
    start /b ollama run qwen2.5-coder:3b >nul 2>&1
    echo [OK] Ollama model ready
)

:: Clear ELECTRON_RUN_AS_NODE to prevent Electron from running as plain Node.js
:: (This variable is often set by VS Code and other Electron-based IDEs)
set ELECTRON_RUN_AS_NODE=
:: Start JARVIS (Electron handles backend lifecycle automatically)
echo.
echo [2/2] Launching JARVIS...
cd /d "%PROJECT_ROOT%\frontend"
call npm run dev
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] JARVIS exited with error code %errorlevel%.
    pause
)

popd
endlocal
