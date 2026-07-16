import cv2
import os
import time
import threading
import json
import paho.mqtt.client as mqtt
from http.server import BaseHTTPRequestHandler, HTTPServer
import socketserver
from PIL import Image, ImageDraw, ImageFont
import numpy as np

try:
    from tflite_runtime.interpreter import Interpreter
except ImportError:
    try:
        from ai_edge_litert.interpreter import Interpreter
    except ImportError:
        import tensorflow.lite as tflite
        Interpreter = tflite.Interpreter

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
MQTT_BROKER        = "192.168.1.3"      # IP máy chủ chạy MQTT broker
MQTT_PORT          = 1883
MQTT_TOPIC_REQUEST = "uitface/attendance/request"   # Gửi vector lên đây
MQTT_TOPIC_RESULT  = "uitface/attendance/result"    # Lắng nghe kết quả ở đây
DEVICE_ID          = "Raspi_Door_01"

STREAM_PORT        = 8080
MIN_FACE_AREA_RATIO = 0.2
HOLD_TIME_SECONDS   = 1.0

# ─────────────────────────────────────────────
# HAAR CASCADE (Tìm kiếm đường dẫn trên Pi)
# ─────────────────────────────────────────────
def get_haar_path(filename):
    paths = [
        "/usr/share/opencv4/haarcascades/",
        "/usr/share/opencv/haarcascades/",
        "/usr/share/opencv4/data/haarcascades/",
        os.path.join(os.getcwd(), "haarcascades/"),
        os.getcwd()
    ]
    if hasattr(cv2, 'data') and hasattr(cv2.data, 'haarcascades'):
        paths.append(cv2.data.haarcascades)
    for p in paths:
        full_path = os.path.join(p, filename)
        if os.path.exists(full_path):
            return full_path
    return None

face_xml = get_haar_path('haarcascade_frontalface_default.xml')
eye_xml  = get_haar_path('haarcascade_eye.xml')

if not face_xml:
    print("CRITICAL ERROR: Không tìm thấy haarcascade_frontalface_default.xml!")
    print("Vui lòng chạy: sudo apt install libopencv-dev")
    exit(1)

face_cascade = cv2.CascadeClassifier(face_xml)
eye_cascade  = cv2.CascadeClassifier(eye_xml) if eye_xml else None

# ─────────────────────────────────────────────
# TFLITE FACENET512 SETUP
# ─────────────────────────────────────────────
FACENET_MODEL_PATH = "facenet512.tflite"
interpreter    = None
input_details  = None
output_details = None

try:
    interpreter = Interpreter(model_path=FACENET_MODEL_PATH)
    interpreter.allocate_tensors()
    input_details  = interpreter.get_input_details()
    output_details = interpreter.get_output_details()
    print("--- Da load model Facenet512 TFLite thanh cong! ---")
except Exception as e:
    print(f"WARNING: Loi load model Facenet512: {e}")
    print("Vui long chay convert_model.py de lay file facenet512.tflite.")

def extract_face_vector(face_img):
    if interpreter is None:
        return None
    img = cv2.resize(face_img, (160, 160))
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    mean, std = img.mean(), img.std()
    img = (img - mean) / (std + 1e-7)
    input_data = np.expand_dims(img, axis=0).astype(np.float32)
    interpreter.set_tensor(input_details[0]['index'], input_data)
    interpreter.invoke()
    vector = interpreter.get_tensor(output_details[0]['index'])[0]
    return vector.tolist()

# ─────────────────────────────────────────────
# TIẾNG VIỆT FONT
# ─────────────────────────────────────────────
def draw_text_vietnamese(image, text, position, font_size, color):
    img_pil = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
    draw    = ImageDraw.Draw(img_pil)
    font_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSans.ttf"
    ]
    font = None
    for path in font_paths:
        try:
            font = ImageFont.truetype(path, font_size)
            break
        except:
            continue
    if font is None:
        font = ImageFont.load_default()
    draw.text(position, text, font=font, fill=color)
    return cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)

# ─────────────────────────────────────────────
# BIẾN TOÀN CỤC — Kết quả điểm danh
# ─────────────────────────────────────────────
last_result  = ""
result_time  = 0
result_color = (0, 255, 0)
result_id    = 0
result_lock  = threading.Lock()

# ─────────────────────────────────────────────
# MQTT CLIENT
# ─────────────────────────────────────────────
def mqtt_on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(f"[MQTT] Kết nối broker thành công: {MQTT_BROKER}:{MQTT_PORT}")
        client.subscribe(MQTT_TOPIC_RESULT)
        print(f"[MQTT] Lắng nghe kết quả tại topic: '{MQTT_TOPIC_RESULT}'")
    else:
        print(f"[MQTT] Kết nối thất bại, mã lỗi: {rc}")

def mqtt_on_message(client, userdata, msg):
    """Callback khi nhận kết quả điểm danh từ Cloud Server"""
    global last_result, result_color, result_id, result_time
    try:
        data    = json.loads(msg.payload.decode("utf-8"))
        raw_msg = data.get("message", "")
        status  = data.get("status", "")
        
        # Chỉ xử lý nếu kết quả gửi đến tương ứng với thiết bị này
        device_id_in_msg = data.get("device_id", "")
        if device_id_in_msg and device_id_in_msg != DEVICE_ID:
            return

        with result_lock:
            if status == "success":
                name = raw_msg.split(": ")[-1] if ": " in raw_msg else "N/A"
                mssv = data.get("student_id", "N/A")
                last_result  = f"Thành công: {name} - {mssv}"
                result_color = (0, 255, 0)   # Xanh lá
            elif status == "warning":
                last_result  = "Không tìm thấy sinh viên"
                result_color = (0, 0, 255)   # Đỏ
            else:
                last_result  = f"Lỗi: {raw_msg}"
                result_color = (0, 165, 255) # Cam

            result_id  += 1
            result_time = time.time()

        print(f"[MQTT] Kết quả nhận: [{status}] {raw_msg}")

    except Exception as e:
        with result_lock:
            last_result  = "Lỗi đọc kết quả MQTT"
            result_color = (0, 165, 255)
            result_id   += 1
            result_time  = time.time()
        print(f"[MQTT] Lỗi parse kết quả: {e}")

def mqtt_on_disconnect(client, userdata, rc):
    if rc != 0:
        print(f"[MQTT] Mất kết nối broker (rc={rc}). Đang thử kết nối lại...")

# Khởi tạo MQTT client
mqtt_client = mqtt.Client(client_id=f"{DEVICE_ID}_mqtt")
mqtt_client.on_connect    = mqtt_on_connect
mqtt_client.on_message    = mqtt_on_message
mqtt_client.on_disconnect = mqtt_on_disconnect
mqtt_client.reconnect_delay_set(min_delay=1, max_delay=30)

try:
    mqtt_client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
    mqtt_client.loop_start()   # Chạy MQTT trong thread nền
    print(f"[MQTT] Đang kết nối đến broker: {MQTT_BROKER}:{MQTT_PORT} ...")
except Exception as e:
    print(f"[MQTT] CẢNH BÁO: Không kết nối được broker — {e}")
    print("       Hãy đảm bảo MQTT broker (mosquitto) đang chạy trên Server.")

# ─────────────────────────────────────────────
# MJPEG STREAM SERVER
# ─────────────────────────────────────────────
output_frame = None
raw_frame    = None
frame_lock   = threading.Lock()

class MJPEGStreamHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/log':
            self.send_response(200)
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Content-type', 'application/json; charset=utf-8')
            self.end_headers()
            with result_lock:
                data = {"msg": last_result, "color": list(result_color), "id": result_id}
            self.wfile.write(json.dumps(data).encode('utf-8'))
            return

        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Content-type', 'multipart/x-mixed-replace; boundary=frame')
        self.end_headers()
        try:
            while True:
                with frame_lock:
                    frame_to_send = raw_frame if self.path.startswith('/raw') else output_frame
                    if frame_to_send is None:
                        continue
                    _, jpeg = cv2.imencode('.jpg', frame_to_send,
                                          [cv2.IMWRITE_JPEG_QUALITY, 70])
                self.wfile.write(b'--frame\r\nContent-Type: image/jpeg\r\n\r\n')
                self.wfile.write(jpeg.tobytes())
                self.wfile.write(b'\r\n')
                time.sleep(0.04)
        except:
            pass

    def log_message(self, *args):
        pass   # Tắt log HTTP mặc định

class ThreadingHTTPServer(socketserver.ThreadingMixIn, HTTPServer):
    daemon_threads = True

threading.Thread(
    target=lambda: ThreadingHTTPServer(
        ('0.0.0.0', STREAM_PORT), MJPEGStreamHandler
    ).serve_forever(),
    daemon=True
).start()

# ─────────────────────────────────────────────
# CAMERA
# ─────────────────────────────────────────────
cap = cv2.VideoCapture(0, cv2.CAP_V4L2)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

if not cap.isOpened():
    print("ERROR: Khong the mo Camera! Kiem tra index hoac ket noi.")
    exit(1)

width  = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
print(f"--- Camera dang chay o do phan gia: {width}x{height} ---")
print(f"--- He thong san sang! OBS xem tai: http://<IP_PI>:{STREAM_PORT} ---")

# ─────────────────────────────────────────────
# VÒNG LẶP CHÍNH
# ─────────────────────────────────────────────
face_start_time = None
face_processed  = False

while True:
    ret, frame = cap.read()
    if not ret:
        break

    frame_raw_copy = frame.copy()
    gray  = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    faces = face_cascade.detectMultiScale(gray, 1.3, 5)

    has_face    = False
    display_msg = ""
    rect_color  = (255, 0, 0)   # Mặc định xanh dương

    if len(faces) > 0:
        # Lấy khuôn mặt to nhất
        x, y, w_f, h_f = sorted(faces, key=lambda f: f[2] * f[3], reverse=True)[0]

        # Yêu cầu mặt chiếm ít nhất 50% chiều rộng khung hình
        if w_f < frame.shape[1] * 0.5:
            rect_color  = (0, 0, 255)
            display_msg = "Tiến lại gần hơn"
            face_start_time = None
        else:
            # Kiểm tra nhìn thẳng (tìm mắt)
            roi_gray = gray[y:y + h_f, x:x + w_f]
            eyes     = eye_cascade.detectMultiScale(roi_gray) if eye_cascade else [1]  # skip nếu ko load được

            if len(eyes) >= 1:
                has_face    = True
                rect_color  = (255, 0, 0)
                display_msg = "Giữ nguyên khuôn mặt"

                if face_start_time is None:
                    face_start_time = time.time()
                elif (time.time() - face_start_time >= HOLD_TIME_SECONDS
                      and not face_processed):
                    face_roi = frame[y:y + h_f, x:x + w_f]
                    cv2.putText(frame, "Dang trich xuat...",
                                (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                                (0, 255, 255), 2)

                    vector = extract_face_vector(face_roi)

                    if vector is not None:
                        # ── MQTT: Gửi vector lên Cloud ──
                        payload = {
                            "device_id": DEVICE_ID,
                            "vector":    vector
                        }
                        try:
                            mqtt_client.publish(
                                MQTT_TOPIC_REQUEST,
                                json.dumps(payload)
                            )
                            print(f"[MQTT] Đã gửi vector lên topic: '{MQTT_TOPIC_REQUEST}'")
                        except Exception as e:
                            with result_lock:
                                last_result  = "Lỗi gửi MQTT"
                                result_color = (0, 0, 255)
                                result_id   += 1
                                result_time  = time.time()
                            print(f"[MQTT] Lỗi publish: {e}")
                    else:
                        with result_lock:
                            last_result  = "Lỗi TFLite"
                            result_color = (0, 0, 255)
                            result_id   += 1
                            result_time  = time.time()

                    face_processed = True
            else:
                rect_color  = (0, 0, 255)
                display_msg = "Hãy nhìn thẳng vào Camera"

        cv2.rectangle(frame, (x, y), (x + w_f, y + h_f), rect_color, 2)
        if display_msg:
            color_pil = (rect_color[2], rect_color[1], rect_color[0])
            frame = draw_text_vietnamese(frame, display_msg, (x, y - 30), 20, color_pil)
    else:
        face_start_time = None
        face_processed  = False

    # Hiển thị kết quả trong 3 giây
    with result_lock:
        _last = last_result
        _col  = result_color
        _time = result_time

    if _last and (time.time() - _time < 3):
        color_pil = (_col[2], _col[1], _col[0])
        frame = draw_text_vietnamese(frame, _last, (20, 50), 22, color_pil)
    elif _last and (time.time() - _time >= 3):
        with result_lock:
            last_result = ""

    with frame_lock:
        raw_frame    = frame_raw_copy
        output_frame = frame.copy()

    if cv2.waitKey(1) == 27:
        break

cap.release()
mqtt_client.loop_stop()
mqtt_client.disconnect()
