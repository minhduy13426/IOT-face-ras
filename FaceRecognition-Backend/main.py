import os
import json
import numpy as np
import psycopg2
from pgvector.psycopg2 import register_vector
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn

load_dotenv()

# --- CẤU HÌNH DATABASE ---
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_NAME = os.getenv("DB_NAME", "postgres")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASS = os.getenv("DB_PASS", "123456")
DB_PORT = os.getenv("DB_PORT", "5432")

# Ngưỡng nhận diện (Threshold) cho Facenet512 (Chuẩn cho vector chưa normalize là 23.5)
DISTANCE_THRESHOLD = 23.5

app = FastAPI(title="Face Recognition HTTP Backend")

class AttendanceRequest(BaseModel):
    device_id: str = "unknown"
    vector: list[float]

# ─────────────────────────────────────────────
# DATABASE
# ─────────────────────────────────────────────

def get_db_connection():
    """Tạo kết nối và đăng ký kiểu Vector cho PostgreSQL"""
    conn = psycopg2.connect(
        host=DB_HOST, database=DB_NAME,
        user=DB_USER, password=DB_PASS, port=DB_PORT
    )
    register_vector(conn)
    with conn.cursor() as cur:
        cur.execute("SET TIME ZONE 'Asia/Ho_Chi_Minh';")
    return conn


def process_attendance(device_id: str, vector_list: list) -> dict:
    """Tra cứu vector trong DB và ghi log điểm danh"""
    conn = None
    cur  = None
    try:
        if len(vector_list) != 512:
            return {
                "status": "error",
                "message": "Kích thước Vector không hợp lệ (cần 512 chiều)"
            }

        face_vector = np.array(vector_list)

        conn = get_db_connection()
        cur  = conn.cursor()

        # Tìm sinh viên có khoảng cách L2 nhỏ nhất so với vector gửi lên
        search_query = """
            SELECT student_id, full_name, (face_vector <-> %s) AS distance
            FROM students
            ORDER BY face_vector <-> %s
            LIMIT 1;
        """
        cur.execute(search_query, (face_vector, face_vector))
        result = cur.fetchone()

        if not result:
            return {
                "status": "error",
                "message": "Chưa có sinh viên nào trong CSDL để so sánh."
            }

        student_id, full_name, distance = result

        if distance <= DISTANCE_THRESHOLD:
            # Tính % độ tin cậy tương ứng với ngưỡng 23.5
            similarity_percent = max(0.0, 100.0 - (distance * 1.5))

            insert_log_query = """
                INSERT INTO attendance_logs (student_id, device_id, similarity)
                VALUES (%s, %s, %s)
            """
            cur.execute(insert_log_query,
                        (student_id, device_id, round(similarity_percent, 2)))
            conn.commit()

            return {
                "status": "success",
                "message": f"Điểm danh thành công: {full_name}",
                "student_id": student_id,
                "similarity": f"{similarity_percent:.2f}%"
            }
        else:
            return {
                "status": "warning",
                "message": "Không nhận diện được (Người lạ). Khoảng cách quá xa.",
                "distance": round(distance, 2)
            }

    except Exception as e:
        if conn:
            conn.rollback()
        return {"status": "error", "message": str(e)}
    finally:
        if cur:  cur.close()
        if conn: conn.close()


# ─────────────────────────────────────────────
# HTTP ENDPOINTS
# ─────────────────────────────────────────────

@app.post("/api/attendance/process")
async def attendance_endpoint(req: AttendanceRequest):
    print(f"\n[HTTP] 📩 Nhận request từ device: '{req.device_id}' | Vector size: {len(req.vector)}")
    res = process_attendance(req.device_id, req.vector)
    status_icon = "✅" if res.get("status") == "success" else "⚠️"
    print(f"[HTTP] {status_icon} Kết quả: {res.get('message', '')}")
    return res

@app.get("/")
async def root():
    return {"message": "Face Recognition HTTP Backend is running"}

# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 50)
    print("  Face Attendance — HTTP Processing Server (FastAPI)")
    print("=" * 50)
    print(f"  DB Host : {DB_HOST}:{DB_PORT}/{DB_NAME}")
    print(f"  Endpoint: http://0.0.0.0:8001/api/attendance/process")
    print("=" * 50)

    uvicorn.run(app, host="0.0.0.0", port=8001)
