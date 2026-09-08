@echo off
chcp 65001 > nul
title Vietnamese TTS Dataset Builder

echo ========================================================
echo        VIETNAMESE TTS DATASET BUILDER (LOCAL)
echo ========================================================
echo.

:: Kiểm tra Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [LOI] Khong tim thay Python! Vui long cai dat Python 3.10 hoac 3.11 tai python.org
    echo Nho tich chon "Add Python to PATH" khi cai dat.
    pause
    exit /b 1
)

:: Kiểm tra FFmpeg
ffmpeg -version >nul 2>&1
if %errorlevel% neq 0 (
    echo [CANH BAO] Khong tim thay FFmpeg tren he thong PATH!
    echo Ban co the cai nhanh bang PowerShell:
    echo     winget install Gyan.FFmpeg
    echo Hoac tai tu https://www.gyan.dev/ffmpeg/builds/
    echo.
)

:: Cài đặt thư viện nếu chưa có
echo [1/2] Kiem tra thu vien phu thuoc...
pip install -r requirements.txt

:: Khởi chạy ứng dụng
echo.
echo [2/2] Dang khoi chay Gradio Web UI...
echo Sau khi hien dong "Running on local URL", trinh duyet se mo tai:
echo http://127.0.0.1:7860
echo.

python app.py
pause
