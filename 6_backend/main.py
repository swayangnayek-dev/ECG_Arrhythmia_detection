import asyncio
import json
import time
from datetime import datetime
from fastapi import FastAPI, WebSocket, WebSocketDisconnect  # type: ignore
from fastapi.middleware.cors import CORSMiddleware  # type: ignore
from typing import List

from config import WINDOW_SIZE_SAMPLES, WINDOW_STRIDE_SAMPLES
from ecg_processor import ECGProcessor
from inference import InferenceEngine
from activity_classifier import ActivityClassifier
from alert_engine import AlertEngine
from history_store import history_store

app = FastAPI(title="ECG Arrhythmia Dashboard Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global State
class DashboardConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except:
                pass

manager = DashboardConnectionManager()
ecg_processor = ECGProcessor()
inference_engine = InferenceEngine()
activity_classifier = ActivityClassifier()
alert_engine = AlertEngine()

# Buffer for 500 samples (2 seconds @ 250Hz)
analysis_buffer = []

@app.websocket("/ws/dashboard")
async def websocket_dashboard(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.websocket("/ws/ecg-ingest")
async def websocket_ecg_ingest(websocket: WebSocket):
    await websocket.accept()
    global analysis_buffer
    
    try:
        while True:
            data = await websocket.receive_text()
            payload = json.loads(data)
            
            # Check for lead-off
            if payload.get("lo", False):
                await manager.broadcast(json.dumps({
                    "type": "DANGER_ALERT",
                    "ts": time.time() * 1000,
                    "condition": "LEAD_OFF",
                    "hr": 0,
                    "message": "Electrodes disconnected!"
                }))
                continue

            samples = payload.get("v", [])
            if not samples:
                continue
                
            # Filter the raw chunk for real-time visualization
            filtered_samples = ecg_processor.process_samples(samples)
            
            # Broadcast raw/filtered to dashboard for plotting
            await manager.broadcast(json.dumps({
                "type": "ECG_SAMPLES",
                "ts": payload["ts"],
                "samples": filtered_samples
            }))
            
            # Accumulate into analysis buffer
            analysis_buffer.extend(samples)
            
            # If we have enough for a 2-second window
            if len(analysis_buffer) >= WINDOW_SIZE_SAMPLES:
                window = analysis_buffer[:WINDOW_SIZE_SAMPLES]
                # Shift buffer by stride (e.g., 500 - 125 = 375 kept) for overlap
                analysis_buffer = analysis_buffer[WINDOW_STRIDE_SAMPLES:]
                
                # 1. Process Signal
                results = ecg_processor.analyze_window(window)
                
                # 2. ML Inference
                classification, confidence, is_ml_alert = inference_engine.invoke(results["normalized_segment"])
                
                # 3. Activity
                activity = activity_classifier.classify(results["hr"], results["hrv_sdnn"])
                
                # 4. Alerts
                alert_triggered, alert_type, alert_msg = alert_engine.evaluate(
                    results["hr"], classification, is_ml_alert
                )
                
                if alert_triggered:
                    await manager.broadcast(json.dumps({
                        "type": "DANGER_ALERT",
                        "ts": time.time() * 1000,
                        "condition": alert_type,
                        "hr": results["hr"],
                        "message": alert_msg
                    }))
                
                # 5. Broadcast Analysis
                analysis_msg = {
                    "type": "ANALYSIS",
                    "ts": time.time() * 1000,
                    "hr": results["hr"],
                    "rr_avg_ms": results["rr_avg_ms"],
                    "hrv_sdnn": results["hrv_sdnn"],
                    "classification": classification,
                    "confidence": confidence,
                    "activity": activity
                }
                await manager.broadcast(json.dumps(analysis_msg))
                
                # 6. Save to History
                record = {
                    "ts": datetime.now().isoformat(),
                    "hr": results["hr"],
                    "rr_avg_ms": results["rr_avg_ms"],
                    "hrv_sdnn": results["hrv_sdnn"],
                    "classification": classification,
                    "confidence": confidence,
                    "activity": activity,
                    "alert": alert_type if alert_triggered else None,
                    "r_peak_count": len(results["r_peaks"])
                }
                asyncio.create_task(history_store.add_record(record))
                
    except WebSocketDisconnect:
        pass

@app.get("/api/history")
async def get_history(hours: int = 24):
    records = await history_store.get_records(hours)
    return {"records": records}

@app.get("/api/analytics/peaks")
async def get_peaks():
    records = await history_store.get_records(24)
    if not records:
        return {}
        
    peak_hr = max(records, key=lambda x: x["hr"])
    lowest_hr = min([r for r in records if r["hr"] > 0], key=lambda x: x["hr"], default=records[0])
    
    return {
        "peak_hr": {
            "time": peak_hr["ts"],
            "bpm": peak_hr["hr"],
            "activity": peak_hr["activity"]
        },
        "lowest_hr": {
            "time": lowest_hr["ts"],
            "bpm": lowest_hr["hr"],
            "activity": lowest_hr["activity"]
        }
    }

# Background task to prune history
@app.on_event("startup")
async def startup_event():
    async def prune_loop():
        while True:
            await history_store.prune_old_records()
            await asyncio.sleep(300) # 5 mins
    asyncio.create_task(prune_loop())

if __name__ == "__main__":
    import uvicorn  # type: ignore
    uvicorn.run(app, host="0.0.0.0", port=8000)
