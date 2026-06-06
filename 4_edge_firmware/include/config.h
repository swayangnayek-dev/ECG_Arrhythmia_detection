#pragma once

// Sampling
constexpr int      kSampleRate         = 250;       // Hz
constexpr int      kWindowSizeSamples  = 500;       // 2 seconds
constexpr int      kWindowStrideSamples= 125;       // 0.5s stride -> 75% overlap

// Inference
constexpr int      kNumClasses         = 3;         // Normal, AFib, PVC
constexpr float    kConfidenceThreshold= 0.90f;     // 90%
constexpr int      kConsecutiveWindows = 3;         // trigger after 3 consecutive

// Classes
constexpr int      kClassNormal        = 0;
constexpr int      kClassAFib          = 1;
constexpr int      kClassPVC           = 2;

// BLE
constexpr int      kBlePacketMaxBytes  = 240;       // MTU-safe payload

// Tensor Arena
constexpr int      kTensorArenaSize    = 30 * 1024; // 30 KB
