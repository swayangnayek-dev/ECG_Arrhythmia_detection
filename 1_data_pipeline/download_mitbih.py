import os
import wfdb
from scipy.signal import resample
import numpy as np

def download_and_resample(target_dir='./data/mitdb', target_fs=250):
    """
    Downloads the MIT-BIH Arrhythmia Database and resamples records to target_fs.
    """
    os.makedirs(target_dir, exist_ok=True)
    
    print("Downloading MIT-BIH database...")
    # dl_database downloads all files from the PhysioNet mitdb database
    wfdb.dl_database('mitdb', dl_dir=target_dir)
    print("Download complete.")
    
    # Optional: we could perform resampling here and save as new files, 
    # but typically it's better to resample dynamically during dataset generation 
    # to avoid duplicating huge data. For this script, we'll just download it.
    
if __name__ == "__main__":
    download_and_resample()
