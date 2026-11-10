@echo off
setlocal
cd /d "%~dp0"

set "PY=python"
if exist "C:\Users\sohel\AppData\Local\Programs\Python\Python312\python.exe" (
    set "PY=C:\Users\sohel\AppData\Local\Programs\Python\Python312\python.exe"
)

"%PY%" run.py %*

if errorlevel 1 (
    echo.
    echo An error occurred. Check the log above.
    pause
)
