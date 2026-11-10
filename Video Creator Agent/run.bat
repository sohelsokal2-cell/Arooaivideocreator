@echo off
setlocal
cd /d "%~dp0"

set "PY=python"
if exist "C:\Users\sohel\AppData\Local\Programs\Python\Python312\python.exe" (
    set "PY=C:\Users\sohel\AppData\Local\Programs\Python\Python312\python.exe"
)

echo.
echo ========================================================
echo    বাংলা এআই ভিডিও ক্রিয়েটর - নিউজ রিল জেনারেটর
echo ========================================================
echo.

"%PY%" main.py %*

if errorlevel 1 (
    echo.
    echo ত্রুটি হয়েছে। উপরের লগ দেখুন।
    pause
) else (
    echo.
    echo ভিডিও তৈরি সম্পন্ন! output ফোল্ডারে দেখুন।
    pause
)
