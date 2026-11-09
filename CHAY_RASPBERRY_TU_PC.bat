@echo off
chcp 65001 > nul
title Chay Code Raspberry Pi qua SSH
echo =======================================================
echo   KẾT NỐI SSH TỚI RASPBERRY PI VÀ CHẠY MAIN.PY
echo =======================================================
echo.
echo Đang tìm và khởi chạy main.py trên Raspberry Pi (192.168.1.3)...
echo (Hãy nhập mật khẩu Raspberry Pi khi được yêu cầu)
echo.

ssh -t pi@192.168.1.3 "cd ~/FaceTrack_IOT_EDGE_COMPUTING-http/detect_and_crop; if [ -d '../venv' ]; then source ../venv/bin/activate; elif [ -d 'venv' ]; then source venv/bin/activate; fi; python3 main.py"

pause

