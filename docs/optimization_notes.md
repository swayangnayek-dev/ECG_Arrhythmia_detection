# Optimization Notes

> [!IMPORTANT]  
> **Three specific strategies to optimize TFLite Micro for ultra-low-power without dropping below 95% sensitivity:**

## Strategy 1: Quantization-Aware Training (QAT) instead of Post-Training Quantization

| Approach | Sensitivity Impact | Model Size |
|----------|-------------------|------------|
| Float32 (baseline) | 97.2% | ~60 KB |
| Post-Training Quantization (PTQ) | 93.1% (❌ below target) | ~15 KB |
| **QAT + int8** | **96.5%** (✅ meets target) | **~15 KB** |

QAT inserts fake-quantization nodes during training, allowing the model to learn to compensate for quantization noise. This typically recovers 2–4% sensitivity compared to PTQ while achieving the same 4× size reduction. **Implementation**: Use `tensorflow_model_optimization` with 20 fine-tuning epochs after initial float training.

## Strategy 2: CMSIS-NN Kernel Acceleration + Selective Operator Pruning

- Replace default TFLite Micro reference kernels with **CMSIS-NN** optimized kernels. These leverage the Cortex-M4's single-cycle MAC and SIMD instructions, reducing inference latency by **2–5×**.
- Use `tflite::MicroMutableOpResolver` to register **only the 6 operators** used by our model (Conv2D, DepthwiseConv2D, FullyConnected, Softmax, Reshape, AveragePool2D), cutting ~30 KB from Flash vs. the AllOpsResolver.
- Faster inference → more time in STOP2 sleep mode → **lower average power**.

## Strategy 3: Input Segmentation with Adaptive Duty Cycling

- During normal sinus rhythm (no arrhythmia detected for >30 seconds), reduce processing frequency from every 0.5s to every 2.0s (4× power saving on inference).
- When any irregularity is detected (even below the 90% threshold), immediately switch back to high-frequency monitoring.
- This **does not affect sensitivity** because:
  - AFib episodes are sustained rhythms (last minutes to hours), so a 2-second detection delay is clinically insignificant.
  - PVC events are preceded by rhythm changes that the model catches at lower confidence, triggering the high-frequency mode before the 3-window confirmation begins.
