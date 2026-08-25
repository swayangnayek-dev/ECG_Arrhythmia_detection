import os
import numpy as np
import random
from config import MODEL_PATH, CLASS_NAMES, CLASS_NORMAL, CLASS_PVC, CLASS_AFIB, CONFIDENCE_THRESHOLD, CONSECUTIVE_WINDOWS

# Try importing tflite_runtime, fallback to mock if not installed or model missing
try:
    import tflite_runtime.interpreter as tflite  # type: ignore
    HAS_TFLITE = True
except ImportError:
    HAS_TFLITE = False
    print("Warning: tflite_runtime not found. Using Mock Inference.")

class InferenceEngine:
    def __init__(self):
        self.mock_mode = False
        self.interpreter = None
        self.input_details = None
        self.output_details = None
        
        self._load_model()

    def _load_model(self):
        if not HAS_TFLITE or not os.path.exists(MODEL_PATH):
            print(f"Warning: Model not found at {MODEL_PATH} or tflite missing. Falling back to Mock Inference.")
            self.mock_mode = True
            return
            
        try:
            self.interpreter = tflite.Interpreter(model_path=MODEL_PATH)
            self.interpreter.allocate_tensors()
            self.input_details = self.interpreter.get_input_details()
            self.output_details = self.interpreter.get_output_details()
            print("Successfully loaded TFLite model.")
        except Exception as e:
            print(f"Failed to load model: {e}. Using Mock Inference.")
            self.mock_mode = True

    def invoke(self, normalized_segment):
        """Returns (predicted_class_name, confidence)."""
        if self.mock_mode:
            return self._mock_invoke()
            
        try:
            # Prepare input
            input_data = np.array(normalized_segment, dtype=np.float32)
            # Reshape to (1, 500, 1) assuming Conv1D
            input_data = np.expand_dims(np.expand_dims(input_data, axis=0), axis=2)
            
            # Note: If it's a quantized int8 model, we might need to quantize the input here.
            # Assuming float32 for runtime flexibility, but checking dtype:
            if self.input_details[0]['dtype'] == np.int8:
                scale, zero_point = self.input_details[0]['quantization']
                input_data = (input_data / scale + zero_point).astype(np.int8)
                
            self.interpreter.set_tensor(self.input_details[0]['index'], input_data)
            self.interpreter.invoke()
            output_data = self.interpreter.get_tensor(self.output_details[0]['index'])
            
            # Dequantize output if int8
            if self.output_details[0]['dtype'] == np.int8:
                scale, zero_point = self.output_details[0]['quantization']
                output_data = (output_data.astype(np.float32) - zero_point) * scale
                
            probs = output_data[0]
            pred_class = int(np.argmax(probs))
            confidence = float(probs[pred_class])
            
        except Exception as e:
            print(f"Inference error: {e}")
            return "Error", 0.0
            
        return self._track_confidence(pred_class, confidence)

    def _mock_invoke(self):
        """Simulates Normal rhythm with occasional PVCs for testing."""
        # 95% Normal, 5% PVC
        if random.random() > 0.95:
            pred_class = CLASS_PVC
            confidence = random.uniform(0.85, 0.99)
        else:
            pred_class = CLASS_NORMAL
            confidence = random.uniform(0.90, 0.99)
            
        return self._track_confidence(pred_class, confidence)

    def _track_confidence(self, pred_class, confidence):
        class_name = CLASS_NAMES.get(pred_class, "Unknown")
        return class_name, confidence
