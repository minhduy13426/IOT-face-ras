# 🚀 Hướng Dẫn Chạy Raspberry Pi Từ PowerShell Trên PC

Dưới đây là câu lệnh **Single-Quote chuẩn cho PowerShell** (đã bao gồm dấu `"` đóng ở cuối):

---

## 1. Lệnh chuẩn cho PowerShell trên PC

Sao chép toàn bộ dòng bên dưới và dán vào **PowerShell** trên PC:

```powershell
ssh -t pi@192.168.1.3 'cd ~/FaceTrack_IOT_EDGE_COMPUTING-http/detect_and_crop; if [ -d "../venv" ]; then source ../venv/bin/activate; elif [ -d "venv" ]; then source venv/bin/activate; fi; python3 main.py'
```

---

## 2. Dùng file 1-Click tự động trên Windows

Bạn chỉ cần nhấp đúp chuột vào file:
👉 [`CHAY_RASPBERRY_TU_PC.bat`](file:///d:/IOT-face-ras/CHAY_RASPBERRY_TU_PC.bat)

