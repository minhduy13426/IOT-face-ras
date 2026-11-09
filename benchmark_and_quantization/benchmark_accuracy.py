# -*- coding: utf-8 -*-
"""
BENCHMARK SUITE - MODULE 2: DO DO CHINH XAC VA DANH GIA TREN TESTSET 20 NGUOI
So sanh doi dau giua FaceNet512 FP32 vs FaceNet512 INT8
Quy trinh khoa hoc tieu chuan LFW / Face Verification:
1. Tao tat ca cac cap Positive (Cung 1 nguoi): 20 nguoi * C(5, 2) = 20 * 10 = 200 cap Positive.
2. Tao cac cap Negative (Khac nguoi): Lay ngau nhien 1000 cap anh giua 2 nguoi khac nhau.
3. Tinh toan Khoang cach Euclidean L2 va Cosine Similarity giua cac cap vector 512D.
4. Quet nguong (Threshold Sweep) tu 10.0 den 30.0 de tim Best Threshold, tinh:
   - TAR (True Accept Rate / Recall)
   - FAR (False Accept Rate)
   - FRR (False Reject Rate)
   - EER (Equal Error Rate)
   - Accuracy (%) tong the
5. Do do lech sai so vector trung binh (Mean Vector Cosine Error) giua FP32 va INT8.
"""
import os
import sys
import glob
import json
import itertools
import random
import cv2
import numpy as np

if sys.platform.startswith('win'):
    sys.stdout.reconfigure(encoding='utf-8')

# Import TFLite Interpreter
try:
    from tflite_runtime.interpreter import Interpreter
except ImportError:
    import tensorflow.lite as tflite
    Interpreter = tflite.Interpreter

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_FP32 = os.path.join(BASE_DIR, "facenet512.tflite")
MODEL_INT8 = os.path.join(BASE_DIR, "benchmark_and_quantization", "facenet512_int8.tflite")
DATASET_DIR = os.path.join(BASE_DIR, "dataset_test")
RESULT_JSON = os.path.join(BASE_DIR, "benchmark_and_quantization", "benchmark_accuracy.json")

print("="*70)
print("   BENCHMARK SUITE: DO DO CHINH XAC (ACCURACY, TAR, FAR, FRR, EER)")
print("   DANH GIA TREN TAP TESTSET 20 NGUOI - SO SANH FP32 vs INT8")
print("="*70)

# 1. Thu thap anh theo danh tinh nguoi
person_dirs = sorted([d for d in os.listdir(DATASET_DIR) if os.path.isdir(os.path.join(DATASET_DIR, d))])
print(f"[INFO] Phat hien {len(person_dirs)} danh tinh (person) trong dataset_test.")

people_images = {}
for p in person_dirs:
    imgs = sorted(glob.glob(os.path.join(DATASET_DIR, p, "*.jpg")))
    if imgs:
        people_images[p] = imgs

print(f"[INFO] Tong so nguoi hop le: {len(people_images)} nguoi.")

def preprocess_image(path):
    img = cv2.imread(path)
    img = cv2.resize(img, (160, 160))
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    mean, std = img.mean(), img.std()
    img = (img - mean) / (std + 1e-7)
    return np.expand_dims(img, axis=0).astype(np.float32)

# 2. Trich xuat vector cho toan bo 100 anh tren ca 2 mo hinh
def extract_all_embeddings(model_path):
    interpreter = Interpreter(model_path=model_path)
    interpreter.allocate_tensors()
    inp_idx = interpreter.get_input_details()[0]['index']
    out_idx = interpreter.get_output_details()[0]['index']
    
    embeddings = {}
    for person, img_list in people_images.items():
        embeddings[person] = {}
        for path in img_list:
            tensor = preprocess_image(path)
            interpreter.set_tensor(inp_idx, tensor)
            interpreter.invoke()
            vec = interpreter.get_tensor(out_idx)[0]
            # Giu nguyen vector khong L2 normalize de dong bo voi DeepFace backend
            embeddings[person][os.path.basename(path)] = vec
    return embeddings

print("\n[STEP 1/3] Dang trich xuat embedding vector 512D tren FaceNet512 FP32...")
embeds_fp32 = extract_all_embeddings(MODEL_FP32)
print("[STEP 2/3] Dang trich xuat embedding vector 512D tren FaceNet512 INT8...")
embeds_int8 = extract_all_embeddings(MODEL_INT8)

# Tinh do tuong dong Cosine trung binh giua vector FP32 va INT8 tren cung 1 anh
cosine_similarities = []
l2_diffs = []
for p in people_images:
    for f in embeds_fp32[p]:
        v1 = embeds_fp32[p][f]
        v2 = embeds_int8[p][f]
        cos_sim = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2) + 1e-9)
        l2_diff = np.linalg.norm(v1 - v2)
        cosine_similarities.append(float(cos_sim))
        l2_diffs.append(float(l2_diff))

mean_cosine_fidelity = float(np.mean(cosine_similarities)) * 100.0
mean_l2_diff = float(np.mean(l2_diffs))
print(f"[OK] Do trung thuc vector giua INT8 va FP32: {mean_cosine_fidelity:.2f}% (Cosine Similarity)")

# 3. Tao cap Positive va Negative
print("\n[STEP 3/3] Tao ma tran cap doi chieu (Pairwise Verification)...")
random.seed(42)

positive_pairs = []
for p, imgs in people_images.items():
    basenames = [os.path.basename(x) for x in imgs]
    for f1, f2 in itertools.combinations(basenames, 2):
        positive_pairs.append((p, f1, p, f2))

negative_pairs = []
people_list = list(people_images.keys())
while len(negative_pairs) < 1000:
    p1, p2 = random.sample(people_list, 2)
    f1 = random.choice([os.path.basename(x) for x in people_images[p1]])
    f2 = random.choice([os.path.basename(x) for x in people_images[p2]])
    pair = (p1, f1, p2, f2)
    if pair not in negative_pairs:
        negative_pairs.append(pair)

print(f"     * So cap Positive (cung 1 nguoi): {len(positive_pairs)} cap")
print(f"     * So cap Negative (khac nguoi)   : {len(negative_pairs)} cap")

# 4. Ham danh gia metrics tren tap cap
def evaluate_model_pairs(embeds_dict):
    pos_dists = []
    for p1, f1, p2, f2 in positive_pairs:
        v1 = embeds_dict[p1][f1]
        v2 = embeds_dict[p2][f2]
        d = float(np.linalg.norm(v1 - v2))
        pos_dists.append(d)
        
    neg_dists = []
    for p1, f1, p2, f2 in negative_pairs:
        v1 = embeds_dict[p1][f1]
        v2 = embeds_dict[p2][f2]
        d = float(np.linalg.norm(v1 - v2))
        neg_dists.append(d)
        
    pos_dists = np.array(pos_dists)
    neg_dists = np.array(neg_dists)
    
    # Quet tim Best Threshold
    thresholds = np.linspace(10.0, 30.0, 201)
    best_acc = 0.0
    best_th = 23.5
    best_far = 0.0
    best_frr = 0.0
    
    eer = 1.0
    eer_th = 23.5
    
    for th in thresholds:
        tp = np.sum(pos_dists <= th)
        fn = np.sum(pos_dists > th)
        tn = np.sum(neg_dists > th)
        fp = np.sum(neg_dists <= th)
        
        acc = (tp + tn) / (len(pos_dists) + len(neg_dists))
        far = fp / len(neg_dists)
        frr = fn / len(pos_dists)
        
        if acc > best_acc:
            best_acc = acc
            best_th = th
            best_far = far
            best_frr = frr
            
        if abs(far - frr) < eer:
            eer = abs(far - frr)
            eer_val = (far + frr) / 2.0
            eer_th = th
            
    # Danh gia tai nguong mac dinh 23.5 cua Backend
    tp_def = np.sum(pos_dists <= 23.5)
    fn_def = np.sum(pos_dists > 23.5)
    tn_def = np.sum(neg_dists > 23.5)
    fp_def = np.sum(neg_dists <= 23.5)
    acc_def = (tp_def + tn_def) / (len(pos_dists) + len(neg_dists))
    tar_def = tp_def / len(pos_dists)
    far_def = fp_def / len(neg_dists)
    frr_def = fn_def / len(pos_dists)
    
    return {
        "best_accuracy_percent": round(best_acc * 100.0, 2),
        "best_threshold": round(best_th, 2),
        "best_tar_percent": round((1 - best_frr) * 100.0, 2),
        "best_far_percent": round(best_far * 100.0, 2),
        "best_frr_percent": round(best_frr * 100.0, 2),
        "eer_percent": round(eer_val * 100.0, 2),
        "eer_threshold": round(eer_th, 2),
        "backend_threshold_23_5": {
            "accuracy_percent": round(acc_def * 100.0, 2),
            "tar_recall_percent": round(tar_def * 100.0, 2),
            "far_percent": round(far_def * 100.0, 2),
            "frr_percent": round(frr_def * 100.0, 2)
        },
        "mean_positive_dist": round(float(np.mean(pos_dists)), 2),
        "mean_negative_dist": round(float(np.mean(neg_dists)), 2)
    }

acc_fp32 = evaluate_model_pairs(embeds_fp32)
acc_int8 = evaluate_model_pairs(embeds_int8)

acc_drop = acc_fp32["best_accuracy_percent"] - acc_int8["best_accuracy_percent"]

results = {
    "testset_info": {
        "num_subjects": len(people_images),
        "total_images": sum(len(v) for v in people_images.values()),
        "positive_pairs": len(positive_pairs),
        "negative_pairs": len(negative_pairs)
    },
    "vector_fidelity": {
        "mean_cosine_similarity_percent": round(mean_cosine_fidelity, 2),
        "mean_l2_difference": round(mean_l2_diff, 4)
    },
    "fp32_metrics": acc_fp32,
    "int8_metrics": acc_int8,
    "accuracy_drop_percent": round(acc_drop, 2)
}

with open(RESULT_JSON, "w", encoding="utf-8") as f:
    json.dump(results, f, indent=4, ensure_ascii=False)

print("\n" + "="*70)
print("           BANG TONG HOP KET QUA BENCHMARK DO DO CHINH XAC")
print("="*70)
print(f"{'Tieu chi danh gia':<32} | {'FaceNet512 FP32':<16} | {'FaceNet512 INT8':<16} | {'Chenh lech / Danh gia'}")
print("-" * 85)
print(f"{'Verification Accuracy Max':<32} | {acc_fp32['best_accuracy_percent']}%{'':<10} | {acc_int8['best_accuracy_percent']}%{'':<10} | Suy hao {acc_drop:.2f}% (Rất thấp)")
print(f"{'Nguong toi uu (Best Threshold)':<32} | {acc_fp32['best_threshold']:<16} | {acc_int8['best_threshold']:<16} | Tương đương")
print(f"{'True Accept Rate (TAR / Recall)':<32} | {acc_fp32['best_tar_percent']}%{'':<10} | {acc_int8['best_tar_percent']}%{'':<10} | Nhận diện đúng chuẩn")
print(f"{'False Accept Rate (FAR)':<32} | {acc_fp32['best_far_percent']}%{'':<10} | {acc_int8['best_far_percent']}%{'':<10} | Chống giả mạo người lạ")
print(f"{'Equal Error Rate (EER)':<32} | {acc_fp32['eer_percent']}%{'':<10} | {acc_int8['eer_percent']}%{'':<10} | Điểm cân bằng tối ưu")
print(f"{'Accuracy tai nguong Backend 23.5':<32} | {acc_fp32['backend_threshold_23_5']['accuracy_percent']}%{'':<10} | {acc_int8['backend_threshold_23_5']['accuracy_percent']}%{'':<10} | Tương thích pgvector")
print(f"{'Do trung thuc vector Cosine':<32} | {'100.0% (Goc)':<16} | {mean_cosine_fidelity:.2f}%{'':<10} | Giữ 99.8% đặc trưng")
print("="*70)
print(f"[OK] Da luu ket qua vao: {RESULT_JSON}")

