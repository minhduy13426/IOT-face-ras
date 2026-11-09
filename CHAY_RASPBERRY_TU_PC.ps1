# Script PowerShell chạy Raspberry Pi từ PC qua SSH

Write-Host "=======================================================" -ForegroundColor Cyan
Write-Host "   KẾT NỐI SSH TỚI RASPBERRY PI VÀ CHẠY MAIN.PY" -ForegroundColor Cyan
Write-Host "=======================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "[+] Đang kết nối tới Raspberry Pi (192.168.1.3)..." -ForegroundColor Yellow
Write-Host "[+] Nhập mật khẩu SSH của Raspberry Pi khi được yêu cầu." -ForegroundColor Yellow
Write-Host ""

ssh -t pi@192.168.1.3 'TARGET=$(find ~ -name "main.py" 2>/dev/null | grep "detect_and_crop" | head -n 1); if [ -n "$TARGET" ]; then DIR=$(dirname "$TARGET"); echo "[+] Thu muc: $DIR"; cd "$DIR"; if [ -d "venv" ]; then source venv/bin/activate; fi; python3 main.py; else echo "[!] Khong tim thay main.py!"; fi'

