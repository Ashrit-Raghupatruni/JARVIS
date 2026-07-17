@echo off
echo ============================================
echo   JARVIS AI Desktop Assistant - Setup
echo ============================================
echo.

:: Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH.
    echo Please install Python 3.11+ from https://python.org
    pause
    exit /b 1
)
echo [OK] Python found

:: Check Node.js
node --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Node.js is not installed or not in PATH.
    echo Please install Node.js 20+ from https://nodejs.org
    pause
    exit /b 1
)
echo [OK] Node.js found

:: Check Ollama
ollama --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [WARNING] Ollama is not installed or not in PATH.
    echo   Download from https://ollama.com/ for local AI inference.
    echo   JARVIS will fall back to Gemini/OpenAI cloud providers without it.
    echo.
) else (
    echo [OK] Ollama found
)

:: Check for .env file
if not exist ".env" (
    echo.
    echo [INFO] Creating .env file from template...
    copy .env.example .env
    echo [IMPORTANT] Edit .env to configure your LLM provider (default: ollama)
    echo.
)

:: Setup Backend
echo.
echo [1/5] Setting up Python backend...
cd backend
if not exist "venv" (
    python -m venv venv
)
call venv\Scripts\activate.bat
pip install -r requirements.txt --quiet
echo [OK] Backend dependencies installed

:: Download openwakeword models
echo.
echo [2/5] Downloading wake word models...
python -c "import openwakeword; openwakeword.utils.download_models()" 2>nul
echo [OK] Wake word models ready

:: Pull Ollama model
echo.
echo [3/5] Pulling Ollama model (qwen2.5-coder:3b)...
ollama pull qwen2.5-coder:3b 2>nul
if %errorlevel% neq 0 (
    echo [SKIP] Ollama not available - skipping model pull
) else (
    echo [OK] Ollama model ready
)

:: Install Playwright browsers
echo.
echo [4/5] Installing Playwright browsers...
playwright install chromium 2>nul
echo [OK] Playwright browsers installed

:: Initialize Prash
echo.
echo [4.5/5] Initializing Prash local AI engine...
python prash\bootstrap_prash.py --skip-training
echo [OK] Prash engine configuration and files initialized

cd ..

:: Setup Frontend
echo.
echo [5/5] Setting up frontend...
cd frontend
call npm install
cd ..

echo.
echo ============================================
echo   Setup Complete!
echo ============================================
echo.
echo Next steps:
echo   1. Make sure Ollama is running: ollama serve
echo   2. (Optional) Edit .env to add GEMINI_API_KEY for cloud fallback + vision
echo   3. Run start.bat to launch JARVIS
echo.
pause



:: Ask user if they want to launch JARVIS now
set /p LAUNCH="Launch JARVIS now? (Y/n): "
if /i "%LAUNCH%"=="n" (
    echo.
    echo   To launch JARVIS later, run: start.bat
    echo.
    pause
    exit /b 0
)

:: Launch JARVIS
echo.
echo   Launching JARVIS...
call "%~dp0start.bat"
