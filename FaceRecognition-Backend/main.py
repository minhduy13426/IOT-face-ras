import os
import json
import numpy as np
import psycopg2
import paho.mqtt.client as mqtt
from pgvector.psycopg2 import register_vector
from dotenv import load_dotenv

load_dotenv()

# --- CẤU HÌNH DATABASE ---
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_NAME = os.getenv("DB_NAME", "postgres")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASS = os.getenv("DB_PASS", "")
DB_PORT = os.getenv("DB_PORT", "5432")

# --- CẤU HÌNH MQTT ---
MQTT_BROKER        = os.getenv("MQTT_BROKER", "localhost")
MQTT_PORT          = int(os.getenv("MQTT_PORT", "1883"))
MQTT_TOPIC_REQUEST = "uitface/attendance/request"   # Lắng nghe yêu cầu từ Edge
MQTT_TOPIC_RESULT  = "uitface/attendance/result"    # Gửi kết quả về cho Edge

# Ngưỡng nhận diện (Threshold) cho Facenet512
# Distance 0 -> 100%, Distance 15.0 -> ~75% (mức sàn chấp nhận)
DISTANCE_THRESHOLD = 15.0

# ─────────────────────────────────────────────
# DATABASE
# ─────────────────────────────────────────────

def get_db_connection():
    """Hàm tạo kết nối và đăng ký kiểu Vector cho PostgreSQL"""
    conn = psycopg2.connect(
        host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASS, port=DB_PORT
    )
    register_vector(conn)
    # Thiết lập Timezone sang Việt Nam để CURRENT_TIMESTAMP trả về đúng giờ VN
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

        # Tìm sinh viên có khoảng cách L2 (<->) nhỏ nhất so với vector gửi lên
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
            # Tính % độ tin cậy: distance=0 -> 100%, distance=15 -> ~75%
            similarity_percent = max(0.0, 100.0 - (distance * 1.67))

            # Ghi vào bảng attendance_logs
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
            # Khuôn mặt lạ,khoảng cách vượt ngưỡng
            return {
                "status": "warning",
                "message": "Không nhận diện được khuôn mặt (Người lạ). Khoảng cách quá xa.",
                "distance": round(distance, 2)
            }

    except Exception as e:
        if conn:
            conn.rollback()  # Hoàn tác nếu có lỗi DB
        return {"status": "error", "message": str(e)}
    finally:
        if cur:  cur.close()
        if conn: conn.close()


# ─────────────────────────────────────────────
# MQTT CALLBACKS
# ─────────────────────────────────────────────

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(f"[MQTT] Ket noi broker thanh cong: {MQTT_BROKER}:{MQTT_PORT}")
        client.subscribe(MQTT_TOPIC_REQUEST)
        print(f"[MQTT] Dang lang nghe topic: '{MQTT_TOPIC_REQUEST}'")
    else:
        print(f"[MQTT] Ket noi that bai, ma loi: {rc}")


def on_message(client, userdata, msg):
    """Nhận yêu cầu điểm danh từ Edge, xử lý, rồi publish kết quả trở lại"""
    print(f"\n[MQTT] Nhan tin tu topic: {msg.topic}")
    try:
        payload   = json.loads(msg.payload.decode("utf-8"))
        device_id = payload.get("device_id", "unknown")
        vector    = payload.get("vector", [])

        print(f"[MQTT] Dang xu ly tu device: '{device_id}' | vector dim: {len(vector)}")

        result = process_attendance(device_id, vector)
        result["device_id"] = device_id  # Đính kèm để Edge phân biệt kết quả của mình

        # Publish kết quả về topic result để Edge nhận
        client.publish(
            MQTT_TOPIC_RESULT,
            json.dumps(result, ensure_ascii=False)
        )
        print(f"[MQTT] Da gui ket qua: [{result['status']}] {result.get('message', '')}")

    except json.JSONDecodeError:
        err = {"status": "error", "message": "Payload JSON khong hop le"}
        client.publish(MQTT_TOPIC_RESULT, json.dumps(err))
        print("[MQTT] LOI: Khong parse duoc JSON tu Edge")
    except Exception as e:
        err = {"status": "error", "message": str(e)}
        client.publish(MQTT_TOPIC_RESULT, json.dumps(err))
        print(f"[MQTT] LOI xu ly: {e}")


def on_disconnect(client, userdata, rc):
    if rc != 0:
        print(f"[MQTT] Mat ket noi broker (rc={rc}). Dang thu ket noi lai...")


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 50)
    print("  Face Attendance — MQTT Processing Server")
    print("=" * 50)
    print(f"  DB    : {DB_HOST}:{DB_PORT}/{DB_NAME}")
    print(f"  Broker: {MQTT_BROKER}:{MQTT_PORT}")
    print(f"  Sub   : {MQTT_TOPIC_REQUEST}")
    print(f"  Pub   : {MQTT_TOPIC_RESULT}")
    print("=" * 50)

    client = mqtt.Client(client_id="FaceAttendance_Backend_01")
    client.on_connect    = on_connect
    client.on_message    = on_message
    client.on_disconnect = on_disconnect

    # Tự động kết nối lại khi mất mạng
    client.reconnect_delay_set(min_delay=1, max_delay=30)

    try:
        client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
        client.loop_forever()   # Blocking loop — xử lý tin nhắn liên tục
    except KeyboardInterrupt:
        print("\n[MQTT] Da dung server.")
        client.disconnect()
    except Exception as e:
        print(f"[MQTT] Khong the ket noi broker: {e}")
        print("       Hay chac chan MQTT broker (mosquitto) dang chay.")
