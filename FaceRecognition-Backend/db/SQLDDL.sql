-- 1. BẮT BUỘC: Kích hoạt extension pgvector trong database hiện tại
CREATE EXTENSION IF NOT EXISTS vector;

-- 2. Tạo bảng Quản lý Sinh viên
CREATE TABLE students (
    student_id VARCHAR(50) PRIMARY KEY,
    full_name VARCHAR(100) NOT NULL,
    face_vector vector(512), -- Lưu mảng 512 chiều từ FaceNet512
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 3. Tạo Index HNSW cho cột face_vector
-- Đây là thuật toán giúp tăng tốc độ tìm kiếm khuôn mặt lên hàng nghìn lần
-- khi lớp học/trường học của bạn scale lên số lượng sinh viên lớn.
CREATE INDEX ON students USING hnsw (face_vector vector_l2_ops);

-- 4. Tạo bảng Lịch sử Điểm danh
CREATE TABLE attendance_logs (
    id SERIAL PRIMARY KEY,
    student_id VARCHAR(50) REFERENCES students(student_id) ON DELETE CASCADE,
    device_id VARCHAR(50),      -- Ghi nhận điểm danh từ Camera nào (VD: 'Cam_Door_1')
    similarity FLOAT,           -- Độ chính xác lúc nhận diện (VD: 0.85)
    checked_in_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    date DATE DEFAULT CURRENT_DATE -- Tách riêng ngày để API thống kê chạy siêu nhanh
);