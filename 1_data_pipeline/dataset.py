import numpy as np
import tensorflow as tf
from imblearn.over_sampling import SMOTE
from sklearn.model_selection import train_test_split

def augment_data(segments, labels):
    """
    Data augmentation for ECG segments:
    - Small amplitude scaling
    - Additive Gaussian noise
    """
    augmented_segments = []
    augmented_labels = []
    
    for seg, lbl in zip(segments, labels):
        # Original
        augmented_segments.append(seg)
        augmented_labels.append(lbl)
        
        # Amplitude scaling
        scale = np.random.uniform(0.9, 1.1)
        augmented_segments.append(seg * scale)
        augmented_labels.append(lbl)
        
        # Additive Gaussian noise
        noise = np.random.normal(0, 0.05, len(seg))
        augmented_segments.append(seg + noise)
        augmented_labels.append(lbl)
        
    return np.array(augmented_segments), np.array(augmented_labels)

def create_tf_dataset(segments, labels, batch_size=128, is_training=True):
    """
    Build a tf.data.Dataset with optional SMOTE and Augmentation.
    """
    if is_training:
        # Reshape for SMOTE (expects 2D)
        samples = segments.shape[0]
        timesteps = segments.shape[1]
        X = segments.reshape(samples, -1)
        
        # Apply SMOTE
        smote = SMOTE()
        X_resampled, y_resampled = smote.fit_resample(X, labels)
        
        # Reshape back to 3D for Conv1D (samples, timesteps, 1)
        X_resampled = X_resampled.reshape(-1, timesteps, 1)
        
        # Augmentation
        X_aug, y_aug = augment_data(X_resampled, y_resampled)
        X_final = X_aug
        y_final = y_aug
    else:
        # Validation/Test, no SMOTE or augmentation
        X_final = segments.reshape(-1, segments.shape[1], 1)
        y_final = labels
        
    dataset = tf.data.Dataset.from_tensor_slices((X_final, y_final))
    
    if is_training:
        dataset = dataset.shuffle(buffer_size=1024)
        
    dataset = dataset.batch(batch_size).prefetch(tf.data.AUTOTUNE)
    return dataset

def split_and_create_datasets(segments, labels, batch_size=128):
    """
    Perform an 80/10/10 split and return tf datasets.
    Note: Real implementation should do Patient-Wise split to avoid data leakage.
    This is a simplified standard split.
    """
    X_temp, X_test, y_temp, y_test = train_test_split(segments, labels, test_size=0.1, random_state=42)
    # Remaining 90% into 80% train / 10% val (so 8/9 of temp goes to train)
    X_train, X_val, y_train, y_val = train_test_split(X_temp, y_temp, test_size=(1/9), random_state=42)
    
    train_ds = create_tf_dataset(X_train, y_train, batch_size, is_training=True)
    val_ds = create_tf_dataset(X_val, y_val, batch_size, is_training=False)
    test_ds = create_tf_dataset(X_test, y_test, batch_size, is_training=False)
    
    return train_ds, val_ds, test_ds
