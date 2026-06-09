import os

# Server
HOST = "0.0.0.0"
PORT = 8000

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
MODEL_PATH = os.path.join(DATA_DIR, "ecg_model.tflite")
HISTORY_FILE = os.path.join(DATA_DIR, "ecg_history.json")

# Ensure data dir exists
os.makedirs(DATA_DIR, exist_ok=True)

# Sampling
SAMPLE_RATE = 250
WINDOW_SIZE_SAMPLES = 500  # 2 seconds
WINDOW_STRIDE_SAMPLES = 125 # 0.5 seconds

# Inference
CONFIDENCE_THRESHOLD = 0.90
CONSECUTIVE_WINDOWS = 3

# Classes (Match label_mapping.py)
CLASS_NORMAL = 0
CLASS_AFIB = 1
CLASS_PVC = 2

CLASS_NAMES = {
    CLASS_NORMAL: "Normal",
    CLASS_AFIB: "AFib",
    CLASS_PVC: "PVC"
}
