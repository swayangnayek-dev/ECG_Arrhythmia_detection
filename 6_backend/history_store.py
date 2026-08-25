import json
import os
import time
from datetime import datetime, timedelta
import asyncio
from config import HISTORY_FILE

class HistoryStore:
    def __init__(self):
        self.file_path = HISTORY_FILE
        self.lock = asyncio.Lock()
        
        if not os.path.exists(self.file_path):
            self._init_file()

    def _init_file(self):
        with open(self.file_path, "w") as f:
            json.dump({"device_id": "esp32-c3-001", "records": []}, f)

    async def add_record(self, record):
        """Append a new record."""
        async with self.lock:
            try:
                with open(self.file_path, "r") as f:
                    data = json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                data = {"device_id": "esp32-c3-001", "records": []}
                
            data["records"].append(record)
            
            with open(self.file_path, "w") as f:
                json.dump(data, f)

    async def get_records(self, hours: int = 24):
        """Get records from the last N hours."""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        async with self.lock:
            try:
                with open(self.file_path, "r") as f:
                    data = json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                return []
                
        # Filter records
        valid_records = []
        for r in data.get("records", []):
            try:
                # ISO format parse
                r_time = datetime.fromisoformat(r["ts"])
                if r_time >= cutoff_time:
                    # Sanitize activity to be only 'Resting' or 'Walking'
                    if r.get("activity") not in ["Resting", "Walking"]:
                        r["activity"] = "Walking" if r.get("hr", 0) > 85 else "Resting"
                    valid_records.append(r)
            except Exception:
                pass
                
        return valid_records

    async def prune_old_records(self):
        """Remove records older than 24 hours."""
        cutoff_time = datetime.now() - timedelta(hours=24)
        async with self.lock:
            try:
                with open(self.file_path, "r") as f:
                    data = json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                return
                
            original_len = len(data["records"])
            
            new_records = []
            for r in data["records"]:
                try:
                    if datetime.fromisoformat(r["ts"]) >= cutoff_time:
                        new_records.append(r)
                except Exception:
                    pass
                    
            if len(new_records) != original_len:
                data["records"] = new_records
                with open(self.file_path, "w") as f:
                    json.dump(data, f)
                    
history_store = HistoryStore()
