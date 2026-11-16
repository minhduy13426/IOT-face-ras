"""
main.py — Admin Web Backend (Port 8000)
Dự án: FaceDF - Nhận diện khuôn mặt chấm công (UIT Đồ án 2)
─────────────────────────────────────────────────────────────
Tính năng mới (M3):
  - JWT Auth: POST /api/auth/login → access_token
  - Multi-tenant: mọi API lọc theo tenant_id từ JWT
  - Export Excel: GET /api/attendance/export/excel?date=YYYY-MM-DD
  - Summary: GET /api/attendance/summary?date=YYYY-MM-DD
  - Devices: POST /api/devices (đăng ký Camera cho tenant)
"""

import os
import io
from datetime import date, datetime, timedelta
from typing import List, Optional

import numpy as np
import psycopg2
from psycopg2.extras import RealDictCursor
from pgvector.psycopg2 import register_vector
from deepface import DeepFace
import shutil
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment

from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from jose import jwt, JWTError
from passlib.context import CryptContext

os.environ["TF_USE_LEGACY_KERAS"] = "1"
load_dotenv()

# ─────────────────────────────────────────────
# CẤU HÌNH
# ─────────────────────────────────────────────

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_NAME = os.getenv("DB_NAME", "postgres")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASS = os.getenv("DB_PASS", "123456")
DB_PORT = os.getenv("DB_PORT", "5432")

# JWT Configuration
SECRET_KEY             = os.getenv("JWT_SECRET_KEY", "facedf-super-secret-key-change-in-production")
ALGORITHM              = "HS256"
ACCESS_TOKEN_EXPIRE    = 60  # phút

# Bcrypt
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Bearer token
bearer_scheme = HTTPBearer()

UPLOAD_DIR = "student_images"
os.makedirs(UPLOAD_DIR, exist_ok=True)

app = FastAPI(title="FaceDF Admin Web API — Multi-Tenant")


# ─────────────────────────────────────────────
# DATABASE
# ─────────────────────────────────────────────

def get_db_connection():
    """Hàm tạo kết nối tới PostgreSQL và đăng ký kiểu dữ liệu Vector."""
    conn = psycopg2.connect(
        host=DB_HOST, database=DB_NAME,
        user=DB_USER, password=DB_PASS, port=DB_PORT
    )
    register_vector(conn)
    with conn.cursor() as cur:
        cur.execute("SET TIME ZONE 'Asia/Ho_Chi_Minh';")
    return conn


# ─────────────────────────────────────────────
# JWT & AUTH
# ─────────────────────────────────────────────

class LoginRequest(BaseModel):
    """Body cho API đăng nhập admin."""
    tenant_code: str    # Mã tổ chức, VD: 'UIT_CE'
    username:    str
    password:    str


def create_access_token(data: dict) -> str:
    """Tạo JWT access token với thời gian hết hạn."""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def get_current_tenant(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)
) -> int:
    """
    Dependency: Giải mã JWT, trả về tenant_id.
    Raise 401 nếu token không hợp lệ hoặc hết hạn.
    """
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        tenant_id: int = payload.get("tenant_id")
        if tenant_id is None:
            raise HTTPException(status_code=401, detail="Token không chứa tenant_id")
        return tenant_id
    except JWTError as e:
        raise HTTPException(status_code=401, detail=f"Token không hợp lệ: {str(e)}")


# ─────────────────────────────────────────────
# ENDPOINT: AUTH
# ─────────────────────────────────────────────

@app.post("/api/auth/login")
def login(req: LoginRequest):
    """
    Đăng nhập admin. Xác thực tenant_code + username + bcrypt password.
    Trả về JWT access_token.
    """
    conn = get_db_connection()
    cur  = conn.cursor()
    try:
        # Tìm tenant theo tenant_code
        cur.execute("SELECT id FROM tenants WHERE tenant_code = %s", (req.tenant_code,))
        tenant_row = cur.fetchone()
        if not tenant_row:
            raise HTTPException(status_code=401, detail="Tenant không tồn tại")

        tenant_id = tenant_row[0]

        # Tìm user trong tenant đó
        cur.execute(
            "SELECT id, password_hash FROM users WHERE tenant_id = %s AND username = %s",
            (tenant_id, req.username)
        )
        user_row = cur.fetchone()
        if not user_row:
            raise HTTPException(status_code=401, detail="Sai tên đăng nhập hoặc mật khẩu")

        user_id, password_hash = user_row

        # Xác thực password bằng bcrypt
        if not pwd_context.verify(req.password, password_hash):
            raise HTTPException(status_code=401, detail="Sai tên đăng nhập hoặc mật khẩu")

        # Tạo JWT
        access_token = create_access_token({
            "sub":       req.username,
            "tenant_id": tenant_id,
            "user_id":   user_id,
        })

        return {
            "access_token": access_token,
            "token_type":   "bearer",
            "expires_in":   ACCESS_TOKEN_EXPIRE * 60,  # giây
            "tenant_code":  req.tenant_code,
            "username":     req.username,
        }
    finally:
        cur.close()
        conn.close()


# ─────────────────────────────────────────────
# ENDPOINT: HEALTH
# ─────────────────────────────────────────────

@app.get("/api/health")
def health_check():
    """API kiểm tra kết nối cho Frontend."""
    return {"status": "ok"}


# ─────────────────────────────────────────────
# ENDPOINT: STATS (dashboard)
# ─────────────────────────────────────────────

@app.get("/api/stats")
def get_stats(tenant_id: int = Depends(get_current_tenant)):
    """API thống kê Dashboard — lọc theo tenant_id từ JWT."""
    today_str = datetime.now().strftime("%Y-%m-%d")

    conn = get_db_connection()
    cur  = conn.cursor()
    try:
        # Tổng sinh viên của tenant này
        cur.execute("SELECT COUNT(*) FROM students WHERE tenant_id = %s", (tenant_id,))
        total_students = cur.fetchone()[0]

        # Số sinh viên có check_in hôm nay (không đếm trùng)
        cur.execute(
            """
            SELECT COUNT(DISTINCT student_id) FROM attendance_logs
            WHERE tenant_id = %s AND date = %s AND attendance_type = 'check_in'
            """,
            (tenant_id, today_str)
        )
        present_today = cur.fetchone()[0]

        # Số đi trễ hôm nay
        cur.execute(
            """
            SELECT COUNT(DISTINCT student_id) FROM attendance_logs
            WHERE tenant_id = %s AND date = %s AND status = 'late'
            """,
            (tenant_id, today_str)
        )
        late_today = cur.fetchone()[0]

    finally:
        cur.close()
        conn.close()

    absent_today    = max(0, total_students - present_today)
    attendance_rate = round(present_today / total_students * 100, 2) if total_students > 0 else 0.0

    return {
        "total_students":  total_students,
        "present_today":   present_today,
        "absent_today":    absent_today,
        "late_today":      late_today,
        "attendance_rate": attendance_rate,
        "date":            today_str,
    }


# ─────────────────────────────────────────────
# ENDPOINT: ATTENDANCE LIST
# ─────────────────────────────────────────────

@app.get("/api/attendance")
def get_attendance(
    date: Optional[str] = None,
    tenant_id: int = Depends(get_current_tenant)
):
    """Lấy danh sách điểm danh theo ngày — lọc theo tenant."""
    target_date = date if date else datetime.now().strftime("%Y-%m-%d")

    conn = get_db_connection()
    cur  = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute(
            """
            SELECT a.id, a.student_id, s.full_name,
                   a.checked_in_at, a.device_id, a.similarity, a.date,
                   a.attendance_type, a.status
            FROM attendance_logs a
            JOIN students s ON a.student_id = s.student_id
            WHERE a.tenant_id = %s AND a.date = %s
            ORDER BY a.checked_in_at DESC
            """,
            (tenant_id, target_date)
        )
        records = cur.fetchall()
    finally:
        cur.close()
        conn.close()

    return list(records)


# ─────────────────────────────────────────────
# ENDPOINT: ATTENDANCE SUMMARY
# ─────────────────────────────────────────────

@app.get("/api/attendance/summary")
def get_attendance_summary(
    date: Optional[str] = None,
    tenant_id: int = Depends(get_current_tenant)
):
    """
    Thống kê điểm danh theo ngày:
    - Tổng check_in / check_out
    - Đúng giờ / Trễ / Về sớm
    """
    target_date = date if date else datetime.now().strftime("%Y-%m-%d")

    conn = get_db_connection()
    cur  = conn.cursor()
    try:
        # Thống kê theo attendance_type
        cur.execute(
            """
            SELECT attendance_type, COUNT(*) FROM attendance_logs
            WHERE tenant_id = %s AND date = %s
            GROUP BY attendance_type
            """,
            (tenant_id, target_date)
        )
        type_rows = cur.fetchall()
        type_summary = {row[0]: row[1] for row in type_rows}

        # Thống kê theo status
        cur.execute(
            """
            SELECT status, COUNT(*) FROM attendance_logs
            WHERE tenant_id = %s AND date = %s
            GROUP BY status
            """,
            (tenant_id, target_date)
        )
        status_rows  = cur.fetchall()
        status_summary = {row[0]: row[1] for row in status_rows}

        # Tổng sinh viên duy nhất có mặt
        cur.execute(
            """
            SELECT COUNT(DISTINCT student_id) FROM attendance_logs
            WHERE tenant_id = %s AND date = %s AND attendance_type = 'check_in'
            """,
            (tenant_id, target_date)
        )
        unique_present = cur.fetchone()[0]

    finally:
        cur.close()
        conn.close()

    return {
        "date":           target_date,
        "unique_present": unique_present,
        "check_in":       type_summary.get("check_in",  0),
        "check_out":      type_summary.get("check_out", 0),
        "on_time":        status_summary.get("on_time",     0),
        "late":           status_summary.get("late",         0),
        "early_leave":    status_summary.get("early_leave",  0),
    }


# ─────────────────────────────────────────────
# ENDPOINT: EXPORT EXCEL
# ─────────────────────────────────────────────

@app.get("/api/attendance/export/excel")
def export_attendance_excel(
    date: Optional[str] = None,
    tenant_id: int = Depends(get_current_tenant)
):
    """
    Xuất file Excel danh sách điểm danh theo ngày.
    Dùng thư viện openpyxl.
    """
    target_date = date if date else datetime.now().strftime("%Y-%m-%d")

    conn = get_db_connection()
    cur  = conn.cursor(cursor_factory=RealDictCursor)
    try:
        # Lấy tên tenant để ghi vào Excel
        cur.execute("SELECT name, tenant_code FROM tenants WHERE id = %s", (tenant_id,))
        tenant_row = cur.fetchone()
        tenant_name = tenant_row["name"] if tenant_row else "Unknown"

        cur.execute(
            """
            SELECT a.id, a.student_id, s.full_name,
                   a.checked_in_at, a.device_id,
                   a.similarity, a.attendance_type, a.status
            FROM attendance_logs a
            JOIN students s ON a.student_id = s.student_id
            WHERE a.tenant_id = %s AND a.date = %s
            ORDER BY a.checked_in_at ASC
            """,
            (tenant_id, target_date)
        )
        records = cur.fetchall()
    finally:
        cur.close()
        conn.close()

    # --- Tạo workbook Excel ---
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = f"Điểm danh {target_date}"

    # Style header
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
    center_align = Alignment(horizontal="center", vertical="center")

    # Tiêu đề file
    ws.merge_cells("A1:H1")
    title_cell = ws["A1"]
    title_cell.value    = f"BÁO CÁO ĐIỂM DANH — {tenant_name} — Ngày {target_date}"
    title_cell.font     = Font(bold=True, size=14)
    title_cell.alignment = center_align

    ws.row_dimensions[1].height = 30

    # Header bảng
    headers = ["STT", "Mã SV", "Họ Tên", "Thời gian", "Thiết bị", "Độ chính xác", "Loại", "Trạng thái"]
    ws.append(headers)

    header_row = ws[2]
    for cell in header_row:
        cell.font      = header_font
        cell.fill      = header_fill
        cell.alignment = center_align

    # Dữ liệu
    type_vn   = {"check_in": "Vào ca", "check_out": "Ra về"}
    status_vn = {"on_time": "Đúng giờ", "late": "Đi trễ", "early_leave": "Về sớm"}

    for idx, rec in enumerate(records, start=1):
        ws.append([
            idx,
            rec["student_id"],
            rec["full_name"],
            rec["checked_in_at"].strftime("%H:%M:%S") if rec["checked_in_at"] else "",
            rec["device_id"],
            f"{rec['similarity']:.1f}%" if rec["similarity"] else "",
            type_vn.get(rec["attendance_type"], rec["attendance_type"]),
            status_vn.get(rec["status"], rec["status"]),
        ])

    # Điều chỉnh độ rộng cột
    col_widths = [5, 15, 25, 12, 20, 15, 10, 12]
    for col_num, width in enumerate(col_widths, start=1):
        ws.column_dimensions[openpyxl.utils.get_column_letter(col_num)].width = width

    # Xuất về bytes
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    filename = f"diem_danh_{target_date.replace('-', '')}.xlsx"
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


# ─────────────────────────────────────────────
# ENDPOINT: STUDENTS
# ─────────────────────────────────────────────

@app.get("/api/students")
def get_all_students(tenant_id: int = Depends(get_current_tenant)):
    """Lấy danh sách sinh viên theo tenant."""
    conn = get_db_connection()
    cur  = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute(
            "SELECT student_id, full_name, created_at FROM students WHERE tenant_id = %s ORDER BY created_at DESC",
            (tenant_id,)
        )
        return list(cur.fetchall())
    finally:
        cur.close()
        conn.close()


@app.post("/api/students")
async def register_student(
    full_name:  str = Form(...),
    student_id: str = Form(...),
    images: List[UploadFile] = File(...),
    tenant_id: int = Depends(get_current_tenant)
):
    """Đăng ký sinh viên mới và trích xuất vector khuôn mặt cho tenant."""
    if len(images) < 3:
        raise HTTPException(status_code=400, detail="Cần cung cấp ít nhất 3 bức ảnh.")

    conn = get_db_connection()
    cur  = conn.cursor()
    try:
        # Kiểm tra student_id đã tồn tại trong tenant này chưa
        cur.execute(
            "SELECT 1 FROM students WHERE student_id = %s AND tenant_id = %s",
            (student_id, tenant_id)
        )
        if cur.fetchone():
            raise HTTPException(status_code=400, detail=f"Mã số sinh viên {student_id} đã tồn tại trong tổ chức này.")
    finally:
        cur.close()
        conn.close()

    # Lưu ảnh và trích xuất vector
    student_dir = os.path.join(UPLOAD_DIR, str(tenant_id), student_id)
    os.makedirs(student_dir, exist_ok=True)

    vectors = []
    processed_count = 0

    for img in images:
        file_path = os.path.join(student_dir, img.filename)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(img.file, buffer)
        try:
            results = DeepFace.represent(img_path=file_path, model_name="Facenet512", enforce_detection=True)
            vectors.append(results[0]["embedding"])
            processed_count += 1
        except Exception:
            try:
                results = DeepFace.represent(img_path=file_path, model_name="Facenet512",
                                              enforce_detection=False, detector_backend="skip")
                vectors.append(results[0]["embedding"])
                processed_count += 1
            except Exception as e2:
                print(f"Bỏ qua ảnh {img.filename}: {e2}")

    if processed_count == 0:
        shutil.rmtree(student_dir)
        raise HTTPException(status_code=400, detail="Không thể nhận diện khuôn mặt trong các ảnh đã tải lên.")

    avg_vector = np.mean(np.array(vectors), axis=0).tolist()

    try:
        conn = get_db_connection()
        cur  = conn.cursor()
        cur.execute(
            "INSERT INTO students (student_id, full_name, face_vector, tenant_id) VALUES (%s, %s, %s, %s)",
            (student_id, full_name, np.array(avg_vector), tenant_id)
        )
        conn.commit()
    except psycopg2.IntegrityError:
        raise HTTPException(status_code=400, detail="Mã sinh viên đã tồn tại trong Database")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cur.close()
        conn.close()

    return {"full_name": full_name, "student_id": student_id, "images_processed": processed_count}


@app.delete("/api/students/{student_id}")
def delete_student(student_id: str, tenant_id: int = Depends(get_current_tenant)):
    """Xoá sinh viên theo ID — chỉ trong phạm vi tenant hiện tại."""
    conn = get_db_connection()
    cur  = conn.cursor()
    try:
        cur.execute(
            "DELETE FROM students WHERE student_id = %s AND tenant_id = %s",
            (student_id, tenant_id)
        )
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Không tìm thấy sinh viên.")
        conn.commit()
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cur.close()
        conn.close()

    # Xóa thư mục ảnh
    student_dir = os.path.join(UPLOAD_DIR, str(tenant_id), student_id)
    if os.path.exists(student_dir):
        shutil.rmtree(student_dir)

    return {"detail": "Xóa thành công"}


# ─────────────────────────────────────────────
# ENDPOINT: DEVICES (đăng ký camera cho tenant)
# ─────────────────────────────────────────────

class DeviceRequest(BaseModel):
    device_id:   str
    description: Optional[str] = None


@app.post("/api/devices")
def register_device(
    req: DeviceRequest,
    tenant_id: int = Depends(get_current_tenant)
):
    """
    Đăng ký device_id (Raspberry Pi / Camera) cho tenant hiện tại.
    Sau khi đăng ký, Pi dùng device_id này khi gọi API 8001.
    """
    conn = get_db_connection()
    cur  = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO devices (device_id, tenant_id, description)
            VALUES (%s, %s, %s)
            ON CONFLICT (device_id) DO UPDATE
                SET tenant_id = EXCLUDED.tenant_id,
                    description = EXCLUDED.description
            """,
            (req.device_id, tenant_id, req.description)
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cur.close()
        conn.close()

    return {"detail": f"Đăng ký device '{req.device_id}' thành công cho tenant {tenant_id}"}


@app.get("/api/devices")
def list_devices(tenant_id: int = Depends(get_current_tenant)):
    """Liệt kê tất cả devices đã đăng ký cho tenant hiện tại."""
    conn = get_db_connection()
    cur  = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute(
            "SELECT device_id, description, created_at FROM devices WHERE tenant_id = %s ORDER BY created_at DESC",
            (tenant_id,)
        )
        return list(cur.fetchall())
    finally:
        cur.close()
        conn.close()


class ShiftUpdateRequest(BaseModel):
    shift_start: str  # Format: "08:00" hoac "08:00:00"
    shift_end: str    # Format: "17:00" hoac "17:00:00"

@app.get("/api/tenant/shift")
def get_tenant_shift(tenant_id: int = Depends(get_current_tenant)):
    """Lấy thông tin ca làm việc hiện tại của tổ chức."""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("SELECT tenant_code, name, shift_start, shift_end FROM tenants WHERE id = %s", (tenant_id,))
        res = cur.fetchone()
        if not res:
            raise HTTPException(status_code=404, detail="Không tìm thấy tổ chức")
        return {
            "tenant_code": res["tenant_code"],
            "name": res["name"],
            "shift_start": str(res["shift_start"])[:5] if res["shift_start"] else "08:00",
            "shift_end": str(res["shift_end"])[:5] if res["shift_end"] else "17:00"
        }
    finally:
        cur.close()
        conn.close()

@app.put("/api/tenant/shift")
def update_tenant_shift(req: ShiftUpdateRequest, tenant_id: int = Depends(get_current_tenant)):
    """Cập nhật giờ bắt đầu và giờ kết thúc ca làm việc cho tổ chức."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "UPDATE tenants SET shift_start = %s, shift_end = %s WHERE id = %s",
            (req.shift_start, req.shift_end, tenant_id)
        )
        conn.commit()
        return {"detail": "Cập nhật ca làm việc thành công!", "shift_start": req.shift_start, "shift_end": req.shift_end}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cur.close()
        conn.close()

# ─────────────────────────────────────────────
# MOUNT FRONTEND TĨNH (STATIC FILES)
# Phải đặt ở cuối cùng để không đè lên các API routes
# ─────────────────────────────────────────────
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
