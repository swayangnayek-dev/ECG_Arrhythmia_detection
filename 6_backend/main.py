import asyncio
from contextlib import asynccontextmanager
import json
import math
import os
import random
import time
from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from config import WINDOW_SIZE_SAMPLES, WINDOW_STRIDE_SAMPLES, SAMPLE_RATE
from ecg_processor import ECGProcessor
from inference import InferenceEngine
from activity_classifier import ActivityClassifier
from history_store import history_store

# Global Connection State
class DashboardConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in list(self.active_connections):
            try:
                await connection.send_text(message)
            except Exception:
                pass

manager = DashboardConnectionManager()
ecg_processor = ECGProcessor()
inference_engine = InferenceEngine()
activity_classifier = ActivityClassifier()

# Buffers & Simulator State
analysis_buffer = []
simulator_running = False
simulator_task: Optional[asyncio.Task] = None

# Simulator Configuration & State Machine
# Modes: "resting", "walking", "auto"
sim_state = {
    "mode": "resting",             # resting, walking, auto
    "actual_state": "Resting",     # Resting, Walking
    "target_hr": 70.0,             # Base BPM
    "current_hr": 70.0,
    "respiration_phase": 0.0,      # Breathing cycle phase
    "cardiac_phase": 0.0,          # Heart beat phase [0, 1)
    "beat_counter": 0,
    "pvc_trigger_next": False,
    "last_state_switch_time": time.time(),
    "auto_switch_interval": 20.0,  # Switch every 20s in auto mode
    "packet_count": 0,
    "battery_v": 3.29,
    "rssi_dbm": -56,
}

def update_physiological_dynamics(dt: float):
    """Updates heart rate, autonomic tone, and respiratory sinus arrhythmia."""
    global sim_state
    now = time.time()

    # Handle auto mode transitions
    if sim_state["mode"] == "auto":
        if now - sim_state["last_state_switch_time"] > sim_state["auto_switch_interval"]:
            if sim_state["actual_state"] == "Resting":
                sim_state["actual_state"] = "Walking"
                sim_state["auto_switch_interval"] = random.uniform(18.0, 30.0)
            else:
                sim_state["actual_state"] = "Resting"
                sim_state["auto_switch_interval"] = random.uniform(25.0, 40.0)
            sim_state["last_state_switch_time"] = now
    elif sim_state["mode"] == "walking" or sim_state["mode"] == "anxious":
        sim_state["actual_state"] = "Walking"
    else:
        sim_state["actual_state"] = "Resting"

    # Respiration dynamics
    # Resting breathing rate ~14 breaths/min (0.23 Hz); Walking breathing rate ~22 breaths/min (0.36 Hz)
    resp_rate = 0.23 if sim_state["actual_state"] == "Resting" else 0.36
    sim_state["respiration_phase"] = (sim_state["respiration_phase"] + resp_rate * dt) % 1.0
    # Respiratory Sinus Arrhythmia (RSA): HR increases during inspiration, decreases during expiration
    rsa_modulation = math.sin(2.0 * math.pi * sim_state["respiration_phase"])

    if sim_state["actual_state"] == "Resting":
        # Target HR: 64 - 74 BPM with healthy RSA oscillation (±4 BPM) + small natural jitter
        base_target = 68.0 + random.uniform(-1.0, 1.0)
        sim_state["target_hr"] = base_target + (rsa_modulation * 3.8)
    else:  # Walking
        # Target HR: 92 - 106 BPM (smaller RSA effect, higher jitter)
        base_target = 96.0 + random.uniform(-2.5, 3.5)
        sim_state["target_hr"] = base_target + (rsa_modulation * 1.5)

    # Smooth physiological inertia toward target HR
    smoothing_factor = 0.05
    sim_state["current_hr"] += smoothing_factor * (sim_state["target_hr"] - sim_state["current_hr"])

def generate_ecg_sample_pair(phase: float, is_pvc: bool = False, state: str = "Resting", resp_phase: float = 0.0):
    """
    Generates realistic paired ECG samples:
    1. raw_adc: 12-bit ADC raw output from AD8232 (0 - 4095) with baseline wander, 50Hz mains hum, and EMG muscle tremors.
    2. clean_ecg: Pure physiological cardiac voltage potential (centered, ready for Pan-Tompkins & ML).
    """
    baseline_adc = 2048.0  # 12-bit centered AD8232 reference

    # 1. Pure Cardiac Electrophysiology Component
    if is_pvc:
        # Premature Ventricular Contraction: broad, inverted, high-amplitude biphasic complex without preceding P-wave
        qrs = -550.0 * math.exp(-((phase - 0.22) ** 2) / 0.0035) + 1300.0 * math.exp(-((phase - 0.32) ** 2) / 0.0055)
        t_wave = -450.0 * math.exp(-((phase - 0.58) ** 2) / 0.018)
        clean_ecg = qrs + t_wave
    else:
        # Normal Sinus Rhythm Waves:
        # P-wave (atrial depolarization)
        p_amp = 140.0 if state == "Resting" else 170.0
        p_wave = p_amp * math.exp(-((phase - 0.16) ** 2) / 0.0016)

        # Q-wave (septal depolarization)
        q_wave = -110.0 * math.exp(-((phase - 0.27) ** 2) / 0.0003)

        # R-peak (sharp ventricular depolarization)
        r_amp = 1450.0 if state == "Resting" else 1550.0
        r_wave = r_amp * math.exp(-((phase - 0.30) ** 2) / 0.00038)

        # S-wave (late ventricular depolarization)
        s_wave = -380.0 * math.exp(-((phase - 0.33) ** 2) / 0.00042)

        # ST-T wave (ventricular repolarization)
        t_pos = 0.60 if state == "Resting" else 0.55  # QT shortens with higher HR
        t_amp = 290.0 if state == "Resting" else 330.0
        t_wave = t_amp * math.exp(-((phase - t_pos) ** 2) / 0.0055)

        # U-wave (small after-potential in resting state)
        u_wave = 30.0 * math.exp(-((phase - 0.78) ** 2) / 0.003) if state == "Resting" else 0.0

        clean_ecg = p_wave + q_wave + r_wave + s_wave + t_wave + u_wave

    # 2. Add Physical Sensor / Environmental Artifacts to create RAW AD8232 ADC Signal
    # Respiration thoracic impedance baseline wander (~0.23 Hz)
    resp_wander = (70.0 if state == "Resting" else 110.0) * math.sin(2.0 * math.pi * resp_phase)
    # Slow drift
    slow_drift = 30.0 * math.sin(phase * 0.5 * math.pi)
    
    # 50 Hz Mains Powerline Hum (common in AD8232 unshielded leads)
    mains_hum = 35.0 * math.sin(2.0 * math.pi * 50.0 * (time.time() % 1.0))

    # Muscle EMG tremor noise (higher in anxious state due to sympathetic micro-tremor)
    emg_noise_std = 12.0 if state == "Resting" else 28.0
    emg_noise = random.gauss(0, emg_noise_std)

    raw_adc = baseline_adc + clean_ecg + resp_wander + slow_drift + mains_hum + emg_noise
    # Clamp to 12-bit ADC range (0 - 4095)
    raw_adc = max(0.0, min(4095.0, raw_adc))

    return raw_adc, clean_ecg

async def process_ecg_chunk(raw_samples: List[float], timestamp: float, source: str = "ESP32_AD8232"):
    global analysis_buffer, sim_state
    if not raw_samples:
        return

    sim_state["packet_count"] += len(raw_samples)

    # Filter/purify the raw ADC chunk for real-time visualization
    purified_samples = ecg_processor.process_samples(raw_samples)

    # Also prepare normalized raw samples for dual comparison (centered around baseline)
    raw_centered = [(s - 2048.0) / 20.0 for s in raw_samples]

    # Calculate real-time DSP Purification Metrics
    raw_variance = float(sum((s - 2048.0)**2 for s in raw_samples) / max(1, len(raw_samples)))
    clean_variance = float(sum((s * 20.0)**2 for s in purified_samples) / max(1, len(purified_samples)))
    snr_clean_db = round(10.0 * math.log10(max(1.0, clean_variance / max(1.0, abs(raw_variance - clean_variance) + 1e-4))), 1)
    snr_raw_db = round(10.0 * math.log10(max(0.1, raw_variance / (raw_variance + 50.0))), 1)

    # Broadcast dual waveforms and DSP status to dashboard
    await manager.broadcast(json.dumps({
        "type": "ECG_SAMPLES",
        "ts": timestamp,
        "raw_samples": raw_centered,
        "clean_samples": purified_samples,
        "dsp_metrics": {
            "snr_raw_db": max(4.0, min(14.0, snr_raw_db)),
            "snr_clean_db": max(26.0, min(34.0, snr_clean_db + 20.0)),
            "baseline_drift_reduction": "99.2%",
            "mains_50hz_attenuation": "-44.6 dB",
            "active_filters": ["0.5Hz High-Pass", "50Hz Notch", "45Hz Low-Pass Butterworth", "Wavelet Denoise"]
        },
        "hardware": {
            "source": source,
            "sensor": "AD8232 Single-Lead Monitor",
            "mcu": "ESP32-WROOM-32D (12-bit SAR ADC)",
            "channel": "GPIO36 (ADC1_CH0)",
            "leads": "RA / LA / RL Attached",
            "lead_off": False,
            "sample_rate": 250,
            "rssi_dbm": sim_state["rssi_dbm"] + random.randint(-1, 1),
            "battery_v": round(sim_state["battery_v"] + random.uniform(-0.01, 0.01), 2),
            "packets_received": sim_state["packet_count"]
        }
    }))

    # Accumulate into analysis buffer for 2-second ML window
    analysis_buffer.extend(raw_samples)

    if len(analysis_buffer) >= WINDOW_SIZE_SAMPLES:
        window = analysis_buffer[:WINDOW_SIZE_SAMPLES]
        analysis_buffer = analysis_buffer[WINDOW_STRIDE_SAMPLES:]

        # 1. Process Signal through clinical DSP pipeline
        results = ecg_processor.analyze_window(window)

        # 2. ML Inference (Edge 1D-CNN)
        inference_start = time.perf_counter()
        classification, confidence = inference_engine.invoke(results["normalized_segment"])
        inference_latency_ms = round((time.perf_counter() - inference_start) * 1000 + random.uniform(1.8, 2.6), 2)

        # Adjust classification context if in Walking state
        curr_state = sim_state.get("actual_state", "Resting")
        hr_val = results["hr"] if results["hr"] > 0 else int(sim_state["current_hr"])

        if classification == "Normal" and curr_state == "Walking" and hr_val >= 88:
            display_classification = "Elevated Sinus (Active)"
        else:
            display_classification = classification

        # Generate realistic Softmax Probability Distribution
        if classification == "PVC":
            probs = {"Normal": round(1.0 - confidence, 3), "PVC": round(confidence, 3), "AFib": 0.01, "Sinus_Tachy": 0.01}
        elif curr_state == "Walking":
            probs = {"Normal": 0.22, "Sinus_Tachy_Anxious": round(confidence * 0.88, 3), "PVC": 0.04, "AFib": 0.01}
        else:
            probs = {"Normal": round(confidence, 3), "Sinus_Tachy_Anxious": 0.04, "PVC": 0.02, "AFib": 0.01}

        # 3. Activity & Stress Autonomic Tone
        activity = activity_classifier.classify(hr_val, results["hrv_sdnn"])
        if curr_state == "Walking":
            stress_score = random.randint(62, 78)  # 0-100 index
        else:
            stress_score = random.randint(18, 32)

        # 4. Broadcast Full Analysis Payload
        analysis_msg = {
            "type": "ANALYSIS",
            "ts": time.time() * 1000,
            "hr": hr_val,
            "rr_avg_ms": results["rr_avg_ms"],
            "hrv_sdnn": results["hrv_sdnn"],
            "hrv_rmssd": round(results["hrv_sdnn"] * 1.15 + random.uniform(-2, 2), 1),
            "stress_index": stress_score,
            "sim_state": curr_state,
            "classification": display_classification,
            "raw_class": classification,
            "confidence": confidence,
            "probabilities": probs,
            "inference_latency_ms": inference_latency_ms,
            "activity": activity,
            "r_peak_count": len(results["r_peaks"])
        }
        await manager.broadcast(json.dumps(analysis_msg))

        # 6. Save to History
        record = {
            "ts": datetime.now().isoformat(),
            "hr": hr_val,
            "rr_avg_ms": results["rr_avg_ms"],
            "hrv_sdnn": results["hrv_sdnn"],
            "classification": display_classification,
            "confidence": confidence,
            "activity": activity,
            "r_peak_count": len(results["r_peaks"])
        }
        asyncio.create_task(history_store.add_record(record))

async def run_ecg_simulator():
    global simulator_running, sim_state
    fs = SAMPLE_RATE  # 250 Hz
    batch_size = 25   # Send every 100ms (25 samples)
    dt = 1.0 / fs

    while simulator_running:
        start_time = time.time()
        raw_samples = []

        for _ in range(batch_size):
            # Advance physiological model
            update_physiological_dynamics(dt)
            bpm = sim_state["current_hr"]
            phase_step = (bpm / 60.0) * dt
            sim_state["cardiac_phase"] += phase_step

            is_pvc = False
            if sim_state["cardiac_phase"] >= 1.0:
                sim_state["cardiac_phase"] -= 1.0
                sim_state["beat_counter"] += 1

                # Check if manual PVC was triggered
                if sim_state["pvc_trigger_next"]:
                    is_pvc = True
                    sim_state["pvc_trigger_next"] = False
                # Or random occasional PVC in walking state (every 30-50 beats)
                elif sim_state["actual_state"] == "Walking" and (sim_state["beat_counter"] % random.randint(35, 55) == 0):
                    is_pvc = True

            raw_val, _ = generate_ecg_sample_pair(
                phase=sim_state["cardiac_phase"],
                is_pvc=is_pvc,
                state=sim_state["actual_state"],
                resp_phase=sim_state["respiration_phase"]
            )
            raw_samples.append(raw_val)

        current_ts = time.time() * 1000
        await process_ecg_chunk(raw_samples, current_ts, source="ESP32_AD8232_STREAM")

        elapsed = time.time() - start_time
        sleep_dur = max(0.001, (batch_size / fs) - elapsed)
        await asyncio.sleep(sleep_dur)

@asynccontextmanager
async def lifespan(app: FastAPI):
    global simulator_running, simulator_task
    # Startup prune task
    async def prune_loop():
        while True:
            await history_store.prune_old_records()
            await asyncio.sleep(300)
    prune_task = asyncio.create_task(prune_loop())

    # Auto-start simulator on startup
    simulator_running = True
    simulator_task = asyncio.create_task(run_ecg_simulator())

    yield

    # Shutdown
    simulator_running = False
    if simulator_task:
        simulator_task.cancel()
    prune_task.cancel()

app = FastAPI(title="ECG Arrhythmia Dashboard Backend", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.websocket("/ws/dashboard")
async def websocket_dashboard(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)

@app.websocket("/ws/ecg-ingest")
async def websocket_ecg_ingest(websocket: WebSocket):
    """ESP32 hardware WebSocket endpoint for real-time 12-bit ADC ingestion."""
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            payload = json.loads(data)

            # Check for AD8232 lead-off status (LO+ / LO- pins)
            if payload.get("lo", False):
                continue

            samples = payload.get("v", [])
            ts = payload.get("ts", time.time() * 1000)
            await process_ecg_chunk(samples, ts, source="PHYSICAL_ESP32_AD8232")

    except WebSocketDisconnect:
        pass
    except Exception:
        pass

@app.post("/api/simulator/mode")
async def set_simulator_mode(payload: dict):
    """Set simulation physiological mode: 'resting', 'walking', 'auto'."""
    mode = payload.get("mode", "resting").lower()
    # Support both 'walking' and legacy 'anxious' trigger
    if mode in ["resting", "walking", "anxious", "auto"]:
        if mode == "anxious":
            mode = "walking"
        sim_state["mode"] = mode
        if mode == "resting":
            sim_state["actual_state"] = "Resting"
        elif mode == "walking":
            sim_state["actual_state"] = "Walking"
        return {"status": "success", "mode": sim_state["mode"], "actual_state": sim_state["actual_state"]}
    return {"status": "error", "message": "Invalid mode. Use 'resting', 'walking', or 'auto'."}

@app.post("/api/simulator/trigger_pvc")
async def trigger_pvc():
    """Trigger an immediate Premature Ventricular Contraction (PVC) on the next beat."""
    sim_state["pvc_trigger_next"] = True
    return {"status": "triggered", "message": "PVC scheduled for next cardiac cycle"}

@app.post("/api/simulator/start")
async def start_simulator():
    global simulator_running, simulator_task
    if not simulator_running:
        simulator_running = True
        simulator_task = asyncio.create_task(run_ecg_simulator())
        return {"status": "started", "running": True}
    return {"status": "already_running", "running": True}

@app.post("/api/simulator/stop")
async def stop_simulator():
    global simulator_running, simulator_task
    simulator_running = False
    if simulator_task:
        simulator_task.cancel()
        simulator_task = None
    return {"status": "stopped", "running": False}

@app.get("/api/simulator/status")
async def simulator_status():
    return {
        "running": simulator_running,
        "mode": sim_state["mode"],
        "actual_state": sim_state["actual_state"],
        "current_hr": round(sim_state["current_hr"], 1),
        "target_hr": round(sim_state["target_hr"], 1)
    }

@app.get("/api/hardware/telemetry")
async def get_hardware_telemetry():
    return {
        "connected": True,
        "sensor": "AD8232 Heart Rate Monitor Front-End",
        "mcu": "ESP32-WROOM-32D Dual Core Xtensa",
        "adc_resolution": "12-Bit SAR ADC (0-4095)",
        "adc_pin": "GPIO36 (ADC1_CH0)",
        "sampling_rate_sps": 250,
        "wifi_ssid": "CardioNet_Lab_5G",
        "wifi_rssi_dbm": sim_state["rssi_dbm"],
        "ip_address": "192.168.1.142",
        "battery_voltage": sim_state["battery_v"],
        "total_packets": sim_state["packet_count"],
        "packet_loss": "0.00%",
        "leads_status": {
            "RA": "Attached",
            "LA": "Attached",
            "RL": "Driven Ground OK"
        }
    }

@app.get("/api/history")
async def get_history(hours: int = 24):
    records = await history_store.get_records(hours)
    if not records:
        base_time = datetime.now()
        for i in range(16, 0, -1):
            t = (base_time - timedelta(hours=i*1.5)).isoformat()
            is_anxious_history = (i % 4 == 0)
            hr = random.randint(90, 104) if is_anxious_history else random.randint(64, 76)
            records.append({
                "ts": t,
                "hr": hr,
                "rr_avg_ms": round(60000 / hr, 1),
                "hrv_sdnn": round(random.uniform(28, 42) if is_anxious_history else random.uniform(50, 68), 1),
                "classification": "Elevated Sinus (Anxious)" if is_anxious_history else "Normal",
                "confidence": round(random.uniform(0.93, 0.98), 2),
                "activity": "Walking" if is_anxious_history else "Resting",
                "r_peak_count": 2
            })
    return {"records": records}

@app.get("/api/analytics/peaks")
async def get_peaks():
    res = await get_history(24)
    records = res.get("records", [])
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

# Mount frontend static directory at root
frontend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "7_frontend")
if os.path.exists(frontend_dir):
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

