@echo off
setlocal enabledelayedexpansion
title Minuto Inexplicavel Studio - Auto-Recuperacao e Watchdog

cd /d "%~dp0.."
set "PYTHONPATH=%CD%\src;%PYTHONPATH%"

set "PY_CMD="
py -3.11 -c "import os" >nul 2>&1
if !errorlevel! equ 0 (
    set "PY_CMD=py -3.11"
    goto found_py
)

py -c "import os" >nul 2>&1
if !errorlevel! equ 0 (
    set "PY_CMD=py"
    goto found_py
)

python -c "import os" >nul 2>&1
if !errorlevel! equ 0 (
    set "PY_CMD=python"
    goto found_py
)

:found_py
if "%PY_CMD%"=="" (
    set "PY_CMD=python"
)

%PY_CMD% src\watchdog.py --check-only >nul 2>&1
if !errorlevel! equ 0 (
    exit /b 0
)

echo =======================================================================
echo   MINUTO INEXPLICAVEL - RECUPERACAO AUTOMATICA (INSTANCIA FECHADA)
echo =======================================================================
echo.
echo [*] Nenhuma instancia ativa detectada.
echo [*] Iniciando gerador supervisionado em nova janela...

if "%~1"=="--boot" (
    echo [*] Aguardando 10 segundos para estabilizacao de rede pos-boot...
    timeout /t 10 /nobreak >nul 2>&1
)

start "Minuto Inexplicavel Studio - Gerador Autonomo (9:16)" cmd /c "%~dp0iniciar_auto_geracao.bat"

exit /b 0
