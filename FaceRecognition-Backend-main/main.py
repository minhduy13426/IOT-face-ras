"""
main.py — Backend 8001: Face Recognition Processing Server
Dự án: FaceDF - Nhận diện khuôn mặt chấm công (UIT Đồ án 2)
Port: 8001  |  Raspberry Pi gọi trực tiếp, KHÔNG có JWT auth
─────────────────────────────────────────────────────────────
Luồng xử lý:
  Pi gửi { device_id, vector } → lookup tenant từ bảng devices
  → so sánh vector với students của tenant đó
  → check_in/check_out theo lịch sử trong ngày
  → tính trạng thái (on_time / late / early_leave)
  → ghi vào attendance_logs
"""

import os
from datetime import datetime, time as dt_time, timedelta

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

# Ngưỡng nhận diện L2 cho Facenet512 (vector chưa normalize)
DISTANCE_THRESHOLD = 23.5

# Độ trễ cho phép (phút) trước khi coi là "đi trễ"
LATE_GRACE_MINUTES = 5
# Độ sớm cho phép (phút) trước khi coi là "về sớm"
EARLY_LEAVE_GRACE_MINUTES = 5

app = FastAPI(title="Face Recognition HTTP Backend — Multi-Tenant")


# ─────────────────────────────────────────────
# MODEL REQUEST
# ─────────────────────────────────────────────

class AttendanceRequest(BaseModel):
    device_id: str = "unknown"
    vector: list[float]


# ─────────────────────────────────────────────
# DATABASE
# ─────────────────────────────────────────────

def get_db_connection():
    """Tạo kết nối và đăng ký kiểu Vector cho PostgreSQL."""
    conn = psycopg2.connect(
        host=DB_HOST, database=DB_NAME,
        user=DB_USER, password=DB_PASS, port=DB_PORT
    )
    register_vector(conn)
    with conn.cursor() as cur:
        cur.execute("SET TIME ZONE 'Asia/Ho_Chi_Minh';")
    return conn


# ─────────────────────────────────────────────
# LOGIC NGHIỆP VỤ
# ─────────────────────────────────────────────

def lookup_tenant_by_device(cur, device_id: str) -> dict | None:
    """
    Tìm thông tin tenant (bao gồm shift_start, shift_end) từ device_id.
    Trả về dict hoặc None nếu không tìm thấy.
    """
    cur.execute(
        """
        SELECT d.tenant_id, t.shift_start, t.shift_end, t.name
        FROM devices d
        JOIN tenants t ON d.tenant_id = t.id
        WHERE d.device_id = %s
        """,
        (device_id,)
    )
    row = cur.fetchone()
    if not row:
        return None
    return {
        "tenant_id":   row[0],
        "shift_start": row[1],   # datetime.time
        "shift_end":   row[2],   # datetime.time
        "tenant_name": row[3],
    }


def determine_attendance_type(cur, student_id: str, tenant_id: int, today: str) -> str:
    """
    Xác định loại điểm danh: 'check_in' hoặc 'check_out'.
    Logic: Nếu trong ngày hôm nay chưa có bản ghi check_in → check_in.
           Nếu đã có check_in → check_out.
    """
    cur.execute(
        """
        SELECT id FROM attendance_logs
        WHERE student_id = %s
          AND tenant_id = %s
          AND date = %s
          AND attendance_type = 'check_in'
        LIMIT 1
        """,
        (student_id, tenant_id, today)
    )
    return "check_out" if cur.fetchone() else "check_in"


def calculate_status(
    attendance_type: str,
    current_time: dt_time,
    shift_start: dt_time,
    shift_end: dt_time
) -> str:
    """
    Tính trạng thái chấm công dựa trên loại điểm danh và ca làm việc.

    - check_in:
        on_time   : đến trước hoặc trong vòng LATE_GRACE_MINUTES sau shift_start
        late      : đến trễ hơn LATE_GRACE_MINUTES so với shift_start

    - check_out:
        on_time      : ra sau shift_end
        early_leave  : ra sớm hơn EARLY_LEAVE_GRACE_MINUTES so với shift_end
    """
    # Chuyển datetime.time → số giây từ 0h để tính toán dễ hơn
    def to_seconds(t: dt_time) -> int:
        return t.hour * 3600 + t.minute * 60 + t.second

    cur_sec   = to_seconds(current_time)
    start_sec = to_seconds(shift_start)
    end_sec   = to_seconds(shift_end)

    if attendance_type == "check_in":
        grace = LATE_GRACE_MINUTES * 60
        if cur_sec <= start_sec + grace:
            return "on_time"
        else:
            return "late"
    else:  # check_out
        grace = EARLY_LEAVE_GRACE_MINUTES * 60
        if cur_sec >= end_sec - grace:
            return "on_time"
        else:
            return "early_leave"


def process_attendance(device_id: str, vector_list: list) -> dict:
    """
    Hàm chính: Tra cứu vector, xác định sinh viên, ghi log điểm danh.
    Hỗ trợ multi-tenant qua device_id.
    """
    conn = None
    cur  = None
    try:
        # --- Kiểm tra kích thước vector ---
        if len(vector_list) != 512:
            return {
                "status":  "error",
                "message": "Kích thước Vector không hợp lệ (cần 512 chiều)"
            }

        face_vector = np.array(vector_list)
        now         = datetime.now()
        today_str   = now.strftime("%Y-%m-%d")
        current_time = now.time()

        conn = get_db_connection()
        cur  = conn.cursor()

        # --- Bước 1: Xác định tenant từ device_id ---
        tenant_info = lookup_tenant_by_device(cur, device_id)
        if not tenant_info:
            # Fallback: cho phép device chưa đăng ký (backward-compat)
            # Tìm trong tất cả students nhưng không gắn tenant
            tenant_id   = None
            shift_start = dt_time(8, 0)
            shift_end   = dt_time(17, 0)
            tenant_filter_sql = ""
            tenant_filter_val = ()
        else:
            tenant_id   = tenant_info["tenant_id"]
            shift_start = tenant_info["shift_start"]
            shift_end   = tenant_info["shift_end"]
            tenant_filter_sql = "AND tenant_id = %s"
            tenant_filter_val = (tenant_id,)

        # --- Bước 2: Tìm sinh viên có vector gần nhất (L2) trong cùng tenant ---
        search_query = f"""
            SELECT student_id, full_name, (face_vector <-> %s) AS distance
            FROM students
            WHERE 1=1 {tenant_filter_sql}
            ORDER BY face_vector <-> %s
            LIMIT 1;
        """
        cur.execute(search_query, (face_vector, *tenant_filter_val, face_vector))
        result = cur.fetchone()

        if not result:
            return {
                "status":  "error",
                "message": "Chưa có sinh viên nào trong CSDL để so sánh."
            }

        student_id, full_name, distance = result

        # --- Bước 3: So sánh với ngưỡng ---
        if distance > DISTANCE_THRESHOLD:
            return {
                "status":   "warning",
                "message":  "Không nhận diện được (Người lạ). Khoảng cách quá xa.",
                "distance": round(distance, 2)
            }

        # --- Bước 4: Tính độ tin cậy ---
        similarity_percent = max(0.0, 100.0 - (distance * 1.5))

        # --- Bước 5: Xác định check_in hay check_out ---
        attendance_type = determine_attendance_type(cur, student_id, tenant_id, today_str) \
            if tenant_id else "check_in"

        # --- Bước 6: Tính trạng thái (on_time / late / early_leave) ---
        att_status = calculate_status(attendance_type, current_time, shift_start, shift_end)

        # --- Bước 7: Ghi log vào DB ---
        insert_query = """
            INSERT INTO attendance_logs
                (student_id, device_id, similarity, tenant_id, attendance_type, status)
            VALUES (%s, %s, %s, %s, %s, %s)
        """
        cur.execute(insert_query, (
            student_id,
            device_id,
            round(similarity_percent, 2),
            tenant_id,
            attendance_type,
            att_status
        ))
        conn.commit()

        # --- Thông báo trạng thái cho Pi hiển thị ---
        type_label   = "Vào ca" if attendance_type == "check_in" else "Ra về"
        status_label = {
            "on_time":    "✅ Đúng giờ",
            "late":       "⏰ Đi trễ",
            "early_leave":"⚡ Về sớm",
        }.get(att_status, att_status)

        return {
            "status":          "success",
            "message":         f"Điểm danh thành công: {full_name}",
            "student_id":      student_id,
            "similarity":      f"{similarity_percent:.2f}%",
            "attendance_type": attendance_type,
            "type_label":      type_label,
            "att_status":      att_status,
            "status_label":    status_label,
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
    """
    Endpoint nhận diện khuôn mặt từ Raspberry Pi.
    Không yêu cầu JWT — Pi gọi trực tiếp bằng device_id.
    """
    print(f"\n[HTTP] 📩 Nhận request từ device: '{req.device_id}' | Vector size: {len(req.vector)}")
    res = process_attendance(req.device_id, req.vector)
    icon = "✅" if res.get("status") == "success" else ("⚠️" if res.get("status") == "warning" else "❌")
    print(f"[HTTP] {icon} Kết quả: {res.get('message', '')} | Type: {res.get('attendance_type', 'N/A')} | Status: {res.get('att_status', 'N/A')}")
    return res


@app.get("/api/health")
async def health_check():
    """Kiểm tra server đang chạy."""
    return {"status": "ok", "port": 8001}


@app.get("/")
async def root():
    return {"message": "Face Recognition HTTP Backend (Multi-Tenant) is running"}


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 55)
    print("  FaceDF — Face Attendance HTTP Processing Server")
    print("=" * 55)
    print(f"  DB Host  : {DB_HOST}:{DB_PORT}/{DB_NAME}")
    print(f"  Endpoint : http://0.0.0.0:8001/api/attendance/process")
    print(f"  Auth     : Không có JWT (Pi gọi trực tiếp)")
    print("=" * 55)
    uvicorn.run(app, host="0.0.0.0", port=8001)
