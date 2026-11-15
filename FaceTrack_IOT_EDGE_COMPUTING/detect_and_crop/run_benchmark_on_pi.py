# -*- coding: utf-8 -*-
"""
BENCHMARK RUNNER TREN RASPBERRY PI
Chay do trac nghiem truc tiep tren CPU ARM Cortex-A72:
- FaceNet512 FP32 vs FaceNet512 INT8
"""
import os, sys, time, glob, json, cv2
import numpy as np

Interpreter = None
# 1. Thu ai_edge_litert (Goi LiteRT nhe moi nhat tren Linux/Pi)
try:
    from ai_edge_litert.interpreter import Interpreter
except ImportError:
    pass

# 2. Thu tflite_runtime
if Interpreter is None:
    try:
        from tflite_runtime.interpreter import Interpreter
    except ImportError:
        pass

# 3. Thu tensorflow.lite
if Interpreter is None:
    try:
        import tensorflow.lite as tflite
        Interpreter = tflite.Interpreter
    except Exception as e:
        print(f"[!] Loi import tensorflow: {e}")

if Interpreter is None:
    print("[ERROR] Khong tim thay thu vien TFLite nao tren Pi (ai_edge_litert, tflite_runtime, hoac tensorflow.lite)")
    sys.exit(1)

print("="*65)
print("   BENCHMARK TRUC TIEP TREN RASPBERRY PI 4 (ARM CORTEX-A72)")
print("="*65)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_FP32 = os.path.join(BASE_DIR, "facenet512.tflite")
MODEL_INT8 = os.path.join(BASE_DIR, "facenet512_int8.tflite")

def test_model(path, name, num_threads=4):
    if not os.path.exists(path):
        print(f"[!] Khong tim thay: {path}")
        return None
    sz = os.path.getsize(path)/(1024*1024)
    print(f"\n---> DANG DO: {name} ({sz:.2f} MB) - Running with {num_threads} CPU Threads...")
    
    try:
        interp = Interpreter(model_path=path, num_threads=num_threads)
    except Exception:
        interp = Interpreter(model_path=path)
        
    interp.allocate_tensors()
    inp = interp.get_input_details()[0]['index']
    out = interp.get_output_details()[0]['index']
    
    dummy = np.random.randn(1, 160, 160, 3).astype(np.float32)
    # Warm-up
    for _ in range(15):
        interp.set_tensor(inp, dummy)
        interp.invoke()
        _ = interp.get_tensor(out)
        
    latencies = []
    for _ in range(50):
        t0 = time.perf_counter_ns()
        interp.set_tensor(inp, dummy)
        interp.invoke()
        _ = interp.get_tensor(out)
        t1 = time.perf_counter_ns()
        latencies.append((t1 - t0)/1_000_000.0)
        
    mean_lat = np.mean(latencies)
    fps = 1000.0 / mean_lat
    print(f"     [+] Latency: {mean_lat:.2f} ms")
    print(f"     [+] FPS    : {fps:.2f} FPS")
    return {"name": name, "size_mb": round(sz, 2), "latency_ms": round(mean_lat, 2), "fps": round(fps, 2)}

r_fp32 = test_model(MODEL_FP32, "FaceNet512 FP32")
r_int8 = test_model(MODEL_INT8, "FaceNet512 INT8")

if r_fp32 and r_int8:
    speedup = (r_fp32["latency_ms"] - r_int8["latency_ms"]) / r_fp32["latency_ms"] * 100
    print("\n" + "="*65)
    print(f"KET QUA RASPBERRY PI: INT8 nhanh hon FP32: {speedup:.1f}%")
    print(f"FP32: {r_fp32['latency_ms']} ms ({r_fp32['fps']} FPS) -> INT8: {r_int8['latency_ms']} ms ({r_int8['fps']} FPS)")
    print("="*65)

