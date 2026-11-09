import tensorflow as tf
from deepface import DeepFace

print("Building Facenet512 model...")
model = DeepFace.build_model("Facenet512")

print("Converting to TFLite...")
converter = tf.lite.TFLiteConverter.from_keras_model(model.model)
tflite_model = converter.convert()

with open("facenet512.tflite", "wb") as f:
    f.write(tflite_model)
print("Saved facenet512.tflite")
