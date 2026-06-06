#include "config.h"
#include "confidence_tracker.h"
#include "ble_service.h"
#include <stdint.h>

// Mock classes/structs for the missing components
class EcgPipeline {
public:
    EcgPipeline(int sample_rate) {}
    void acquireWindow(int16_t* buffer, int size, int stride) { /* Block until DMA fills buffer */ }
    void filter(const int16_t* raw, float* filtered, int size) { /* CMSIS-DSP IIR filter */ }
    void normalize(float* buffer, int size) { /* Z-score norm */ }
};

class InferenceEngine {
public:
    void init() { /* Load TFLite model, allocate arena */ }
    void quantizeInput(const float* float_input, int8_t* int8_input, int size) { /* Map float to int8 */ }
    void invoke(const int8_t* input, int* predicted_class, float* confidence) {
        // Mock inference result
        *predicted_class = kClassNormal;
        *confidence = 0.95f;
    }
};

class HapticController {
public:
    void init() { /* I2C to DRV2605L */ }
    void triggerAlert(int predicted_class) { /* Trigger vibration */ }
};

// MCU Hardware Abstraction Layer mocks
void HAL_Init() {}
void SystemClock_Config() {}
void ADC_Init(int sample_rate) {}
void enterLowPowerMode() {}

// ── Static Buffers (no dynamic allocation) ──────────────────
static int16_t  raw_buffer[kWindowSizeSamples];
static float    filtered_buffer[kWindowSizeSamples];
static int8_t   quantized_input[kWindowSizeSamples];
static uint8_t  ble_packet[kBlePacketMaxBytes];

// ── Module Instances ────────────────────────────────────────
static EcgPipeline        ecgPipeline(kSampleRate);
static InferenceEngine    inferenceEngine;
static ConfidenceTracker  confidenceTracker(kConfidenceThreshold, kConsecutiveWindows);
static HapticController   hapticCtrl;
static BleService         bleService;

int main() {
    // ── 1. Hardware Init ────────────────────────────────────
    HAL_Init();
    SystemClock_Config();
    ADC_Init(kSampleRate);          // Configure ADC + DMA for ECG
    hapticCtrl.init();              // I2C -> DRV2605L
    bleService.init();              // STM32WPAN BLE stack
    inferenceEngine.init();         // Load TFLite model, allocate arena

    // ── 2. Main Processing Loop ─────────────────────────────
    while (true) {
        // ── 2a. Acquire Window ──────────────────────────────
        ecgPipeline.acquireWindow(raw_buffer, kWindowSizeSamples, kWindowStrideSamples);

        // ── 2b. Preprocess ──────────────────────────────────
        ecgPipeline.filter(raw_buffer, filtered_buffer, kWindowSizeSamples);
        ecgPipeline.normalize(filtered_buffer, kWindowSizeSamples);

        // ── 2c. Quantize Input ──────────────────────────────
        inferenceEngine.quantizeInput(filtered_buffer, quantized_input, kWindowSizeSamples);

        // ── 2d. Run Inference ───────────────────────────────
        int    predicted_class;
        float  confidence;
        inferenceEngine.invoke(quantized_input, &predicted_class, &confidence);

        // ── 2e. Sliding Window Confidence Tracking ──────────
        bool alert_triggered = false;
        if (predicted_class != kClassNormal) {
            alert_triggered = confidenceTracker.update(predicted_class, confidence);
        } else {
            confidenceTracker.reset();
        }

        // ── 2f. Alert & Transmit ────────────────────────────
        if (alert_triggered) {
            hapticCtrl.triggerAlert(predicted_class);

            int pkt_len = bleService.buildPacket(
                ble_packet, kBlePacketMaxBytes,
                predicted_class, confidence,
                raw_buffer, kWindowSizeSamples);

            bleService.transmit(ble_packet, pkt_len);

            confidenceTracker.reset();
        }

        // ── 2g. Low-Power Idle ──────────────────────────────
        enterLowPowerMode();
    }
}
