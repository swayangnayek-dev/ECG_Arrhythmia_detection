class ActivityClassifier:
    def __init__(self):
        # We could keep history of HR/HRV here to smooth out the classification
        pass

    def classify(self, hr: int, hrv_sdnn: float) -> str:
        """
        Classifies activity based on HR and HRV rules.
        """
        if hr == 0:
            return "Unknown"
            
        if hr < 55 and hrv_sdnn > 80:
            return "Sleeping"
        elif 55 <= hr <= 85:
            return "Resting"
        elif 85 < hr <= 120:
            return "Walking"
        elif hr > 120 and hrv_sdnn < 40:
            return "Exercising"
        elif hr > 120:
            # High HR but not low HRV? Might be anxiety, anomalous, or exercising
            return "Exercising"
            
        return "Resting"
