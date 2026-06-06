import numpy as np
from scipy.signal import butter, lfilter

def pan_tompkins_detector(signal: np.ndarray, fs: int = 250) -> np.ndarray:
    """
    Pan-Tompkins QRS detection algorithm.
    
    Steps:
    1. Bandpass filter (5-15 Hz)
    2. Derivative
    3. Squaring
    4. Moving Window Integration
    5. Thresholding (Simplified for this example)
    
    Returns:
        Indices of detected R-peaks.
    """
    # 1. Bandpass filter (5-15 Hz)
    nyquist = 0.5 * fs
    low = 5.0 / nyquist
    high = 15.0 / nyquist
    b, a = butter(1, [low, high], btype='band')
    filtered = lfilter(b, a, signal)
    
    # 2. Derivative
    # H(z) = (1/8T)(-z^-2 - 2z^-1 + 2z^1 + z^2)
    # Using a simpler numpy diff or a custom kernel
    derivative = np.zeros_like(filtered)
    for i in range(2, len(filtered) - 2):
        derivative[i] = (1/8.0) * (-filtered[i-2] - 2*filtered[i-1] + 2*filtered[i+1] + filtered[i+2])
        
    # 3. Squaring
    squared = derivative ** 2
    
    # 4. Moving Window Integration
    # Window width ~150ms
    window_samples = int(0.150 * fs)
    integrated = np.zeros_like(squared)
    for i in range(window_samples, len(squared)):
        integrated[i] = np.sum(squared[i - window_samples:i]) / window_samples
        
    # 5. Thresholding & peak detection (Basic thresholding)
    # A complete Pan-Tompkins uses adaptive thresholding and search-back.
    # This is a simplified version finding peaks above a mean threshold.
    threshold = np.mean(integrated) * 1.5
    peaks = []
    
    # Refractory period: 200 ms
    refractory_samples = int(0.200 * fs)
    last_peak = -refractory_samples
    
    for i in range(1, len(integrated) - 1):
        if integrated[i] > threshold and integrated[i] > integrated[i-1] and integrated[i] > integrated[i+1]:
            if i - last_peak >= refractory_samples:
                peaks.append(i)
                last_peak = i
                
    return np.array(peaks)
