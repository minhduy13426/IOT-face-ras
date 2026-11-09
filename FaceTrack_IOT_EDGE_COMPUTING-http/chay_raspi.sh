#!/bin/bash
# Script khởi chạy chương trình trên Raspberry Pi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR/detect_and_crop" || cd "$SCRIPT_DIR"

if [ -d "venv" ]; then
    source venv/bin/activate
elif [ -d "../venv" ]; then
    source ../venv/bin/activate
fi

echo "[+] Đang chạy main.py trên Raspberry Pi..."
echo "[+] Gửi dữ liệu về Server PC: http://192.168.1.2:8001/api/attendance/process"
python3 main.py

