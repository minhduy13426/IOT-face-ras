import os

os.environ["TF_USE_LEGACY_KERAS"] = "1"

from dotenv import load_dotenv
import shutil
from datetime import date, datetime
from typing import List, Optional
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import numpy as np
from deepface import DeepFace
import psycopg2
from psycopg2.extras import RealDictCursor
from pgvector.psycopg2 import register_vector

load_dotenv()  # Tải biến môi trường từ file .env nếu có

app = FastAPI(title="FaceDF Smart Attendance API")

# Thông tin kết nối Database của bạn
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_NAME = os.getenv("DB_NAME", "postgres")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASS = os.getenv("DB_PASS", "")
DB_PORT = os.getenv("DB_PORT", "5432")

def get_db_connection():
    """Hàm tạo kết nối tới PostgreSQL và đăng ký kiểu dữ liệu Vector"""
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASS,
        port=DB_PORT
    )
    # Bắt buộc: Đăng ký pgvector để Python hiểu được mảng vector từ DB
    register_vector(conn)

    # Thiết lập Timezone sang Việt Nam để đồng bộ dữ liệu
    with conn.cursor() as cur:
        cur.execute("SET TIME ZONE 'Asia/Ho_Chi_Minh';")

    return conn

# Thư mục lưu trữ ảnh gốc của sinh viên
UPLOAD_DIR = "student_images"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@app.get("/api/health")
def health_check():
    """API kiểm tra kết nối cho Frontend"""
    return {"status": "ok"}

@app.get("/api/stats")
def get_stats():
    """API thống kê hiển thị trên Dashboard sử dụng Database thật"""
    # Lấy ngày hiện tại (dùng datetime để tránh lỗi Variable Shadowing)
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # 1. Đếm tổng số sinh viên có trong hệ thống
        cur.execute("SELECT COUNT(*) FROM students")
        total_students = cur.fetchone()[0]  # Lấy phần tử đầu tiên của tuple trả về
        
        # 2. Đếm số sinh viên có mặt hôm nay 
        # (Dùng DISTINCT để tránh đếm trùng nếu 1 người đứng trước camera nhiều lần)
        cur.execute("SELECT COUNT(DISTINCT student_id) FROM attendance_logs WHERE date = %s", (today_str,))
        present_today = cur.fetchone()[0]
        
    finally:
        # Luôn đảm bảo đóng kết nối CSDL dù có lỗi xảy ra hay không
        cur.close()
        conn.close()
        
    # Tính số người vắng mặt
    absent_today = total_students - present_today if total_students > present_today else 0
    
    # Tính phần trăm tỷ lệ điểm danh
    attendance_rate = round((present_today / total_students * 100), 2) if total_students > 0 else 0.0

    return {
        "total_students": total_students,
        "present_today": present_today,
        "absent_today": absent_today,
        "attendance_rate": attendance_rate,
        "date": today_str
    }

@app.get("/api/attendance")
def get_attendance(date: Optional[str] = None):
    target_date = date if date else datetime.now().strftime("%Y-%m-%d")
    
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    query = """
        SELECT a.id, a.student_id, s.full_name, a.checked_in_at, a.device_id, a.similarity, a.date
        FROM attendance_logs a
        JOIN students s ON a.student_id = s.student_id
        WHERE a.date = %s
        ORDER BY a.checked_in_at DESC
    """
    cur.execute(query, (target_date,))
    records = cur.fetchall()
    
    cur.close()
    conn.close()
    return records

@app.get("/api/students")
def get_all_students():
    conn = get_db_connection()
    # Dùng RealDictCursor để kết quả trả về dưới dạng Dictionary thay vì Tuple
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # Không select cột face_vector để API chạy nhanh và nhẹ
    cur.execute("SELECT student_id, full_name, created_at FROM students ORDER BY created_at DESC")
    students_list = cur.fetchall()
    
    cur.close()
    conn.close()
    return students_list

@app.post("/api/students")
async def register_student(
    full_name: str = Form(...),
    student_id: str = Form(...),
    images: List[UploadFile] = File(...)
):
    """Đăng ký sinh viên mới và trích xuất vector khuôn mặt"""
    if len(images) < 3:
        raise HTTPException(status_code=400, detail="Cần cung cấp ít nhất 3 bức ảnh.")
        
    # 1. Mở kết nối đến Database
    conn = get_db_connection()
    cur = conn.cursor()
    
    # 2. Truy vấn kiểm tra xem student_id đã tồn tại chưa
    # Dùng "SELECT 1" giúp tối ưu tốc độ vì CSDL không cần lấy toàn bộ dữ liệu ra
    cur.execute("SELECT 1 FROM students WHERE student_id = %s", (student_id,))
    existing_student = cur.fetchone()
    
    # 3. Đóng kết nối
    cur.close()
    conn.close()
    
    # 4. Nếu có kết quả trả về, nghĩa là sinh viên đã tồn tại
    if existing_student:
        raise HTTPException(status_code=400, detail=f"Mã số sinh viên {student_id} đã tồn tại.")

    student_dir = os.path.join(UPLOAD_DIR, student_id)
    os.makedirs(student_dir, exist_ok=True)
    
    vectors = []
    processed_count = 0
    
    for img in images:
        file_path = os.path.join(student_dir, img.filename)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(img.file, buffer)
            
        try:
            # Dùng mô hình Facenet512 để trích xuất đặc trưng
            results = DeepFace.represent(img_path=file_path, model_name="Facenet512", enforce_detection=True)
            vectors.append(results[0]["embedding"])
            processed_count += 1
        except Exception as e:
            print(f"Bỏ qua ảnh {img.filename} do không thấy rõ khuôn mặt.")
            continue
            
    if processed_count == 0:
        shutil.rmtree(student_dir)
        raise HTTPException(status_code=400, detail="Không thể nhận diện khuôn mặt trong các ảnh đã tải lên.")

    # Tính Vector trung bình từ các góc ảnh để nhận diện ổn định nhất
    avg_vector = np.mean(np.array(vectors), axis=0).tolist()
    
    # Lưu vào Database thật
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Insert vào bảng students
        cur.execute(
            "INSERT INTO students (student_id, full_name, face_vector) VALUES (%s, %s, %s)",
            (student_id, full_name, np.array(avg_vector))
        )
        conn.commit()
        cur.close()
        conn.close()
    except psycopg2.IntegrityError:
        raise HTTPException(status_code=400, detail="Mã sinh viên đã tồn tại trong Database")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    # Frontend app.js gọi: `${data.full_name} (${data.student_id}) — ${data.images_processed}`
    return {
        "full_name": full_name,
        "student_id": student_id,
        "images_processed": processed_count
    }

@app.delete("/api/students/{student_id}")
def delete_student(student_id: str):
    """Xoá sinh viên theo ID sử dụng Database thật"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Lệnh DELETE trong SQL. 
        # Nhờ có "ON DELETE CASCADE", dữ liệu bên bảng attendance_logs sẽ tự động bay màu theo.
        cur.execute("DELETE FROM students WHERE student_id = %s", (student_id,))
        
        # cur.rowcount sẽ trả về số lượng dòng bị ảnh hưởng bởi lệnh SQL trên.
        # Nếu bằng 0, nghĩa là không tìm thấy sinh viên nào mang ID đó để xóa.
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Không tìm thấy sinh viên.")
            
        # Xác nhận lưu thay đổi (xóa) vào CSDL
        conn.commit()
        
    except HTTPException:
        # Bắt lại lỗi 404 để đẩy về cho Frontend
        raise
    except Exception as e:
        # Nếu có lỗi Database khác (ví dụ rớt mạng), ta hủy bỏ thao tác xóa
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Luôn đóng kết nối để giải phóng tài nguyên
        cur.close()
        conn.close()
        
    # Bước cuối cùng: Xoá cả thư mục file ảnh trên ổ cứng của Server
    student_dir = os.path.join(UPLOAD_DIR, student_id)
    if os.path.exists(student_dir):
        shutil.rmtree(student_dir)
        
    return {"detail": "Xóa thành công"}

# ==========================================
# MOUNT FRONTEND TĨNH (STATIC FILES)
# Phải đặt ở cuối cùng để không đè lên các API routes
# ==========================================
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")