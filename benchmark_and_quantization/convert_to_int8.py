# -*- coding: utf-8 -*-
"""
Script thuc hien Post-Training Quantization (PTQ) INT8 cho mo hinh FaceNet512
Xay dung tu DeepFace.build_model("Facenet512")
Su dung tap du lieu hieu chuan (Representative Dataset) tu dataset_test/
Luu ra: facenet512_int8.tflite
"""
import os
import sys
import glob
import cv2
import numpy as np

# Thiet lap ma hoa UTF-8
if sys.platform.startswith('win'):
    sys.stdout.reconfigure(encoding='utf-8')

print("="*65)
print("   CHUONG TRINH LUONG TU HOA POST-TRAINING QUANTIZATION (INT8)")
print("   BACKBONE: FaceNet512 -> TFLite INT8")
print("="*65)

import tensorflow as tf
from deepface import DeepFace

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATASET_DIR = os.path.join(BASE_DIR, "dataset_test")
OUTPUT_BENCHMARK = os.path.join(BASE_DIR, "benchmark_and_quantization", "facenet512_int8.tflite")
OUTPUT_ROOT = os.path.join(BASE_DIR, "facenet512_int8.tflite")
OUTPUT_EDGE = os.path.join(BASE_DIR, "FaceTrack_IOT_EDGE_COMPUTING-http", "detect_and_crop", "facenet512_int8.tflite")

# 1. Thu thap anh tu dataset_test de lam Representative Dataset
image_paths = glob.glob(os.path.join(DATASET_DIR, "*", "*.jpg"))
print(f"[INFO] Tim thay {len(image_paths)} anh tu dataset_test lam tap hieu chuan Representative Dataset.")

if len(image_paths) == 0:
    print("[ERROR] Khong tim thay anh trong dataset_test! Vui long kiem tra lai duong dan.")
    sys.exit(1)

def representative_dataset_gen():
    count = 0
    for path in image_paths:
        img = cv2.imread(path)
        if img is None:
            continue
        # Resize ve dung chuan FaceNet 160x160
        img = cv2.resize(img, (160, 160))
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        
        # Chuan hoa FaceNet tieu chuan: (img - mean) / (std + 1e-7)
        mean, std = img.mean(), img.std()
        img = (img - mean) / (std + 1e-7)
        
        tensor = np.expand_dims(img, axis=0).astype(np.float32)
        yield [tensor]
        count += 1
        if count >= 100:  # Dung 100 anh hieu chuan chuan xac
            break

# 2. Xay dung mo hinh Facenet512 tu Keras
print("\n[STEP 1/3] Dang khoi tao mo hinh Keras Facenet512 tu DeepFace...")
face_model = DeepFace.build_model("Facenet512")
keras_model = face_model.model
print("[OK] Khoi tao Keras Facenet512 thanh cong.")

# 3. Thiet lap bo chuyen doi TFLiteConverter voi INT8 PTQ
print("\n[STEP 2/3] Cau hinh bo chuyen doi TFLite sang INT8 (Post-Training Quantization)...")
converter = tf.lite.TFLiteConverter.from_keras_model(keras_model)

# Kich hoat toi uu hoa mac dinh (Default optimizations)
converter.optimizations = [tf.lite.Optimize.DEFAULT]

# Gan tap du lieu dai dien de xac dinh scale va zero-point
converter.representative_dataset = representative_dataset_gen

# Su dung tap lenh so nguyen INT8 cho toan bo cac layer ho tro (ARM NEON compatible)
converter.target_spec.supported_ops = [
    tf.lite.OpsSet.TFLITE_BUILTINS_INT8,  # Cac toan tu so nguyen INT8
    tf.lite.OpsSet.TFLITE_BUILTINS        # Cho phep fallback neu co toan tu dac biet
]

# De nguyen float32 o input/output tensor de tuong thich nguyen ban voi he thong hien tai
converter.inference_input_type = tf.float32
converter.inference_output_type = tf.float32

print("[INFO] Dang thuc hien convert va luong tu hoa weights sang INT8...")
print("       (Qua trinh nay tinh toan bang phan bo tensor tren tap Representative Dataset...)")

tflite_int8_model = converter.convert()

# 4. Ghi file mo hinh INT8 ra cac thu muc can thiet
print("\n[STEP 3/3] Luu file mo hinh INT8...")
targets = [OUTPUT_BENCHMARK, OUTPUT_ROOT, OUTPUT_EDGE]

for target in targets:
    os.makedirs(os.path.dirname(target), exist_ok=True)
    with open(target, "wb") as f:
        f.write(tflite_int8_model)
    sz_mb = os.path.getsize(target) / (1024 * 1024)
    print(f"[SUCCESS] Da luu: {target} ({sz_mb:.2f} MB)")

# 5. So sanh dung luong voi ban FP32
fp32_path = os.path.join(BASE_DIR, "facenet512.tflite")
if os.path.exists(fp32_path):
    fp32_mb = os.path.getsize(fp32_path) / (1024 * 1024)
    int8_mb = len(tflite_int8_model) / (1024 * 1024)
    ratio = (1 - int8_mb / fp32_mb) * 100
    print("\n" + "="*65)
    print("   KET QUA SO SANH KICH THUOC MO HINH (FP32 vs INT8)")
    print("="*65)
    print(f" * FaceNet512 FP32 (Goc)        : {fp32_mb:.2f} MB")
    print(f" * FaceNet512 INT8 (Luong tu)   : {int8_mb:.2f} MB")
    print(f" * Ty le giam dung luong       : GIAM {ratio:.1f}% (~{fp32_mb/int8_mb:.1f}x nho hon)")
    print("="*65)

print("\n[HOAN TAT] Mo hinh INT8 da san sang de Benchmark va trien khai!")
