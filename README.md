# HƯỚNG DẪN CHI TIẾT: HỆ THỐNG ĐIỂM DANH AI (LAPTOP + RASPBERRY PI 4)

Tài liệu này là hướng dẫn đầy đủ nhất để bạn cài đặt, vận hành và xử lý sự cố cho đồ án điểm danh khuôn mặt sử dụng Laptop làm Server và Raspberry Pi làm Client.

---

## I. CHUẨN BỊ VÀ KẾT NỐI MẠNG

### 1. Yêu cầu chung
- **Laptop**: Chạy Windows (để làm Server và Dashboard).
- **Raspberry Pi 4**: Dùng USB Webcam (để làm thiết bị nhận diện tại chỗ).
- **Mạng**: Cả 2 thiết bị phải bắt chung một Wifi hoặc cắm chung dây LAN.

### 2. Xác định IP của Laptop
Đây là bước quan trọng nhất để Pi có thể gửi dữ liệu về đúng máy:
1. Trên Laptop, nhấn `Windows + R`, gõ `cmd` rồi Enter.
2. Gõ lệnh `ipconfig`.
3. Tìm dòng **IPv4 Address** (Ví dụ: `192.168.1.50`). Hãy ghi nhớ số này.

---

## II. THIẾT LẬP SERVER (TRÊN LAPTOP)

1. **Cơ sở dữ liệu**: Đảm bảo PostgreSQL đã chạy. Vào pgAdmin chạy lệnh này một lần duy nhất:
   ```sql
   CREATE EXTENSION IF NOT EXISTS vector;
   ```
2. **Khởi động**: Vào thư mục gốc `D:\IOT-face`, chạy file **`BAT-DAU-HE-THONG.bat`**.
3. **Kiểm tra**: Mở trình duyệt vào `http://localhost:8000`. Nếu thấy giao diện Dashboard là Server đã sẵn sàng.

---

## III. THIẾT LẬP CLIENT (TRÊN RASPBERRY PI 4)

### 1. Chuyển Code lên Pi
- Dùng phần mềm **WinSCP** (trên Windows) để kéo thư mục `FaceTrack_IOT_EDGE_COMPUTING-http` sang Raspberry Pi (thư mục `/home/pi`).
- **Mẹo kết nối nhanh (SSH)**: Bạn có thể mở CMD hoặc PowerShell trên Laptop và gõ lệnh sau để điều khiển Pi mà không cần màn hình:
  ```bash
  ssh pi@<IP_CUA_PI>
  # Ví dụ: ssh pi@192.168.1.20
  ```
  (Nhập mật khẩu của Pi - mặc định thường là `raspberry` nếu bạn chưa đổi).

### 2. Cài đặt môi trường trên Pi
Mở Terminal trên Pi và chạy các lệnh sau để cài đặt các thư viện hệ thống và thư viện Python cần thiết:
```bash
# 1. Cập nhật hệ thống và cài đặt các thư viện đã build sẵn (AN TOÀN CHO THẺ NHỚ)
sudo apt update && sudo apt install -y python3-pip python3-venv python3-opencv python3-numpy python3-pil libgl1 libglib2.0-0

# 2. Di chuyển vào thư mục code
cd ~/FaceTrack_IOT_EDGE_COMPUTING-http/detect_and_crop

# 3. Tạo môi trường ảo cho phép dùng thư viện hệ thống
# (Điều này giúp dùng bản OpenCV đã cài bằng 'apt' ở trên, cực nhanh và an toàn)
python3 -m venv --system-site-packages venv
source venv/bin/activate

# 4. Cài đặt các thư viện còn lại qua pip
pip install requests Pillow
```

### 3. Cấu hình kết nối về Laptop
1. Mở file `main.py` trên Pi: `nano main.py`.
2. Sửa dòng `SERVER_URL` (dòng 11) bằng IP của Laptop bạn đã lấy ở phần I:
   ```python
   SERVER_URL = "http://192.168.1.50:8001/api/attendance/process" # Thay IP Laptop của bạn
   ```
3. Lưu và thoát (`Ctrl+O` -> `Enter` -> `Ctrl+X`).

### 4. Lệnh chạy các chức năng

#### A. Chạy nhận diện & Điểm danh (MJPEG Stream)
Đây là chương trình chính, gửi dữ liệu về Server và livestream qua web (cổng 8080):
```bash
cd ~/FaceTrack_IOT_EDGE_COMPUTING-http/detect_and_crop && source venv/bin/activate && python3 main.py
```

#### B. Chạy Tool Đăng ký khuôn mặt (Lấy mẫu dữ liệu)
Nếu bạn cần thu thập ảnh khuôn mặt mới bằng Mediapipe (nhấn 's' để lưu, 'q' để thoát):
```bash
cd ~/FaceTrack_IOT_EDGE_COMPUTING-http/detect_and_crop && source venv/bin/activate && python3 main_gui.py
```

### 5. Hướng dẫn kết nối VNC (Điều khiển màn hình từ xa)
Để xem được màn hình của Pi từ Laptop (cần thiết để chạy tool GUI):
1. **Bật VNC trên Pi (Thực hiện qua SSH từ Laptop)**:
   - Trên Laptop, mở CMD và kết nối SSH: `ssh pi@<IP_PI>`.
   - Sau khi đăng nhập, gõ lệnh: `sudo raspi-config`.
   - Dùng phím mũi tên chọn **Interfacing Options** (hoặc **Interface Options**).
   - Chọn **VNC** -> Chọn **Yes** để kích hoạt.
   - Chọn **Finish** để thoát.
2. **Cài VNC Viewer trên Laptop**: Tải và cài đặt [RealVNC Viewer](https://www.realvnc.com/en/connect/download/viewer/).
3. **Kết nối**:
   - Mở VNC Viewer trên Laptop, nhập IP của Raspberry Pi.
   - Nhập Username (`pi`) và Password để vào màn hình desktop của Pi.

---

## IV. VẬN HÀNH VÀ CHẠY THỬ (TESTING)

1. **Chạy Client**: Copy lệnh ở mục 4 phía trên dán vào terminal của Pi.
2. **Đăng ký sinh viên**: Trên Laptop (Dashboard), vào mục Đăng ký, nhập tên và chụp ảnh mẫu.
3. **Điểm danh**: Đứng trước camera của Pi. Hệ thống sẽ tự động chụp và gửi về Laptop.
4. **Xác nhận**: Xem kết quả hiện lên trên màn hình camera của Pi và danh sách trên Dashboard Laptop.

---

## V. LƯU Ý CHO USB WEBCAM VÀ SỰ CỐ

- **Cổng USB**: Luôn cắm Webcam vào cổng **USB 3.0 (màu xanh)** trên Pi 4 để tránh giật lag.
- **Kiểm tra Webcam**: Nếu không lên hình, chạy lệnh `ls /dev/video*`. Nếu thấy `/dev/video0` là Pi đã nhận.
- **Lỗi kết nối**: Nếu Pi báo "Loi ket noi", hãy thử `ping <IP_LAPTOP>` từ Pi. Nếu không thông, hãy kiểm tra lại Wifi hoặc tắt Tường lửa (Firewall) trên Laptop.
- **Ánh sáng**: Đảm bảo vị trí đặt Pi có đủ ánh sáng để nhận diện khuôn mặt chính xác nhất.

---
*Phát triển bởi Đội ngũ AIoT Project. Chúc bạn hoàn thành đồ án xuất sắc!*
