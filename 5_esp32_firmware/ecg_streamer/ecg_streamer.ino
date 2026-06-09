#include <WiFi.h>
#include <WebSocketsClient.h>
#include "config.h"

WebSocketsClient webSocket;
unsigned long lastSampleTime = 0;

// Buffer to hold our samples before sending
uint16_t sampleBuffer[BATCH_SIZE];
int sampleIndex = 0;

void webSocketEvent(WStype_t type, uint8_t * payload, size_t length) {
    switch(type) {
        case WStype_DISCONNECTED:
            Serial.println("[WS] Disconnected!");
            break;
        case WStype_CONNECTED:
            Serial.printf("[WS] Connected to url: %s\n", payload);
            break;
        case WStype_TEXT:
        case WStype_BIN:
            break;
    }
}

void setup() {
    Serial.begin(115200);
    
    // Configure AD8232 pins
    pinMode(LO_PLUS_PIN, INPUT);
    pinMode(LO_MINUS_PIN, INPUT);
    // ADC resolution on ESP32 is 12-bit (0-4095) by default
    analogReadResolution(12);

    // Connect to WiFi
    Serial.print("Connecting to WiFi ");
    Serial.println(ssid);
    WiFi.begin(ssid, password);
    while (WiFi.status() != WL_CONNECTED) {
        delay(500);
        Serial.print(".");
    }
    Serial.println("\nWiFi connected.");
    Serial.print("IP address: ");
    Serial.println(WiFi.localIP());

    // Connect to WebSocket Server
    webSocket.begin(ws_host, ws_port, ws_path);
    webSocket.onEvent(webSocketEvent);
    webSocket.setReconnectInterval(5000);
}

void loop() {
    webSocket.loop();

    unsigned long currentTime = millis();
    if (currentTime - lastSampleTime >= SAMPLE_DELAY_MS) {
        lastSampleTime = currentTime;

        // Check for Lead-Off condition
        bool leadOff = (digitalRead(LO_PLUS_PIN) == 1 || digitalRead(LO_MINUS_PIN) == 1);

        if (leadOff) {
            // Send Lead-Off warning if connected
            if (webSocket.isConnected() && sampleIndex == 0) { // Throttle warning
                String json = "{\"ts\":" + String(currentTime) + ",\"lo\":true}";
                webSocket.sendTXT(json);
            }
        } else {
            // Read ADC
            sampleBuffer[sampleIndex++] = analogRead(ECG_PIN);

            // If buffer is full, send it as JSON
            if (sampleIndex >= BATCH_SIZE) {
                if (webSocket.isConnected()) {
                    String json = "{\"ts\":" + String(currentTime) + ",\"lo\":false,\"v\":[";
                    for (int i = 0; i < BATCH_SIZE; i++) {
                        json += String(sampleBuffer[i]);
                        if (i < BATCH_SIZE - 1) json += ",";
                    }
                    json += "]}";
                    webSocket.sendTXT(json);
                }
                sampleIndex = 0; // Reset buffer
            }
        }
    }
}
