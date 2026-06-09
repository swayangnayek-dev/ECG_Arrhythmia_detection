import time

class AlertEngine:
    def __init__(self):
        self.last_alert_time = 0
        self.alert_cooldown = 30 # seconds
        self.pvc_count_window = []

    def evaluate(self, hr: int, classification: str, is_ml_alert: bool) -> tuple[bool, str, str]:
        """
        Evaluates conditions and returns (triggered, alert_type, message).
        """
        current_time = time.time()
        
        # Track PVCs in the last 10 seconds
        if classification == "PVC":
            self.pvc_count_window.append(current_time)
            
        # Clean old PVCs
        self.pvc_count_window = [t for t in self.pvc_count_window if current_time - t <= 10]
        
        # Check cooldown
        if current_time - self.last_alert_time < self.alert_cooldown:
            return False, "", ""
            
        triggered = False
        alert_type = ""
        message = ""

        # 1. Bradycardia
        if 0 < hr < 40:
            triggered = True
            alert_type = "BRADYCARDIA"
            message = f"Dangerously low heart rate: {hr} BPM"
            
        # 2. Tachycardia
        elif hr > 180:
            triggered = True
            alert_type = "TACHYCARDIA"
            message = f"Dangerously high heart rate: {hr} BPM"
            
        # 3. ML Arrhythmia Alert (e.g. sustained AFib)
        elif is_ml_alert and classification == "AFib":
            triggered = True
            alert_type = "AFIB_DETECTED"
            message = "Sustained Atrial Fibrillation detected"
            
        # 4. PVC Burst
        elif len(self.pvc_count_window) >= 3:
            triggered = True
            alert_type = "PVC_BURST"
            message = "Multiple Premature Ventricular Contractions detected"
            
        if triggered:
            self.last_alert_time = current_time
            
        return triggered, alert_type, message
