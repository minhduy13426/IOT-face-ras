#!/bin/bash
# ==============================================================================
# SCRIPT CHẠY DỰ ÁN TRÊN RASPBERRY PI
# ==============================================================================

echo "=================================================="
echo "   KHI CHẠY CHƯƠNG TRÌNH TRÊN RASPBERRY PI"
echo "=================================================="

# 1. Di chuyển vào thư mục code detect_and_crop
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TARGET_DIR="$SCRIPT_DIR/FaceTrack_IOT_EDGE_COMPUTING-http-lay tu ras/detect_and_crop"

if [ -d "$TARGET_DIR" ]; then
    cd "$TARGET_DIR"
else
    cd "$SCRIPT_DIR/detect_and_crop" 2>/dev/null || cd "$SCRIPT_DIR"
fi

echo "[+] Thư mục làm việc: $(pwd)"

# 2. Kích hoạt Virtual Environment (nếu có)
if [ -d "venv" ]; then
    echo "[+] Kích hoạt virtualenv (venv)..."
    source venv/bin/activate
elif [ -d "../venv" ]; then
    echo "[+] Kích hoạt virtualenv (../venv)..."
    source ../venv/bin/activate
fi

# 3. Khởi chạy file main.py
echo "[+] Đang khởi chạy nhận diện khuôn mặt main.py..."
echo "[+] Gửi dữ liệu về Server PC: http://192.168.1.2:8001/api/attendance/process"
echo "[+] Xem Camera Stream tại: http://$(hostname -I | awk '{print $1}'):8080"
echo "=================================================="

python3 main.py

