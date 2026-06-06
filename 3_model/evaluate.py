import numpy as np
from sklearn.metrics import classification_report, confusion_matrix

def evaluate_model(model, test_ds, is_tflite=False):
    """
    Evaluates the trained model or TFLite model on the test dataset.
    Computes Sensitivity, Specificity, PPV, and F1-score per class.
    """
    y_true = []
    y_pred = []
    
    print("Evaluating model...")
    # For a Keras model
    if not is_tflite:
        for x, y in test_ds:
            preds = model.predict(x, verbose=0)
            y_true.extend(y.numpy())
            y_pred.extend(np.argmax(preds, axis=1))
    else:
        # TFLite inference
        interpreter = model
        input_details = interpreter.get_input_details()
        output_details = interpreter.get_output_details()
        
        for x, y in test_ds:
            for i in range(x.shape[0]):
                input_data = np.expand_dims(x[i], axis=0).astype(input_details[0]['dtype'])
                interpreter.set_tensor(input_details[0]['index'], input_data)
                interpreter.invoke()
                output_data = interpreter.get_tensor(output_details[0]['index'])
                
                y_true.append(y[i].numpy())
                y_pred.append(np.argmax(output_data))
                
    y_true = np.array(y_true)
    y_pred = np.array(y_pred)
    
    print("\nClassification Report:")
    print(classification_report(y_true, y_pred, target_names=['Normal', 'AFib', 'PVC']))
    
    print("\nConfusion Matrix:")
    print(confusion_matrix(y_true, y_pred))
    
    # Calculate Sensitivity (Recall) and Specificity per class
    cm = confusion_matrix(y_true, y_pred)
    for i, class_name in enumerate(['Normal', 'AFib', 'PVC']):
        tp = cm[i, i]
        fp = cm[:, i].sum() - tp
        fn = cm[i, :].sum() - tp
        tn = cm.sum() - (tp + fp + fn)
        
        sensitivity = tp / (tp + fn) if (tp + fn) > 0 else 0
        specificity = tn / (tn + fp) if (tn + fp) > 0 else 0
        
        print(f"{class_name} - Sensitivity: {sensitivity:.4f}, Specificity: {specificity:.4f}")
