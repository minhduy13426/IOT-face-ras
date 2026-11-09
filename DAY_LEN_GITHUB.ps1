# ==============================================================================
# SCRIPT DAY TOAN BO DU AN LEN GITHUB (BO QUA FILE RAC VA BAO CAO)
# ==============================================================================
Clear-Host
Write-Host "=======================================================" -ForegroundColor Cyan
Write-Host "   DONG BO VA DAY DU AN IOT-FACE-RAS LEN GITHUB" -ForegroundColor Cyan
Write-Host "=======================================================" -ForegroundColor Cyan
Write-Host ""

# 1. Kiem tra kho Git
if (!(Test-Path ".git")) {
    Write-Host "[1/4] Khoi tao Git repository..." -ForegroundColor Yellow
    git init
    git branch -M main
} else {
    Write-Host "[1/4] Git repository da ton tai." -ForegroundColor Green
}

# 2. Hoi link GitHub neu chua co remote
$remote = git remote get-url origin 2>$null
if (!$remote) {
    Write-Host ""
    Write-Host "Chua co link Repository GitHub!" -ForegroundColor Yellow
    $repoUrl = Read-Host "-> Vui long dan link GitHub repo cua ban (vi du: https://github.com/MinhDuy134/ten-repo.git)"
    if ([string]::IsNullOrWhiteSpace($repoUrl)) {
        Write-Host "[!] Ban chua nhap link repo. Dung tien trinh." -ForegroundColor Red
        pause
        exit
    }
    git remote add origin $repoUrl.Trim()
} else {
    Write-Host "[+] Remote origin hien tai: $remote" -ForegroundColor Gray
}

# 3. Add toan bo file va Commit
Write-Host ""
Write-Host "[2/4] Dang dong goi code, model INT8 va dataset (loai bo venv va bao cao)..." -ForegroundColor Yellow
git add .

Write-Host ""
Write-Host "[3/4] Dang Commit..." -ForegroundColor Yellow
$commitMsg = "M2: Tich hop mo hinh FaceNet512 INT8 (43.5ms, 23FPS tren Pi 4) va Benchmark Suite"
git commit -m "$commitMsg"

# 4. Push len GitHub
Write-Host ""
Write-Host "[4/4] Dang day code len GitHub..." -ForegroundColor Yellow
git push -u origin main

Write-Host ""
Write-Host "=======================================================" -ForegroundColor Green
Write-Host "   HOAN TAT DAY DU AN LEN GITHUB!" -ForegroundColor Green
Write-Host "=======================================================" -ForegroundColor Green
pause

