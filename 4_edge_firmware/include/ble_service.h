#pragma once
#include <stdint.h>

/**
 * BLE packet format:
 * Byte 0    : Class ID (0=Normal, 1=AFib, 2=PVC)
 * Byte 1    : Confidence (0-255 mapped from 0-1.0)
 * Byte 2-5  : Timestamp (ms since boot, uint32)
 * Byte 6-7  : Heart rate (BPM, uint16)
 * Byte 8-N  : Delta-encoded ECG segment
 */

class BleService {
public:
    void init() {
        // Initialize STM32WPAN BLE stack and ECG GATT service
    }

    int buildPacket(uint8_t* packet, int max_bytes, int predicted_class, float confidence, const int16_t* raw_ecg, int num_samples) {
        if (max_bytes < 8) return 0;
        
        packet[0] = (uint8_t)predicted_class;
        packet[1] = (uint8_t)(confidence * 255.0f);
        
        // Dummy timestamp and HR for structural completion
        uint32_t timestamp = 0; // Replace with HAL_GetTick()
        uint16_t hr = 60;       // Replace with actual HR from Pan-Tompkins
        
        packet[2] = (timestamp >> 24) & 0xFF;
        packet[3] = (timestamp >> 16) & 0xFF;
        packet[4] = (timestamp >> 8) & 0xFF;
        packet[5] = timestamp & 0xFF;
        
        packet[6] = (hr >> 8) & 0xFF;
        packet[7] = hr & 0xFF;
        
        // Simple Delta Encoding logic here
        int packet_idx = 8;
        if (num_samples > 0 && packet_idx < max_bytes) {
             // Store first sample
             // Compress rest
        }
        
        return packet_idx; // Total length
    }

    void transmit(uint8_t* packet, int length) {
        // BLE GATT notification logic
    }
};
