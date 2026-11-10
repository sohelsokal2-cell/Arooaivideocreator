@echo off
chcp 65001 >nul
title AI Reels Creator - Bangalii Facts
cd /d "%~dp0"
python run_pipeline.py
pause

