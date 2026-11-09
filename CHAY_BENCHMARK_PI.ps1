# Script PowerShell chay Benchmark truc tiep tren Raspberry Pi 4 (192.168.1.3)
$PI_IP = "192.168.1.3"
$PI_USER = "pi"
$LOCAL_DIR = "d:\IOT-face-ras\FaceTrack_IOT_EDGE_COMPUTING-http\detect_and_crop"

Clear-Host
Write-Host "=======================================================" -ForegroundColor Cyan
Write-Host "   BENCHMARK RASPBERRY PI 4: FP32 vs INT8" -ForegroundColor Cyan
Write-Host "   Target IP: $PI_IP" -ForegroundColor Cyan
Write-Host "=======================================================" -ForegroundColor Cyan
Write-Host ""

# 1. Kiem tra file model INT8 tren may
$INT8_FILE = "$LOCAL_DIR\facenet512_int8.tflite"
$BENCH_SCRIPT = "$LOCAL_DIR\run_benchmark_on_pi.py"

if (!(Test-Path $INT8_FILE)) {
    Write-Host "[!] Khong tim thay file facenet512_int8.tflite!" -ForegroundColor Red
    exit
}

Write-Host "[1/3] Dang copy file model INT8 va script benchmark sang Raspberry Pi..." -ForegroundColor Yellow
Write-Host "      (Vui long nhap password cua Pi neu duoc hoi)" -ForegroundColor Gray

# Copy model INT8 va script sang Pi
scp "$INT8_FILE" "$BENCH_SCRIPT" "${PI_USER}@${PI_IP}:~/"

Write-Host ""
Write-Host "[2/3] Chuyen file vao thu muc detect_and_crop tren Pi va thuc thi Benchmark..." -ForegroundColor Yellow
Write-Host ""

# Thuc hien chay tren Pi qua SSH
ssh -t "${PI_USER}@${PI_IP}" '
cd ~/FaceTrack_IOT_EDGE_COMPUTING-http/detect_and_crop 2>/dev/null || cd ~
cp ~/run_benchmark_on_pi.py . 2>/dev/null
if [ -d "../venv" ]; then source ../venv/bin/activate; elif [ -d "venv" ]; then source venv/bin/activate; fi
echo "Moi truong Python hien tai: $(which python3)"
python3 run_benchmark_on_pi.py
'

Write-Host ""
Write-Host "[3/3] HOAN TAT BENCHMARK TREN RASPBERRY PI!" -ForegroundColor Green
Write-Host "Nhan phim bat ky de thoat..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")

