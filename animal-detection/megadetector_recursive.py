import os
import json
import torch
from megadetector.detection.run_detector_batch import load_and_run_detector_batch
from megadetector.utils import path_utils

# Paths and job configuration
input_base_path = "C:/yamaneko-kenkyu/p_data/20240531"  # Base path to start recursion
output_base = 'C:/yamaneko-kenkyu/p_data'
model_file = 'MDV5A'

#%% Function to write results to file with relative paths
def write_results_to_file_with_filenames(results, output_json):
    for result in results:
        # Extract only the filename from the path
        result['file'] = os.path.basename(result['file'])
    
    with open(output_json, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"Wrote results to {output_json}")

#%% Function to process images in a directory
def process_images_in_directory(directory_path):
    print(f"Enumerating image files in {directory_path}")
    all_images = sorted(path_utils.find_images(directory_path, recursive=False, convert_slashes=True))
    print(f"Enumerated {len(all_images)} image files in {directory_path}")

    if not all_images:
        return

    # Output paths
    output_json = os.path.join(directory_path, 'detections.json')

    # Run MegaDetector
    use_gpu = torch.cuda.is_available()
    gpu_device = 0 if use_gpu else None
    print(f"Using GPU: {use_gpu}")

    # Run detector
    print("Running MegaDetector...")
    results = load_and_run_detector_batch(model_file=model_file,
                                          image_file_names=all_images,
                                          checkpoint_path=None,
                                          confidence_threshold=None,
                                          checkpoint_frequency=None,
                                          results=None,
                                          n_cores=1,
                                          use_image_queue=False,
                                          quiet=True,
                                          image_size=None)

    # Write results to file with filenames only
    write_results_to_file_with_filenames(results, output_json)
    print(f"Wrote results to {output_json}")

#%% Traverse directories and process images
for root, dirs, files in os.walk(input_base_path):
    for directory in dirs:
        directory_path = os.path.join(root, directory)
        # Check if the directory contains any images
        jpeg_files = path_utils.find_images(directory_path, recursive=False, convert_slashes=True)
        if jpeg_files:
            process_images_in_directory(directory_path)
