import tensorflow as tf
import tensorflow_model_optimization as tfmot
from architecture import build_ecg_model

def train_model(train_ds, val_ds, epochs=100, learning_rate=1e-3):
    """
    Standard training loop with EarlyStopping and ReduceLROnPlateau.
    """
    model = build_ecg_model()
    
    # Compile
    optimizer = tf.keras.optimizers.Adam(learning_rate=learning_rate)
    # Using CategoricalCrossentropy; Focal Loss can be used for imbalanced datasets
    loss = tf.keras.losses.SparseCategoricalCrossentropy()
    
    model.compile(optimizer=optimizer, loss=loss, metrics=['accuracy'])
    
    # Callbacks
    callbacks = [
        tf.keras.callbacks.EarlyStopping(patience=15, restore_best_weights=True),
        tf.keras.callbacks.ReduceLROnPlateau(factor=0.5, patience=5)
    ]
    
    print("Starting initial training...")
    history = model.fit(
        train_ds,
        validation_data=val_ds,
        epochs=epochs,
        callbacks=callbacks
    )
    
    return model

def finetune_qat(model, train_ds, val_ds, epochs=20):
    """
    Quantization-Aware Training (QAT) fine-tuning to prepare the model
    for Int8 conversion without significant accuracy loss.
    """
    print("Starting Quantization-Aware Training (QAT)...")
    quantize_model = tfmot.quantization.keras.quantize_model
    
    # Create QAT model
    qat_model = quantize_model(model)
    
    # Need to recompile the QAT model
    qat_model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=1e-4), # Lower LR for finetuning
        loss=tf.keras.losses.SparseCategoricalCrossentropy(),
        metrics=['accuracy']
    )
    
    qat_model.fit(
        train_ds,
        validation_data=val_ds,
        epochs=epochs
    )
    
    return qat_model
