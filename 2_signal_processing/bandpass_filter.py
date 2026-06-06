import numpy as np
from scipy.signal import butter, sosfiltfilt

def bandpass_filter(signal: np.ndarray, fs: int = 250,
                    lowcut: float = 0.5, highcut: float = 40.0,
                    order: int = 4) -> np.ndarray:
    """
    Apply a zero-phase Butterworth bandpass filter.

    Args:
        signal:  1D raw ECG array
        fs:      Sampling frequency (Hz)
        lowcut:  Lower cutoff frequency (Hz)
        highcut: Upper cutoff frequency (Hz)
        order:   Filter order

    Returns:
        Filtered ECG signal (same length as input)
    """
    nyquist = 0.5 * fs
    low = lowcut / nyquist
    high = highcut / nyquist
    sos = butter(order, [low, high], btype='band', output='sos')
    return sosfiltfilt(sos, signal)
