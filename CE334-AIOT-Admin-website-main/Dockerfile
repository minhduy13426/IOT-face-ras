# 1. Sử dụng Python 3.11 bản slim để image nhẹ hơn nhưng vẫn đầy đủ tính năng
FROM python:3.11-slim

# 2. Thiết lập thư mục làm việc bên trong Container
WORKDIR /app

# 3. Cài đặt các thư viện lõi của Linux cần thiết cho OpenCV và AI
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# 4. Copy file requirements.txt vào trước để tận dụng Docker Cache
COPY requirements.txt .

# 5. Cài đặt các thư viện Python
# (Dùng --no-cache-dir để xóa file rác cài đặt, giúp image nhẹ đi hàng trăm MB)
RUN pip install --no-cache-dir -r requirements.txt

# 6. Copy toàn bộ mã nguồn của bạn vào Container
# (Nhớ cấu hình .dockerignore để không copy file .env hay thư mục __pycache__)
COPY . .

# 7. Khai báo các biến môi trường mặc định (Có thể ghi đè lúc chạy)
# Sửa lỗi xung đột Keras
ENV TF_USE_LEGACY_KERAS="1" 

# Thông số DB mặc định
ENV DB_HOST="localhost"
ENV DB_NAME="face_attendance_db"
ENV DB_USER="postgres"
ENV DB_PASS=""
ENV DB_PORT="5432"

# 8. Mở cổng 8000 để giao tiếp với bên ngoài
EXPOSE 8000

# 9. Lệnh khởi chạy Uvicorn khi Container bật lên
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
