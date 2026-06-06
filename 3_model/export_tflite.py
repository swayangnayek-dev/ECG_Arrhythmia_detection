import os
import subprocess

def export_tflite_to_c(tflite_model_bytes, output_header_path="ecg_model_data.h", model_name="ecg_model_tflite"):
    """
    Saves the TFLite model as a .tflite file, then converts it to a C header array using xxd.
    Note: 'xxd' must be installed on the system.
    """
    tflite_file_path = "temp_model.tflite"
    
    # Save the binary .tflite file
    with open(tflite_file_path, 'wb') as f:
        f.write(tflite_model_bytes)
        
    print(f"Model saved as {tflite_file_path} ({len(tflite_model_bytes)} bytes)")
    
    # Convert to C header using xxd
    print(f"Converting to C header {output_header_path}...")
    try:
        with open(output_header_path, "w") as f:
            # xxd -i <input_file>
            subprocess.run(['xxd', '-i', tflite_file_path], stdout=f, check=True)
        print(f"Successfully generated {output_header_path}")
    except FileNotFoundError:
        print("Error: 'xxd' command not found. Please ensure it is installed and in your PATH.")
        print("Alternative: You can use a Python script to format the bytes as a C array.")
    except subprocess.CalledProcessError as e:
        print(f"Error during xxd conversion: {e}")
        
    # Clean up temp file
    if os.path.exists(tflite_file_path):
        os.remove(tflite_file_path)

def tflite_to_c_array_python(tflite_model_bytes, output_header_path="ecg_model_data.h", array_name="g_ecg_model_data"):
    """
    Pure Python alternative to xxd for generating the C array.
    """
    hex_array = [format(b, '#04x') for b in tflite_model_bytes]
    
    with open(output_header_path, 'w') as f:
        f.write(f"// Auto-generated TFLite model C array\n")
        f.write(f"// Size: {len(tflite_model_bytes)} bytes\n\n")
        f.write(f"const unsigned char {array_name}[] = {{\n")
        
        # Write 12 bytes per line
        for i in range(0, len(hex_array), 12):
            f.write("  " + ", ".join(hex_array[i:i+12]))
            if i + 12 < len(hex_array):
                f.write(",\n")
            else:
                f.write("\n")
                
        f.write("};\n")
        f.write(f"const int {array_name}_len = {len(tflite_model_bytes)};\n")
        
    print(f"Successfully generated {output_header_path} using Python array formatter.")
