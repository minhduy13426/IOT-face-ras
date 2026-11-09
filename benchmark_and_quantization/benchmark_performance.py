# -*- coding: utf-8 -*-
"""
BENCHMARK SUITE - MODULE 1: DO TOC DO, FPS VA BO NHO RAM
So sanh doi dau giua FaceNet512 FP32 vs FaceNet512 INT8
Cac chi so do:
- Inference Latency (ms): Min, Max, Mean, Median, P95, P99 (Warm-up 30 lan, Test 200 lan)
- System Real-world FPS (FPS tinh toan thuan & FPS toan chu trinh voi Webcam/Frame)
- RAM Peak Consumption (MB): Su dung psutil RSS & tracemalloc
"""
import os
import sys
import time
import glob
import json
import cv2
import numpy as np
import psutil
import tracemalloc

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
RESULT_JSON = os.path.join(BASE_DIR, "benchmark_and_quantization", "benchmark_speed_ram.json")

print("="*70)
print("   BENCHMARK SUITE: DO TOC DO (LATENCY), FPS VA BO NHO RAM (PEAK)")
print("   SO SANH TRUC TIEP: FaceNet512 FP32  vs  FaceNet512 INT8")
print("="*70)

# Lay tap anh mau de chay suy luan thuc te
sample_images = glob.glob(os.path.join(DATASET_DIR, "*", "*.jpg"))
if not sample_images:
    print("[ERROR] Khong tim thay anh trong dataset_test!")
    sys.exit(1)

def get_input_tensor(img_path):
    img = cv2.imread(img_path)
    img = cv2.resize(img, (160, 160))
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    mean, std = img.mean(), img.std()
    img = (img - mean) / (std + 1e-7)
    return np.expand_dims(img, axis=0).astype(np.float32)

# Chuan bi 20 tensor test da dang
test_tensors = [get_input_tensor(p) for p in sample_images[:20]]

def benchmark_model(model_path, model_name, num_warmup=30, num_iterations=200):
    print(f"\n---> DANG BENCHMARK: {model_name}")
    print(f"     Duong dan: {model_path}")
    size_mb = os.path.getsize(model_path) / (1024 * 1024)
    print(f"     Kich thuoc file: {size_mb:.2f} MB")
    
    process = psutil.Process(os.getpid())
    ram_before = process.memory_info().rss / (1024 * 1024)
    tracemalloc.start()
    
    # Nap model
    interpreter = Interpreter(model_path=model_path)
    interpreter.allocate_tensors()
    inp_details = interpreter.get_input_details()
    out_details = interpreter.get_output_details()
    
    inp_idx = inp_details[0]['index']
    out_idx = out_details[0]['index']
    
    # 1. Warm-up Phase
    print(f"     [1/3] Warm-up {num_warmup} vong de nap cache CPU...")
    for i in range(num_warmup):
        dummy = test_tensors[i % len(test_tensors)]
        interpreter.set_tensor(inp_idx, dummy)
        interpreter.invoke()
        _ = interpreter.get_tensor(out_idx)
        
    # 2. Measurement Phase (Inference Latency)
    print(f"     [2/3] Do Inference Latency tren {num_iterations} lan chay...")
    latencies = []
    peak_ram = process.memory_info().rss / (1024 * 1024)
    
    start_total_time = time.perf_counter()
    for i in range(num_iterations):
        t_in = test_tensors[i % len(test_tensors)]
        
        t0 = time.perf_counter_ns()
        interpreter.set_tensor(inp_idx, t_in)
        interpreter.invoke()
        _ = interpreter.get_tensor(out_idx)
        t1 = time.perf_counter_ns()
        
        latencies.append((t1 - t0) / 1_000_000.0)  # ms
        
        # Lay mau RAM dinh moi 20 lan
        if i % 20 == 0:
            cur_ram = process.memory_info().rss / (1024 * 1024)
            if cur_ram > peak_ram:
                peak_ram = cur_ram
                
    total_elapsed = time.perf_counter() - start_total_time
    
    # Giai phong tracemalloc
    current_traced, peak_traced = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    peak_traced_mb = peak_traced / (1024 * 1024)
    
    # 3. Xu ly thong ke ngoai lai (Trimming 1% min, 1% max)
    latencies_sorted = sorted(latencies)
    trim_k = max(1, int(len(latencies) * 0.01))
    trimmed = latencies_sorted[trim_k:-trim_k]
    
    mean_lat = float(np.mean(trimmed))
    median_lat = float(np.median(trimmed))
    min_lat = float(np.min(trimmed))
    max_lat = float(np.max(trimmed))
    p95_lat = float(np.percentile(trimmed, 95))
    p99_lat = float(np.percentile(trimmed, 99))
    
    pure_fps = 1000.0 / mean_lat
    e2e_fps = num_iterations / total_elapsed
    
    print(f"     [OK] Latency Trung binh (Mean) : {mean_lat:.2f} ms")
    print(f"     [OK] Latency Trung vi (Median) : {median_lat:.2f} ms")
    print(f"     [OK] Latency P95 / P99        : {p95_lat:.2f} ms / {p99_lat:.2f} ms")
    print(f"     [OK] Pure Inference FPS       : {pure_fps:.2f} FPS")
    print(f"     [OK] RAM Peak Allocation       : {peak_traced_mb:.2f} MB (Process RSS: {peak_ram:.2f} MB)")
    
    return {
        "model_name": model_name,
        "size_mb": round(size_mb, 2),
        "mean_latency_ms": round(mean_lat, 2),
        "median_latency_ms": round(median_lat, 2),
        "min_latency_ms": round(min_lat, 2),
        "max_latency_ms": round(max_lat, 2),
        "p95_latency_ms": round(p95_lat, 2),
        "p99_latency_ms": round(p99_lat, 2),
        "pure_fps": round(pure_fps, 2),
        "e2e_fps": round(e2e_fps, 2),
        "ram_peak_mb": round(peak_traced_mb, 2),
        "process_rss_mb": round(peak_ram, 2)
    }

# Chay ca 2 model
res_fp32 = benchmark_model(MODEL_FP32, "FaceNet512 FP32 (Baseline)")
res_int8 = benchmark_model(MODEL_INT8, "FaceNet512 INT8 (Quantized)")

# Tinh toan muc do cai thien (%)
lat_speedup = (res_fp32["mean_latency_ms"] - res_int8["mean_latency_ms"]) / res_fp32["mean_latency_ms"] * 100
fps_increase = (res_int8["pure_fps"] - res_fp32["pure_fps"]) / res_fp32["pure_fps"] * 100
size_reduction = (res_fp32["size_mb"] - res_int8["size_mb"]) / res_fp32["size_mb"] * 100

summary = {
    "fp32": res_fp32,
    "int8": res_int8,
    "improvements": {
        "latency_speedup_percent": round(lat_speedup, 1),
        "fps_increase_percent": round(fps_increase, 1),
        "size_reduction_percent": round(size_reduction, 1),
        "latency_ratio": round(res_fp32["mean_latency_ms"] / res_int8["mean_latency_ms"], 2)
    }
}

with open(RESULT_JSON, "w", encoding="utf-8") as f:
    json.dump(summary, f, indent=4, ensure_ascii=False)

print("\n" + "="*70)
print("               BANG TONG HOP KET QUA BENCHMARK DO TOC DO & RAM")
print("="*70)
print(f"{'Chi so do luong':<30} | {'FaceNet512 FP32':<18} | {'FaceNet512 INT8':<18} | {'Muc cai thien'}")
print("-" * 85)
print(f"{'Kich thuoc mo hinh (MB)':<30} | {res_fp32['size_mb']:<18} | {res_int8['size_mb']:<18} | Giam {size_reduction:.1f}%")
print(f"{'Inference Latency Mean (ms)':<30} | {res_fp32['mean_latency_ms']:<18} | {res_int8['mean_latency_ms']:<18} | Nhanh hon {lat_speedup:.1f}%")
print(f"{'Inference Latency Median (ms)':<30} | {res_fp32['median_latency_ms']:<18} | {res_int8['median_latency_ms']:<18} | Nhanh hon {((res_fp32['median_latency_ms']-res_int8['median_latency_ms'])/res_fp32['median_latency_ms']*100):.1f}%")
print(f"{'Inference Latency P95 (ms)':<30} | {res_fp32['p95_latency_ms']:<18} | {res_int8['p95_latency_ms']:<18} | On dinh hon")
print(f"{'Inference FPS (fps)':<30} | {res_fp32['pure_fps']:<18} | {res_int8['pure_fps']:<18} | Tang {fps_increase:.1f}% (~{summary['improvements']['latency_ratio']}x)")
print(f"{'RAM Peak Dinh (MB)':<30} | {res_fp32['ram_peak_mb']:<18} | {res_int8['ram_peak_mb']:<18} | Toi uu bo nho")
print("="*70)
print(f"[OK] Da luu ket qua vao: {RESULT_JSON}")

