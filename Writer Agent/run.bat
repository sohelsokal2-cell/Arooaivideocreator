@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python install kora nai. https://www.python.org/downloads/ theke install korun.
    echo.
    pause
    exit /b 1
)

if not exist ".env" (
    echo [ERROR] .env file nai. .env.example copy kore .env banan ar GEMINI_API_KEY bosan.
    echo.
    pause
    exit /b 1
)

python main.py %*

if errorlevel 1 (
    echo.
    echo [ERROR] Run failed. Uparer message dekhte paren.
)

echo.
pause
