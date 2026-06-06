import numpy as np
from sklearn.preprocessing import StandardScaler

# We'll need the bandpass filter here
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '2_signal_processing'))
from bandpass_filter import bandpass_filter

def preprocess_segment(signal: np.ndarray, fs: int = 250) -> np.ndarray:
    """
    Preprocess an ECG segment (e.g. 500 samples / 2 seconds).
    
    Steps:
    1. Apply bandpass filter (0.5 - 40 Hz)
    2. Z-score normalization
    """
    # 1. Bandpass filter
    filtered = bandpass_filter(signal, fs=fs, lowcut=0.5, highcut=40.0)
    
    # 2. Z-score normalization per segment
    # Reshape for StandardScaler which expects 2D array
    scaler = StandardScaler()
    normalized = scaler.fit_transform(filtered.reshape(-1, 1)).flatten()
    
    return normalized

def segment_ecg(signal: np.ndarray, labels: list, fs: int = 250, window_sec: float = 2.0):
    """
    Segment continuous ECG signal into overlapping or non-overlapping windows.
    For demonstration, simply split into non-overlapping windows.
    """
    window_samples = int(window_sec * fs)
    segments = []
    segment_labels = []
    
    # This is a naive segmentation. Real implementation would involve 
    # synchronizing with beat annotations or using a sliding window.
    for i in range(0, len(signal) - window_samples, window_samples):
        segment = signal[i:i + window_samples]
        segments.append(preprocess_segment(segment, fs))
        
        # Dummy label selection (e.g., majority vote or rhythm marker in window)
        # Assuming `labels` array matches `signal` array length
        if labels is not None and len(labels) == len(signal):
            window_labels = labels[i:i + window_samples]
            # Simple approach: most common label
            vals, counts = np.unique(window_labels, return_counts=True)
            segment_labels.append(vals[np.argmax(counts)])
        else:
            segment_labels.append(0)
            
    return np.array(segments), np.array(segment_labels)
