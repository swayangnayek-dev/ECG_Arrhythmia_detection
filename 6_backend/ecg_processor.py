import sys
import os
import numpy as np

# Add parent paths directly to allow importing from directories starting with numbers
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '2_signal_processing'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '1_data_pipeline'))

from bandpass_filter import bandpass_filter  # type: ignore
from pan_tompkins import pan_tompkins_detector  # type: ignore
from preprocess import preprocess_segment  # type: ignore
from config import SAMPLE_RATE

class ECGProcessor:
    def __init__(self):
        self.buffer = []
        self.fs = SAMPLE_RATE
        self.running_mean = 2048.0  # Initial guess for 12-bit ADC

    def process_samples(self, new_samples):
        """Center the real-time signal using a running mean (DC blocker) and scale it down."""
        if not new_samples:
            return []
            
        centered = []
        alpha = 0.05  # Smoothing factor for running mean
        
        for val in new_samples:
            self.running_mean = (1 - alpha) * self.running_mean + alpha * val
            # Scale down the raw ADC values (0-4095) so they fit nicely on the canvas
            centered.append((val - self.running_mean) / 20.0) 
            
        return centered

    def analyze_window(self, window_samples):
        """
        Takes a full 2-second window (500 samples), detects R-peaks,
        calculates HR/HRV, and normalizes for ML.
        """
        arr = np.array(window_samples)
        
        # Detect R-peaks using Pan-Tompkins
        r_peaks = pan_tompkins_detector(arr, fs=self.fs)
        
        # Calculate HR and HRV
        hr = 0
        rr_avg_ms = 0
        hrv_sdnn = 0
        
        if len(r_peaks) >= 2:
            rr_intervals_samples = np.diff(r_peaks)
            rr_intervals_ms = (rr_intervals_samples / self.fs) * 1000
            rr_avg_ms = np.mean(rr_intervals_ms)
            hrv_sdnn = np.std(rr_intervals_ms)
            hr = int(60000 / rr_avg_ms) if rr_avg_ms > 0 else 0
            
        # Normalize for model inference
        # The preprocess_segment function applies bandpass + Z-score
        normalized_segment = preprocess_segment(arr, fs=self.fs)
        
        return {
            "r_peaks": r_peaks.tolist(),
            "hr": hr,
            "rr_avg_ms": float(rr_avg_ms),
            "hrv_sdnn": float(hrv_sdnn),
            "normalized_segment": normalized_segment
        }
