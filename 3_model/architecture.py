import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Conv1D, SeparableConv1D, MaxPool1D, GlobalAveragePooling1D, Dense, Dropout, BatchNormalization, ReLU

def build_ecg_model(input_shape=(500, 1), num_classes=3):
    """
    Builds a lightweight 1D-CNN designed for Cortex-M4 memory constraints.
    Uses Depthwise Separable Convolutions to reduce parameter count.
    
    Args:
        input_shape: Shape of the input (window_samples, channels)
        num_classes: Number of output classes (Normal, AFib, PVC)
        
    Returns:
        Keras Sequential model
    """
    model = Sequential([
        # Block 1
        Conv1D(16, kernel_size=7, strides=2, padding='same', input_shape=input_shape),
        BatchNormalization(),
        ReLU(),
        MaxPool1D(pool_size=2),
        
        # Block 2
        SeparableConv1D(32, kernel_size=5, padding='same'),
        BatchNormalization(),
        ReLU(),
        MaxPool1D(pool_size=2),
        
        # Block 3
        SeparableConv1D(64, kernel_size=3, padding='same'),
        BatchNormalization(),
        ReLU(),
        
        # Feature Aggregation
        GlobalAveragePooling1D(),
        
        # Classifier
        Dense(32),
        ReLU(),
        Dropout(0.3),
        Dense(num_classes, activation='softmax')
    ])
    
    return model

if __name__ == '__main__':
    model = build_ecg_model()
    model.summary()
