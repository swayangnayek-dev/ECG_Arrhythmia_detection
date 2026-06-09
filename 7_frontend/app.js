const WS_URL = 'ws://127.0.0.1:8000/ws/dashboard';
const API_BASE = 'http://127.0.0.1:8000/api';

// State
let isConnected = false;
let socket = null;
let currentTheme = 'classic';
let audioCtx = null;

// DOM Elements
const connStatus = document.getElementById('conn-status');
const bpmVal = document.getElementById('bpm-val');
const rhythmVal = document.getElementById('rhythm-val');
const activityVal = document.getElementById('activity-val');
const hrvVal = document.getElementById('hrv-val');
const alertModal = document.getElementById('alert-modal');
const alertTitle = document.getElementById('alert-title');
const alertMsg = document.getElementById('alert-msg');
const ecgCanvas = document.getElementById('ecg-canvas');
const ctx = ecgCanvas.getContext('2d');

// Waveform settings
const DRAW_SPEED = 2; // pixels per sample
let drawX = 0;
let lastY = 0;
const SIGNAL_SCALE = 50; // Scaling for Z-scored or raw amplitude
let historyChartInstance = null;

function toggleTheme() {
    currentTheme = currentTheme === 'classic' ? 'modern' : 'classic';
    document.documentElement.setAttribute('data-theme', currentTheme);
    resizeCanvas();
    if(historyChartInstance) fetchHistory(24); // Redraw with new theme colors
}

function initAudio() {
    if (!audioCtx) {
        audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    }
}

function playAlarm() {
    initAudio();
    if(audioCtx.state === 'suspended') audioCtx.resume();
    
    const osc = audioCtx.createOscillator();
    const gain = audioCtx.createGain();
    
    osc.type = 'square';
    osc.frequency.setValueAtTime(800, audioCtx.currentTime);
    osc.frequency.setValueAtTime(1000, audioCtx.currentTime + 0.2);
    
    gain.gain.setValueAtTime(0.1, audioCtx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + 0.4);
    
    osc.connect(gain);
    gain.connect(audioCtx.destination);
    
    osc.start();
    osc.stop(audioCtx.currentTime + 0.5);
}

function showAlert(title, msg) {
    alertTitle.innerText = title;
    alertMsg.innerText = msg;
    alertModal.classList.remove('hidden');
    playAlarm();
    
    // Notification API
    if (Notification.permission === 'granted') {
        new Notification(`ECG ALERT: ${title}`, { body: msg });
    }
}

function dismissAlert() {
    alertModal.classList.add('hidden');
}

function resizeCanvas() {
    ecgCanvas.width = ecgCanvas.parentElement.clientWidth;
    ecgCanvas.height = ecgCanvas.parentElement.clientHeight;
    lastY = ecgCanvas.height / 2;
    
    // Clear canvas
    ctx.fillStyle = currentTheme === 'classic' ? '#000000' : '#1e293b';
    ctx.fillRect(0, 0, ecgCanvas.width, ecgCanvas.height);
}

window.addEventListener('resize', resizeCanvas);
resizeCanvas();

function drawWaveform(samples) {
    const centerY = ecgCanvas.height / 2;
    const strokeColor = currentTheme === 'classic' ? '#00ff88' : '#3b82f6';
    const bgColor = currentTheme === 'classic' ? '#000000' : '#1e293b';

    ctx.lineWidth = 2;
    ctx.strokeStyle = strokeColor;
    
    for (let i = 0; i < samples.length; i++) {
        const val = samples[i];
        // Assuming val is normalized around 0. If it's raw 0-4095, subtract 2048 and scale.
        // Let's assume it's somewhat raw but baseline subtracted by the backend filter.
        let y = centerY - (val * SIGNAL_SCALE); 
        
        // Clamp Y
        if (y < 0) y = 0;
        if (y > ecgCanvas.height) y = ecgCanvas.height;

        // Erase ahead (with wrap-around handling)
        ctx.fillStyle = bgColor;
        ctx.fillRect(drawX + 1, 0, Math.max(15, DRAW_SPEED * 2), ecgCanvas.height);
        if (drawX + 15 > ecgCanvas.width) {
            ctx.fillRect(0, 0, (drawX + 15) - ecgCanvas.width, ecgCanvas.height);
        }

        ctx.beginPath();
        ctx.moveTo(drawX, lastY);
        
        drawX += DRAW_SPEED;
        if (drawX >= ecgCanvas.width) {
            drawX = 0;
        }

        ctx.lineTo(drawX, y);
        ctx.stroke();
        lastY = y;
    }
}

function connectWebSocket() {
    socket = new WebSocket(WS_URL);

    socket.onopen = () => {
        isConnected = true;
        connStatus.innerText = '● Connected';
        connStatus.className = 'status-indicator online';
    };

    socket.onclose = () => {
        isConnected = false;
        connStatus.innerText = '● Offline';
        connStatus.className = 'status-indicator offline';
        setTimeout(connectWebSocket, 3000);
    };

    socket.onmessage = (event) => {
        const data = JSON.parse(event.data);

        if (data.type === 'ECG_SAMPLES') {
            drawWaveform(data.samples);
        } 
        else if (data.type === 'ANALYSIS') {
            updateVitals(data);
        }
        else if (data.type === 'DANGER_ALERT') {
            showAlert(data.condition, data.message);
        }
    };
}

function updateVitals(data) {
    bpmVal.innerHTML = `${data.hr} <span class="unit">BPM</span>`;
    hrvVal.innerHTML = `${Math.round(data.hrv_sdnn)} <span class="unit">ms</span>`;
    activityVal.innerText = data.activity;
    
    rhythmVal.innerText = `${data.classification} (${Math.round(data.confidence*100)}%)`;
    rhythmVal.className = 'vital-value';
    if(data.classification === 'Normal') rhythmVal.classList.add('rhythm-normal');
    else if(data.classification === 'AFib') rhythmVal.classList.add('rhythm-afib');
    else rhythmVal.classList.add('rhythm-pvc');
}

async function fetchHistory(hours) {
    try {
        const res = await fetch(`${API_BASE}/history?hours=${hours}`);
        const data = await res.json();
        renderHistoryChart(data.records);
    } catch(e) {
        console.error("Failed to fetch history", e);
    }
}

async function fetchAnalytics() {
    try {
        const res = await fetch(`${API_BASE}/analytics/peaks`);
        const data = await res.json();
        
        if (data.peak_hr) {
            document.getElementById('peak-hr-val').innerText = `${data.peak_hr.bpm} BPM`;
            document.getElementById('peak-hr-time').innerText = new Date(data.peak_hr.time).toLocaleTimeString() + ` (${data.peak_hr.activity})`;
        }
        if (data.low_hr) {
            document.getElementById('low-hr-val').innerText = `${data.low_hr.bpm} BPM`;
            document.getElementById('low-hr-time').innerText = new Date(data.low_hr.time).toLocaleTimeString() + ` (${data.low_hr.activity})`;
        }
    } catch(e) {
        console.error("Failed to fetch analytics", e);
    }
}

function renderHistoryChart(records) {
    const ctx = document.getElementById('history-chart').getContext('2d');
    
    if (historyChartInstance) {
        historyChartInstance.destroy();
    }

    const labels = records.map(r => new Date(r.ts).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'}));
    const hrData = records.map(r => r.hr);
    const pointColors = records.map(r => {
        if(r.classification === 'AFib') return '#f59e0b';
        if(r.classification === 'PVC') return '#ef4444';
        return currentTheme === 'classic' ? '#00ff88' : '#3b82f6';
    });

    const textColor = currentTheme === 'classic' ? '#00ff88' : '#f8fafc';
    const gridColor = currentTheme === 'classic' ? 'rgba(0,255,136,0.1)' : 'rgba(255,255,255,0.1)';

    historyChartInstance = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: 'Heart Rate (BPM)',
                data: hrData,
                borderColor: currentTheme === 'classic' ? '#00ff88' : '#3b82f6',
                borderWidth: 2,
                pointBackgroundColor: pointColors,
                pointRadius: records.length > 100 ? 0 : 3,
                tension: 0.4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false }
            },
            scales: {
                y: {
                    grid: { color: gridColor },
                    ticks: { color: textColor }
                },
                x: {
                    grid: { display: false },
                    ticks: { color: textColor, maxTicksLimit: 10 }
                }
            }
        }
    });
}

// Request Notification Permission
if ("Notification" in window && Notification.permission !== "granted") {
    Notification.requestPermission();
}

// Start
connectWebSocket();
fetchHistory(1);
fetchAnalytics();

// Periodically update history
setInterval(() => {
    fetchHistory(1);
    fetchAnalytics();
}, 60000);
