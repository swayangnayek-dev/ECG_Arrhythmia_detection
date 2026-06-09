#pragma once

// ==========================================
// CONFIGURATION
// ==========================================

// WiFi Credentials
const char* ssid = "YOUR_WIFI_SSID";
const char* password = "YOUR_WIFI_PASSWORD";

// Backend WebSocket Server URL
// Note: Use the IP address of the machine running the FastAPI backend.
const char* ws_host = "192.168.1.100"; 
const uint16_t ws_port = 8000;
const char* ws_path = "/ws/ecg-ingest";

// Hardware Pins (ESP32-C3)
const int ECG_PIN = 2;       // Analog input from AD8232 OUT
const int LO_PLUS_PIN = 3;   // Digital input from AD8232 LO+
const int LO_MINUS_PIN = 4;  // Digital input from AD8232 LO-

// Sampling Configuration
const int SAMPLE_RATE_HZ = 250;
const int BATCH_SIZE = 25;   // Send 25 samples per websocket message (every 100ms)

// Calculated Delay
const int SAMPLE_DELAY_MS = 1000 / SAMPLE_RATE_HZ;
