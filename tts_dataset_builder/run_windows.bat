@echo off
setlocal
chcp 65001 > nul
title Vietnamese TTS Dataset Builder
cd /d "%~dp0"

echo ========================================================
echo        VIETNAMESE TTS DATASET BUILDER (LOCAL)
echo ========================================================
echo.

set "PY_CMD="
python --version >nul 2>&1
if %errorlevel% equ 0 set "PY_CMD=python"
if not defined PY_CMD (
    py -3 --version >nul 2>&1
    if %errorlevel% equ 0 set "PY_CMD=py -3"
)
if not defined PY_CMD (
    python3 --version >nul 2>&1
    if %errorlevel% equ 0 set "PY_CMD=python3"
)
if not defined PY_CMD (
    echo [LOI] Khong tim thay Python 3!
    echo Vui long cai Python 3.10 hoac 3.11 va bat tuy chon Add Python to PATH.
    pause
    exit /b 1
)
echo [OK] Python launcher: %PY_CMD%

set "FFMPEG_OK=1"
ffmpeg -version >nul 2>&1
if %errorlevel% neq 0 set "FFMPEG_OK=0"
ffprobe -version >nul 2>&1
if %errorlevel% neq 0 set "FFMPEG_OK=0"
if "%FFMPEG_OK%"=="0" (
    echo [LOI] Khong tim thay day du FFmpeg + FFprobe tren PATH.
    echo Cai nhanh bang PowerShell:
    echo     winget install Gyan.FFmpeg
    echo Sau khi cai, dong va mo lai Terminal.
    pause
    exit /b 1
)
echo [OK] FFmpeg + FFprobe san sang.

echo [1/2] Cai dat/kiem tra thu vien phu thuoc...
%PY_CMD% -m pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [LOI] Cai thu vien that bai.
    pause
    exit /b 1
)

echo.
echo [2/2] Dang khoi chay Gradio Web UI...
echo http://127.0.0.1:7860
echo.
%PY_CMD% app.py
if %errorlevel% neq 0 (
    echo.
    echo [LOI] Ung dung ket thuc voi ma loi %errorlevel%.
)
pause
endlocal
