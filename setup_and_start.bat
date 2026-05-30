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

:: Check for .env file
if not exist ".env" (
    echo.
    echo [INFO] Creating .env file from template...
    copy .env.example .env
    echo [IMPORTANT] Please edit .env and add your GEMINI_API_KEY (and optionally OPENAI_API_KEY as fallback)
    echo.
)

:: Setup Backend
echo.
echo [1/4] Setting up Python backend...
cd backend
if not exist "venv" (
    python -m venv venv
)
call venv\Scripts\activate.bat
pip install -r requirements.txt --quiet
echo [OK] Backend dependencies installed

:: Download openwakeword models
echo.
echo [2/4] Downloading wake word models...
python -c "import openwakeword; openwakeword.utils.download_models()" 2>nul
echo [OK] Wake word models ready

:: Install Playwright browsers
echo.
echo [3/4] Installing Playwright browsers...
playwright install chromium 2>nul
echo [OK] Playwright browsers installed

cd ..

:: Setup Frontend
echo.
echo [4/4] Setting up frontend...
cd frontend
call npm install
cd ..

echo.
echo ============================================
echo   Setup Complete!
echo ============================================
echo.
echo   Make sure your .env file has your GEMINI_API_KEY configured.
echo.

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
