# Script PowerShell tu dong day code da cap nhat IP sang Raspberry Pi 4 (192.168.1.3)
$PI_IP = "192.168.1.3"
$PI_USER = "pi"
$LOCAL_DIR = "d:\IOT-face-ras\FaceTrack_IOT_EDGE_COMPUTING-http\detect_and_crop"

Clear-Host
Write-Host "=======================================================" -ForegroundColor Cyan
Write-Host "   DONG BO FILE CODE TU LAPTOP SANG RASPBERRY PI" -ForegroundColor Cyan
Write-Host "   Target: $PI_USER@$PI_IP" -ForegroundColor Cyan
Write-Host "=======================================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "[1/2] Dang copy main.py, model INT8 va script benchmark len Pi..." -ForegroundColor Yellow
Write-Host "      (Nhap mat khau cua Pi neu duoc hoi)" -ForegroundColor Gray

# Copy cac file can thiet sang thu muc home tren Pi
scp "$LOCAL_DIR\main.py" "$LOCAL_DIR\facenet512_int8.tflite" "$LOCAL_DIR\run_benchmark_on_pi.py" "${PI_USER}@${PI_IP}:~/"

Write-Host ""
Write-Host "[2/2] Cap nhat vao thu muc detect_and_crop tren Raspberry Pi..." -ForegroundColor Yellow

ssh -t "${PI_USER}@${PI_IP}" "mkdir -p ~/FaceTrack_IOT_EDGE_COMPUTING-http/detect_and_crop && cp ~/main.py ~/facenet512_int8.tflite ~/run_benchmark_on_pi.py ~/FaceTrack_IOT_EDGE_COMPUTING-http/detect_and_crop/ && ls -lh ~/FaceTrack_IOT_EDGE_COMPUTING-http/detect_and_crop"

Write-Host ""
Write-Host "=======================================================" -ForegroundColor Green
Write-Host "   DA DONG BO XONG CODE LEN RASPBERRY PI!" -ForegroundColor Green
Write-Host "=======================================================" -ForegroundColor Green
Write-Host "Nhan phim bat ky de thoat..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")

