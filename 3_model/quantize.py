import tensorflow as tf

def convert_to_tflite_int8(qat_model, representative_dataset_gen):
    """
    Converts a Quantization-Aware Trained (QAT) Keras model to a fully
    integer quantized TFLite model suitable for Cortex-M4.
    """
    print("Converting model to TFLite Int8...")
    converter = tf.lite.TFLiteConverter.from_keras_model(qat_model)
    
    # Enable optimizations
    converter.optimizations = [tf.lite.Optimize.DEFAULT]
    
    # Set the representative dataset
    converter.representative_dataset = representative_dataset_gen
    
    # Restrict supported ops to Int8
    converter.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
    
    # Set input and output tensors to Int8
    converter.inference_input_type = tf.int8
    converter.inference_output_type = tf.int8
    
    # Convert the model
    tflite_model = converter.convert()
    
    return tflite_model

def get_representative_dataset_gen(train_ds, num_samples=100):
    """
    Generator function for the representative dataset used during quantization.
    """
    def representative_dataset_gen():
        # Unbatch and take num_samples
        dataset = train_ds.unbatch().take(num_samples)
        for input_value, _ in dataset:
            # Add batch dimension and yield
            yield [tf.expand_dims(input_value, axis=0)]
    
    return representative_dataset_gen

if __name__ == '__main__':
    # This is meant to be imported, but could be run standalone
    pass
