"""
Standalone ECG WebSocket Streamer (ESP32 Simulator)
Simulates an ESP32 device streaming 250Hz ECG data to the backend via WebSocket.
"""
import asyncio
import json
import math
import random
import time
import websockets

SERVER_URI = "ws://127.0.0.1:8000/ws/ecg-ingest"
SAMPLE_RATE = 250  # 250 Hz
BATCH_SIZE = 25    # 25 samples every 100ms

def generate_ecg_sample(phase: float, is_pvc: bool = False) -> float:
    baseline = 2048.0
    if is_pvc:
        qrs = -600.0 * math.exp(-((phase - 0.25) ** 2) / 0.003) + 1200.0 * math.exp(-((phase - 0.35) ** 2) / 0.006)
        t_wave = -400.0 * math.exp(-((phase - 0.6) ** 2) / 0.02)
        noise = random.gauss(0, 15)
        return baseline + qrs + t_wave + noise

    p_wave = 150.0 * math.exp(-((phase - 0.15) ** 2) / 0.0015)
    q_wave = -120.0 * math.exp(-((phase - 0.27) ** 2) / 0.0003)
    r_wave = 1400.0 * math.exp(-((phase - 0.30) ** 2) / 0.0004)
    s_wave = -350.0 * math.exp(-((phase - 0.33) ** 2) / 0.0004)
    t_wave = 280.0 * math.exp(-((phase - 0.60) ** 2) / 0.006)
    wander = 40.0 * math.sin(phase * 2 * math.pi)
    noise = random.gauss(0, 12)
    return baseline + p_wave + q_wave + r_wave + s_wave + t_wave + wander + noise

async def stream_ecg():
    print(f"Connecting to ECG Ingestion server at {SERVER_URI}...")
    while True:
        try:
            async with websockets.connect(SERVER_URI) as ws:
                print("Connected! Streaming simulated ECG data @ 250Hz...")
                dt = 1.0 / SAMPLE_RATE
                target_hr = 72.0
                phase = 0.0
                beat_counter = 0
                pvc_active = False

                while True:
                    start_t = time.time()
                    samples = []
                    for _ in range(BATCH_SIZE):
                        bpm = target_hr + random.uniform(-1.5, 1.5)
                        phase_step = (bpm / 60.0) * dt
                        phase += phase_step
                        if phase >= 1.0:
                            phase -= 1.0
                            beat_counter += 1
                            pvc_active = (beat_counter % random.randint(12, 18) == 0)

                        val = generate_ecg_sample(phase, is_pvc=pvc_active)
                        samples.append(int(val))

                    payload = {
                        "ts": int(time.time() * 1000),
                        "lo": False,
                        "v": samples
                    }
                    await ws.send(json.dumps(payload))
                    elapsed = time.time() - start_t
                    sleep_dur = max(0.001, (BATCH_SIZE / SAMPLE_RATE) - elapsed)
                    await asyncio.sleep(sleep_dur)
        except Exception as e:
            print(f"Connection error: {e}. Retrying in 3 seconds...")
            await asyncio.sleep(3)

if __name__ == "__main__":
    asyncio.run(stream_ecg())
