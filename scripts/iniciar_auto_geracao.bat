@echo off
setlocal
title Minuto Inexplicavel Studio - Modo Geracao Automatica (Batches de 10 Videos)

echo =======================================================================
echo   MINUTO INEXPLICAVEL - GERACAO AUTONOMA EM BATCHES (9:16)
echo   Sistema de Checkpoints Resiliente a Quedas de Energia
echo =======================================================================
echo.

cd /d "%~dp0.."
set "PYTHONPATH=%CD%\src;%PYTHONPATH%"

if not exist ".env" (
    echo [AVISO] Arquivo .env nao encontrado na raiz do projeto.
    echo.
)

echo [*] Detectando ambiente Python 3.11+...
set "PY_CMD="

py -3.11 -c "import google.genai, edge_tts, yt_dlp, PIL" >nul 2>&1
if "%ERRORLEVEL%"=="0" (
    set "PY_CMD=py -3.11"
    goto found_python
)

py -c "import google.genai, edge_tts, yt_dlp, PIL" >nul 2>&1
if "%ERRORLEVEL%"=="0" (
    set "PY_CMD=py"
    goto found_python
)

python -c "import google.genai, edge_tts, yt_dlp, PIL" >nul 2>&1
if "%ERRORLEVEL%"=="0" (
    set "PY_CMD=python"
    goto found_python
)

:found_python
if "%PY_CMD%"=="" (
    echo [ERRO] Interpretador Python com as dependencias necessarias nao foi encontrado.
    echo Por favor, instale as dependencias executando:
    echo   py -3.11 -m pip install -r requirements.txt
    echo.
    timeout /t 10 >nul 2>&1
    exit /b 1
)

echo [OK] Python detectado: %PY_CMD%
echo [*] Iniciando processamento em lote continuo (10 videos por batch)...
echo [*] Checkpoints salvos automaticamente em: .\checkpoint\
echo [*] Blacklist de temas ativada para impedir repeticoes.
echo.

%PY_CMD% src\auto_pipeline.py %*
set "EXIT_CODE=%ERRORLEVEL%"

if not "%EXIT_CODE%"=="0" (
    echo.
    echo [AVISO] O processo encerrou com codigo %EXIT_CODE%.
    echo Verifique os logs detalhados em .\logs\latest.log
    timeout /t 5 >nul 2>&1
)

exit /b %EXIT_CODE%
