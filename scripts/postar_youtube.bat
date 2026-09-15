@echo off
setlocal
title Minuto Inexplicavel Studio - Postagem no YouTube Studio (Shorts)

echo =======================================================================
echo   MINUTO INEXPLICAVEL - POSTAGEM NO YOUTUBE STUDIO VIA PLAYWRIGHT
echo   Upload Autonomo de Shorts com Titulo, Descricao e Tags
echo =======================================================================
echo.

cd /d "%~dp0.."
set "PYTHONPATH=%CD%\src;%PYTHONPATH%"

echo [*] Detectando ambiente Python...
set "PY_CMD="

py -3.11 -c "import playwright" >nul 2>&1
if "%ERRORLEVEL%"=="0" (
    set "PY_CMD=py -3.11"
    goto found_python
)

py -c "import playwright" >nul 2>&1
if "%ERRORLEVEL%"=="0" (
    set "PY_CMD=py"
    goto found_python
)

python -c "import playwright" >nul 2>&1
if "%ERRORLEVEL%"=="0" (
    set "PY_CMD=python"
    goto found_python
)

:found_python
if "%PY_CMD%"=="" (
    echo [ERRO] Playwright nao encontrado. Execute:
    echo   py -3.11 -m pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)

echo [OK] Python detectado: %PY_CMD%
echo.

%PY_CMD% -m src.youtube_uploader %*

if "%ERRORLEVEL%" neq "0" (
    echo.
    echo [AVISO] Execucao finalizada com codigo de retorno: %ERRORLEVEL%
)
