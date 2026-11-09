@echo off
chcp 65001 > nul
set PYTHONIOENCODING=utf-8
title He thong Diem danh AI - Master Controller
echo Dang khoi dong cac thanh phan tren PC...

set PYTHON_BIN="%~dp0venv\Scripts\python.exe"
if not exist %PYTHON_BIN% (
    set PYTHON_BIN=python
)

:: 1. Chay Admin Website (Port 8000)
echo [1/2] Dang khoi dong Admin Dashboard (Port 8000)...
start "Server: Admin Dashboard" cmd /k "cd /d "%~dp0CE334-AIOT-Admin-website-main" && %PYTHON_BIN% -m uvicorn main:app --host 0.0.0.0 --port 8000"

:: 2. Chay Attendance Processing API (Port 8001)
echo [2/2] Dang khoi dong Processing API (Port 8001)...
start "Server: Processing API" cmd /k "cd /d "%~dp0CE344-AIOT-FaceRecognition-Backend-main" && %PYTHON_BIN% main.py"

echo.
echo =======================================================
echo Tat ca dich vu tren PC da duoc khoi dong!
echo - Admin Dashboard : http://localhost:8000 (hoac http://192.168.1.2:8000)
echo - Processing API  : http://192.168.1.2:8001/api/attendance/process
echo =======================================================
pause

