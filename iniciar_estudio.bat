@echo off
setlocal enabledelayedexpansion
title Minuto Inexplicavel Studio - Shorts 9:16

echo =======================================================================
echo   MINUTO INEXPLICAVEL STUDIO - SHORTS 9:16 EDITION
echo   Iniciando estúdio WebUI Streamlit...
echo =======================================================================
echo.

cd /d "%~dp0"
set "PYTHONPATH=%CD%\src;%PYTHONPATH%"

python run.py %*

pause
