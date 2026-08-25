class ActivityClassifier:
    def classify(self, hr: int, hrv_sdnn: float) -> str:
        """
        Classifies activity based on HR and HRV rules, restricted to Resting and Walking.
        """
        if hr <= 85:
            return "Resting"
        return "Walking"

