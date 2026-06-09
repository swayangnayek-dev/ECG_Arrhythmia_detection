import os
import sys
import numpy as np
import wfdb  # type: ignore
import tensorflow as tf

# Add paths
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '1_data_pipeline'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '2_signal_processing'))

from download_mitbih import download_and_resample  # type: ignore
from preprocess import segment_ecg  # type: ignore
from label_mapping import get_class_for_symbol  # type: ignore
from dataset import split_and_create_datasets  # type: ignore
from architecture import build_ecg_model
from train import train_model, finetune_qat
from quantize import convert_to_tflite_int8, get_representative_dataset_gen
from export_tflite import export_tflite_to_c

def load_and_preprocess_data(data_dir='./data/mitdb', limit_records=None):
    """Loads WFDB records, extracts labels, and segments the ECG."""
    print(f"Loading records from {data_dir}...")
    records = [f.split('.')[0] for f in os.listdir(data_dir) if f.endswith('.dat')]
    
    if limit_records:
        records = records[:limit_records]
        
    all_segments = []
    all_labels = []
    
    for record_name in records:
        record_path = os.path.join(data_dir, record_name)
        try:
            # Read signal and annotations
            record = wfdb.rdrecord(record_path)
            annotation = wfdb.rdann(record_path, 'atr')
            
            # We typically use MLII (Lead II) which is usually channel 0
            # but let's just grab the first channel for simplicity
            signal = record.p_signal[:, 0]
            fs = record.fs
            
            # Convert annotations to sample-wise labels (very simplified)
            # A real implementation maps beats to segments carefully.
            # Here we just create a label array matching signal length.
            sample_labels = np.zeros(len(signal), dtype=int) # Default to Normal
            
            for sym, pos in zip(annotation.symbol, annotation.sample):
                cls = get_class_for_symbol(sym)
                if cls != -1:
                    # Assign label to a small window around the beat
                    start = max(0, pos - int(fs * 0.1))
                    end = min(len(signal), pos + int(fs * 0.1))
                    sample_labels[start:end] = cls
                    
            # Segment the record
            # To speed up training for this demo, we'll only take the first 5 minutes (300 seconds) of each record
            max_samples = 300 * fs
            signal = signal[:max_samples]
            sample_labels = sample_labels[:max_samples]
            
            segments, segment_labels = segment_ecg(signal, sample_labels, fs=fs, window_sec=2.0)
            all_segments.extend(segments)
            all_labels.extend(segment_labels)
            print(f"Processed {record_name}: {len(segments)} segments")
        except Exception as e:
            print(f"Error processing {record_name}: {e}")
            
    return np.array(all_segments), np.array(all_labels)

def main():
    data_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data', 'mitdb'))
    
    # 1. Download
    if not os.path.exists(data_dir):
        download_and_resample(target_dir=data_dir)
        
    # 2. Process (Limit to 5 records for fast generation, user can change later)
    print("Preparing dataset (using a subset of records for speed)...")
    segments, labels = load_and_preprocess_data(data_dir, limit_records=2)
    
    if len(segments) == 0:
        print("No data found! Check download.")
        return
        
    # 3. Create TF Datasets
    # Segments shape is (N, 500)
    train_ds, val_ds, test_ds = split_and_create_datasets(segments, labels, batch_size=32)
    
    # 4. Train Float Model (1 epoch for speed)
    print("Training float model...")
    float_model = train_model(train_ds, val_ds, epochs=1)
    
    # 5. QAT Fine-tuning (1 epoch)
    print("Fine-tuning QAT model...")
    qat_model = finetune_qat(float_model, train_ds, val_ds, epochs=1)
    
    # 6. Quantize
    print("Quantizing to TFLite Int8...")
    rep_gen = get_representative_dataset_gen(train_ds, num_samples=100)
    tflite_model = convert_to_tflite_int8(qat_model, rep_gen)
    
    # 7. Save
    out_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data'))
    os.makedirs(out_dir, exist_ok=True)
    out_file = os.path.join(out_dir, 'ecg_model.tflite')
    
    with open(out_file, 'wb') as f:
        f.write(tflite_model)
        
    print(f"\n✅ Pipeline Complete! TFLite model saved to {out_file}")
    
if __name__ == '__main__':
    main()
