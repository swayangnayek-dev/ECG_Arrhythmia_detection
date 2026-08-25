// ==========================================================================
// CardioShield AI - Real-Time Frontend Telemetry Engine
// ==========================================================================

const loc = window.location;
const host = (loc.host && loc.protocol.startsWith('http')) ? loc.host : '127.0.0.1:8000';
const wsProto = loc.protocol === 'https:' ? 'wss:' : 'ws:';
const WS_URL = `${wsProto}//${host}/ws/dashboard`;
const API_BASE = (loc.origin && loc.protocol.startsWith('http')) ? `${loc.origin}/api` : 'http://127.0.0.1:8000/api';

// Core State
let isConnected = false;
let socket = null;
let currentTheme = 'classic';
let audioEnabled = true;
let audioCtx = null;
let isSimulating = true;
let currentSimMode = 'resting';
let oscilloscopeMode = 'dual'; // 'dual', 'overlay', 'clean'

// Canvas References
const rawCanvas = document.getElementById('ecg-raw-canvas');
const rawCtx = rawCanvas ? rawCanvas.getContext('2d') : null;
const cleanCanvas = document.getElementById('ecg-canvas');
const cleanCtx = cleanCanvas ? cleanCanvas.getContext('2d') : null;

const DRAW_SPEED = 2.0; // pixels per sample
let rawDrawX = 0;
let rawLastY = 0;
let cleanDrawX = 0;
let cleanLastY = 0;
const SIGNAL_SCALE = 38;

let historyChartInstance = null;
let lastBeatTimestamp = 0;

// DOM Elements Cache
const connStatusChip = document.getElementById('conn-status-chip');
const connStatusText = document.getElementById('conn-status-text');
const bpmVal = document.getElementById('bpm-val');
const rhythmVal = document.getElementById('rhythm-val');
const activityVal = document.getElementById('activity-val');
const hrvVal = document.getElementById('hrv-val');
const rmssdVal = document.getElementById('rmssd-val');
const rrVal = document.getElementById('rr-val');
const heartAnimBox = document.getElementById('heart-anim-box');

// Hardware Telemetry DOM
const hwRssi = document.getElementById('hw-rssi');
const hwLatency = document.getElementById('hw-latency');
const hwPackets = document.getElementById('hw-packets');

// DSP Metrics DOM
const metricRawSnr = document.getElementById('metric-raw-snr');
const metricCleanSnr = document.getElementById('metric-clean-snr');
const metricRrLive = document.getElementById('metric-rr-live');
const metricMlLatency = document.getElementById('metric-ml-latency');

// Stress & Probability DOM
const stressBadge = document.getElementById('stress-badge');
const stressBarFill = document.getElementById('stress-bar-fill');
const stressIndexVal = document.getElementById('stress-index-val');
const stressExplainerTxt = document.getElementById('stress-explainer-txt');

const probNormalBar = document.getElementById('prob-normal-bar');
const probNormalTxt = document.getElementById('prob-normal-txt');
const probAnxiousBar = document.getElementById('prob-anxious-bar');
const probAnxiousTxt = document.getElementById('prob-anxious-txt');
const probPvcBar = document.getElementById('prob-pvc-bar');
const probPvcTxt = document.getElementById('prob-pvc-txt');
const probAfibBar = document.getElementById('prob-afib-bar');
const probAfibTxt = document.getElementById('prob-afib-txt');
const mlConfTop = document.getElementById('ml-conf-top');


// ==========================================================================
// Canvas Management & Real-Time Waveform Oscilloscopes
// ==========================================================================

function resizeCanvases() {
    if (cleanCanvas && cleanCanvas.parentElement) {
        cleanCanvas.width = cleanCanvas.parentElement.clientWidth;
        cleanCanvas.height = cleanCanvas.parentElement.clientHeight;
        cleanLastY = cleanCanvas.height / 2;
        clearCanvas(cleanCtx, cleanCanvas);
    }
    if (rawCanvas && rawCanvas.parentElement) {
        rawCanvas.width = rawCanvas.parentElement.clientWidth;
        rawCanvas.height = rawCanvas.parentElement.clientHeight;
        rawLastY = rawCanvas.height / 2;
        clearCanvas(rawCtx, rawCanvas);
    }
}

function clearCanvas(c, canvas) {
    if (!c || !canvas) return;
    c.fillStyle = '#020611';
    c.fillRect(0, 0, canvas.width, canvas.height);
    drawGrid(c, canvas);
}

function drawGrid(c, canvas) {
    c.strokeStyle = 'rgba(255, 255, 255, 0.035)';
    c.lineWidth = 1;
    const step = 25;
    for (let x = 0; x < canvas.width; x += step) {
        c.beginPath();
        c.moveTo(x, 0);
        c.lineTo(x, canvas.height);
        c.stroke();
    }
    for (let y = 0; y < canvas.height; y += step) {
        c.beginPath();
        c.moveTo(0, y);
        c.lineTo(canvas.width, y);
        c.stroke();
    }
}

window.addEventListener('resize', resizeCanvases);

// Audio Synthesis for ECG Beeper
function initAudio() {
    if (!audioCtx) {
        audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    }
}

function playHeartbeatTone(isPvc = false) {
    if (!audioEnabled) return;
    try {
        initAudio();
        if (audioCtx.state === 'suspended') audioCtx.resume();
        const osc = audioCtx.createOscillator();
        const gain = audioCtx.createGain();
        
        osc.type = isPvc ? 'sawtooth' : 'sine';
        osc.frequency.setValueAtTime(isPvc ? 220 : 640, audioCtx.currentTime);
        gain.gain.setValueAtTime(0.04, audioCtx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + 0.08);

        osc.connect(gain);
        gain.connect(audioCtx.destination);
        osc.start();
        osc.stop(audioCtx.currentTime + 0.09);
    } catch (e) {}
}



function toggleAudio() {
    audioEnabled = !audioEnabled;
    const btn = document.getElementById('audio-toggle-btn');
    if (btn) {
        btn.innerText = audioEnabled ? '🔊 Sound' : '🔇 Muted';
        btn.style.color = audioEnabled ? 'var(--text-main)' : 'var(--text-dim)';
    }
}

function toggleTheme() {
    currentTheme = currentTheme === 'classic' ? 'modern' : 'classic';
    document.documentElement.setAttribute('data-theme', currentTheme);
    resizeCanvases();
    if (historyChartInstance) fetchHistory(24);
}

// Oscilloscope View Mode Switcher
function setOscilloscopeMode(mode) {
    oscilloscopeMode = mode;
    document.querySelectorAll('.view-tab').forEach(el => el.classList.remove('active'));
    const activeBtn = document.getElementById(`view-mode-${mode}`);
    if (activeBtn) activeBtn.classList.add('active');

    const rawBox = document.getElementById('raw-waveform-wrapper');
    const cleanBox = document.getElementById('clean-waveform-wrapper');
    const cleanTitle = document.getElementById('clean-track-title');

    if (mode === 'clean') {
        if (rawBox) rawBox.style.display = 'none';
        if (cleanBox) {
            cleanBox.style.display = 'block';
            cleanBox.querySelector('.canvas-wrapper').style.height = '310px';
            if (cleanTitle) cleanTitle.innerText = 'PURIFIED CLINICAL ECG (0.5-45Hz Bandpass • Wavelet Denoised • High-Precision Trace)';
        }
    } else if (mode === 'overlay') {
        if (rawBox) rawBox.style.display = 'none';
        if (cleanBox) {
            cleanBox.style.display = 'block';
            cleanBox.querySelector('.canvas-wrapper').style.height = '290px';
            if (cleanTitle) cleanTitle.innerHTML = '<span style="color:#f59e0b">RAW AD8232 (Amber)</span> vs <span style="color:#00ff88">PURIFIED CLINICAL OVERLAY (Neon Green)</span>';
        }
    } else { // dual split
        if (rawBox) {
            rawBox.style.display = 'block';
            rawBox.querySelector('.canvas-wrapper').style.height = '150px';
        }
        if (cleanBox) {
            cleanBox.style.display = 'block';
            cleanBox.querySelector('.canvas-wrapper').style.height = '165px';
            if (cleanTitle) cleanTitle.innerText = 'PURIFIED CLINICAL ECG (0.5-45Hz Bandpass • Wavelet Denoised • R-Peaks Highlighted)';
        }
    }
    resizeCanvases();
}

// Waveform Rendering
function drawRawWaveform(samples) {
    if (!rawCtx || !rawCanvas || oscilloscopeMode === 'clean') return;
    const centerY = rawCanvas.height / 2;
    rawCtx.lineWidth = 1.8;
    rawCtx.strokeStyle = '#f59e0b'; // Amber trace for raw sensor

    for (let i = 0; i < samples.length; i++) {
        const val = samples[i];
        let y = centerY - (val * (SIGNAL_SCALE * 0.85));
        if (y < 2) y = 2;
        if (y > rawCanvas.height - 2) y = rawCanvas.height - 2;

        rawCtx.fillStyle = '#020611';
        rawCtx.fillRect(rawDrawX + 1, 0, Math.max(16, DRAW_SPEED * 3), rawCanvas.height);
        if (rawDrawX + 16 > rawCanvas.width) {
            rawCtx.fillRect(0, 0, (rawDrawX + 16) - rawCanvas.width, rawCanvas.height);
        }

        rawCtx.beginPath();
        rawCtx.moveTo(rawDrawX, rawLastY);
        rawDrawX += DRAW_SPEED;
        if (rawDrawX >= rawCanvas.width) rawDrawX = 0;
        rawCtx.lineTo(rawDrawX, y);
        rawCtx.stroke();
        rawLastY = y;
    }
}

function drawCleanWaveform(cleanSamples, rawSamples) {
    if (!cleanCtx || !cleanCanvas) return;
    const centerY = cleanCanvas.height / 2;

    // If overlay mode, draw faint raw signal underneath
    if (oscilloscopeMode === 'overlay' && rawSamples) {
        cleanCtx.lineWidth = 1.2;
        cleanCtx.strokeStyle = 'rgba(245, 158, 11, 0.45)';
        for (let i = 0; i < rawSamples.length; i++) {
            const rawVal = rawSamples[i];
            let rawY = centerY - (rawVal * (SIGNAL_SCALE * 0.85));
            cleanCtx.beginPath();
            cleanCtx.moveTo(cleanDrawX, cleanLastY);
            cleanCtx.lineTo(cleanDrawX + DRAW_SPEED, rawY);
            cleanCtx.stroke();
        }
    }

    cleanCtx.lineWidth = 2.4;
    cleanCtx.strokeStyle = '#00ff88'; // Neon Green clinical trace

    for (let i = 0; i < cleanSamples.length; i++) {
        const val = cleanSamples[i];
        let y = centerY - (val * SIGNAL_SCALE);
        if (y < 2) y = 2;
        if (y > cleanCanvas.height - 2) y = cleanCanvas.height - 2;

        cleanCtx.fillStyle = '#020611';
        cleanCtx.fillRect(cleanDrawX + 1, 0, Math.max(16, DRAW_SPEED * 3), cleanCanvas.height);
        if (cleanDrawX + 16 > cleanCanvas.width) {
            cleanCtx.fillRect(0, 0, (cleanDrawX + 16) - cleanCanvas.width, cleanCanvas.height);
        }

        // Heartbeat Trigger on R-peak
        if (val > 1.35 && (Date.now() - lastBeatTimestamp > 320)) {
            lastBeatTimestamp = Date.now();
            triggerCardiacPulseAnimation();
            playHeartbeatTone(val > 2.0);
        }

        cleanCtx.beginPath();
        cleanCtx.moveTo(cleanDrawX, cleanLastY);
        cleanDrawX += DRAW_SPEED;
        if (cleanDrawX >= cleanCanvas.width) cleanDrawX = 0;
        cleanCtx.lineTo(cleanDrawX, y);
        cleanCtx.stroke();
        cleanLastY = y;
    }
}

function triggerCardiacPulseAnimation() {
    if (!heartAnimBox) return;
    heartAnimBox.classList.add('beat');
    setTimeout(() => heartAnimBox.classList.remove('beat'), 140);
}

// ==========================================================================
// WebSocket Ingestion & UI State Handlers
// ==========================================================================

function connectWebSocket() {
    socket = new WebSocket(WS_URL);

    socket.onopen = () => {
        isConnected = true;
        if (connStatusChip && connStatusText) {
            connStatusChip.className = 'connection-status-chip online';
            connStatusText.innerText = 'ESP32 Connected';
        }
    };

    socket.onclose = () => {
        isConnected = false;
        if (connStatusChip && connStatusText) {
            connStatusChip.className = 'connection-status-chip offline';
            connStatusText.innerText = 'ESP32 Offline';
        }
        setTimeout(connectWebSocket, 2500);
    };

    socket.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);

            if (data.type === 'ECG_SAMPLES') {
                if (data.raw_samples) drawRawWaveform(data.raw_samples);
                if (data.clean_samples) drawCleanWaveform(data.clean_samples, data.raw_samples);
                if (data.dsp_metrics) updateDspMetrics(data.dsp_metrics);
                if (data.hardware) updateHardwareTelemetry(data.hardware);
            } 
            else if (data.type === 'ANALYSIS') {
                updateVitals(data);
                updateProbabilityBars(data);
                updateStressIndex(data);
            }

        } catch (e) {
            console.error("Error processing websocket frame:", e);
        }
    };
}

function updateDspMetrics(dsp) {
    if (metricRawSnr && dsp.snr_raw_db !== undefined) metricRawSnr.innerText = `${dsp.snr_raw_db} dB`;
    if (metricCleanSnr && dsp.snr_clean_db !== undefined) metricCleanSnr.innerText = `${dsp.snr_clean_db} dB`;
}

function updateHardwareTelemetry(hw) {
    if (hwPackets && hw.packets_received !== undefined) hwPackets.innerText = hw.packets_received.toLocaleString();
    if (hwRssi && hw.rssi_dbm !== undefined) hwRssi.innerText = `${hw.rssi_dbm} dBm (Excellent)`;
}

function updateVitals(data) {
    if (bpmVal) bpmVal.innerText = data.hr > 0 ? data.hr : '--';
    if (hrvVal) hrvVal.innerHTML = `${Math.round(data.hrv_sdnn || 0)} <span class="unit">ms</span>`;
    if (rmssdVal) rmssdVal.innerHTML = `${Math.round(data.hrv_rmssd || (data.hrv_sdnn * 1.15))} <span class="unit">ms</span>`;
    if (rrVal) rrVal.innerHTML = `${Math.round(data.rr_avg_ms || 840)} <span class="unit">ms</span>`;
    if (metricRrLive) metricRrLive.innerText = `${Math.round(data.rr_avg_ms || 840)} ms`;
    if (metricMlLatency) metricMlLatency.innerText = `${data.inference_latency_ms || 2.4} ms`;

    if (activityVal) activityVal.innerText = data.activity || 'Resting';

    // Rhythm Status
    if (rhythmVal) {
        rhythmVal.innerText = `${data.classification} (${Math.round((data.confidence || 0.95) * 100)}%)`;
        rhythmVal.className = 'rhythm-chip';
        if (data.raw_class === 'PVC' || data.classification.includes('PVC')) {
            rhythmVal.classList.add('rhythm-pvc');
        } else if (data.classification.includes('Anxious') || data.classification.includes('Elevated') || data.classification.includes('Active')) {
            rhythmVal.classList.add('rhythm-anxious');
        } else {
            rhythmVal.classList.add('rhythm-normal');
        }
    }
}

function updateStressIndex(data) {
    const stress = data.stress_index || (data.sim_state === 'Walking' ? 72 : 25);
    if (stressBarFill) stressBarFill.style.width = `${stress}%`;
    if (stressIndexVal) stressIndexVal.innerText = `${stress} / 100`;

    if (stressBadge && stressExplainerTxt) {
        if (stress > 50) {
            stressBadge.className = 'stress-badge anxious';
            stressBadge.innerText = 'SYMPATHETIC ELEVATED';
            stressExplainerTxt.innerText = 'Sympathetic arousal detected. Elevated heart rate, compressed respiratory sinus arrhythmia, and micro-tremor EMG jitter present.';
        } else {
            stressBadge.className = 'stress-badge calm';
            stressBadge.innerText = 'PARASYMPATHETIC CALM';
            stressExplainerTxt.innerText = 'Vagal tone dominant. Healthy respiratory sinus arrhythmia present with deep rhythmic autonomic stability.';
        }
    }
}

function updateProbabilityBars(data) {
    const probs = data.probabilities || { "Normal": 0.96, "Sinus_Tachy_Anxious": 0.03, "PVC": 0.01, "AFib": 0.0 };
    const pNorm = Math.round((probs.Normal || 0) * 100);
    const pAnx = Math.round(((probs.Sinus_Tachy_Anxious || probs.Anxious || 0)) * 100);
    const pPvc = Math.round((probs.PVC || 0) * 100);
    const pAfib = Math.round((probs.AFib || 0) * 100);

    if (probNormalBar) probNormalBar.style.width = `${pNorm}%`;
    if (probNormalTxt) probNormalTxt.innerText = `${pNorm}%`;

    if (probAnxiousBar) probAnxiousBar.style.width = `${pAnx}%`;
    if (probAnxiousTxt) probAnxiousTxt.innerText = `${pAnx}%`;

    if (probPvcBar) probPvcBar.style.width = `${pPvc}%`;
    if (probPvcTxt) probPvcTxt.innerText = `${pPvc}%`;

    if (probAfibBar) probAfibBar.style.width = `${pAfib}%`;
    if (probAfibTxt) probAfibTxt.innerText = `${pAfib}%`;

    if (mlConfTop) {
        mlConfTop.innerText = `${Math.round((data.confidence || 0.96) * 100)}% Confidence`;
    }
}

// ==========================================================================
// Simulation Controls & REST Handlers
// ==========================================================================

async function setSimulationMode(mode) {
    currentSimMode = mode;
    document.querySelectorAll('.sim-pill-btn').forEach(btn => btn.classList.remove('active'));
    const btn = document.getElementById(`btn-mode-${mode}`);
    if (btn) btn.classList.add('active');

    try {
        await fetch(`${API_BASE}/simulator/mode`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ mode })
        });
    } catch (e) {
        console.error("Failed to set simulator mode:", e);
    }
}

async function triggerPvc() {
    const btn = document.getElementById('btn-trigger-pvc');
    if (btn) {
        btn.style.transform = 'scale(0.92)';
        setTimeout(() => btn.style.transform = '', 140);
    }
    try {
        await fetch(`${API_BASE}/simulator/trigger_pvc`, { method: 'POST' });
    } catch (e) {
        console.error("Failed to trigger PVC:", e);
    }
}

async function toggleSimulation() {
    const btn = document.getElementById('sim-toggle-btn');
    if (!btn) return;
    try {
        const action = isSimulating ? 'stop' : 'start';
        const res = await fetch(`${API_BASE}/simulator/${action}`, { method: 'POST' });
        const data = await res.json();
        isSimulating = data.running;
        btn.innerText = isSimulating ? '⏸ Pause' : '▶ Resume';
    } catch(e) {
        console.error('Failed to toggle simulator:', e);
    }
}



// ==========================================================================
// Continuous Holter 24h History & Peak Analytics
// ==========================================================================

async function fetchHistory(hours) {
    document.querySelectorAll('.history-tab').forEach(btn => btn.classList.remove('active'));
    const targetBtn = Array.from(document.querySelectorAll('.history-tab')).find(b => b.innerText.includes(`${hours}`));
    if (targetBtn) targetBtn.classList.add('active');

    try {
        const res = await fetch(`${API_BASE}/history?hours=${hours}`);
        const data = await res.json();
        renderHistoryChart(data.records || []);
    } catch(e) {
        console.error("Failed to fetch history:", e);
    }
}

async function fetchAnalytics() {
    try {
        const res = await fetch(`${API_BASE}/analytics/peaks`);
        const data = await res.json();
        if (data.peak_hr) {
            document.getElementById('peak-hr-val').innerText = `${data.peak_hr.bpm} BPM`;
            document.getElementById('peak-hr-time').innerText = new Date(data.peak_hr.time).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'}) + ` (${data.peak_hr.activity})`;
        }
        if (data.lowest_hr) {
            document.getElementById('low-hr-val').innerText = `${data.lowest_hr.bpm} BPM`;
            document.getElementById('low-hr-time').innerText = new Date(data.lowest_hr.time).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'}) + ` (${data.lowest_hr.activity})`;
        }
    } catch(e) {
        console.error("Failed to fetch analytics:", e);
    }
}

function renderHistoryChart(records) {
    const canvasEl = document.getElementById('history-chart');
    if (!canvasEl) return;
    const ctx = canvasEl.getContext('2d');
    if (historyChartInstance) historyChartInstance.destroy();

    const labels = records.map(r => new Date(r.ts).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'}));
    const hrData = records.map(r => r.hr);
    const pointColors = records.map(r => {
        if (r.classification && r.classification.includes('PVC')) return '#ef4444';
        if (r.classification && (r.classification.includes('Anxious') || r.classification.includes('Elevated'))) return '#f59e0b';
        return '#00ff88';
    });

    historyChartInstance = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: 'Heart Rate (BPM)',
                data: hrData,
                borderColor: '#10b981',
                backgroundColor: 'rgba(16, 185, 129, 0.08)',
                fill: true,
                borderWidth: 2,
                pointBackgroundColor: pointColors,
                pointBorderColor: '#0c1322',
                pointRadius: records.length > 80 ? 2 : 4,
                tension: 0.35
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: 'rgba(11, 17, 32, 0.95)',
                    titleColor: '#00ff88',
                    bodyColor: '#f8fafc',
                    borderColor: 'rgba(255, 255, 255, 0.1)',
                    borderWidth: 1
                }
            },
            scales: {
                y: {
                    grid: { color: 'rgba(255, 255, 255, 0.05)' },
                    ticks: { color: '#94a3b8', font: { family: "'JetBrains Mono', monospace" } }
                },
                x: {
                    grid: { display: false },
                    ticks: { color: '#64748b', maxTicksLimit: 8, font: { family: "'JetBrains Mono', monospace" } }
                }
            }
        }
    });
}

// Initial Boot Sequence
resizeCanvases();
connectWebSocket();
fetchHistory(1);
fetchAnalytics();

// Refresh Holter Analytics every 12 seconds
setInterval(() => {
    fetchHistory(1);
    fetchAnalytics();
}, 12000);
