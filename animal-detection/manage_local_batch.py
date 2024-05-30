"""
manage_local_batch_simplified.py

Simplified process for managing a local MegaDetector job, including
basic postprocessing steps.

This script can be run from top to bottom in a Python environment.
"""

#%% Imports and constants

import os
import json
import datetime
import torch
from megadetector.detection.run_detector_batch import load_and_run_detector_batch, write_results_to_file
from megadetector.utils import path_utils
from tqdm import tqdm

# Paths and job configuration
video_name="karasu.mp4"
input_path = r"C:\yamaneko-kenkyu\animal-detection\video-processed/"+ video_name
output_base = 'C:/yamaneko-kenkyu/animal-detection/postprocessing'
organization_name_short = 'yamanekoinasaku'
job_date = str(datetime.date.today())
model_file = 'MDV5A'

# Output paths
job_name = f"{organization_name_short}-{job_date}-{video_name}-v5a.0.0"
output_folder = os.path.join(output_base, job_name)
os.makedirs(output_folder, exist_ok=True)
output_json = os.path.join(output_folder, 'detections.json')

#%% Enumerate image files
print(f"Enumerating image files in {input_path}")
all_images = sorted(path_utils.find_images(input_path, recursive=True, convert_slashes=True))
print(f"Enumerated {len(all_images)} image files in {input_path}")

#%% Run MegaDetector
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

# Write results to file
write_results_to_file(results, output_json, model_file)
print(f"Wrote results to {output_json}")

#%% Simple Post-processing: Generate HTML Preview (optional)

from megadetector.postprocessing.postprocess_batch_results import PostProcessingOptions, process_batch_results

# Post-processing options
options = PostProcessingOptions()
options.image_base_dir = os.path.dirname(input_path) 
options.include_almost_detections = True
options.num_images_to_sample = 500
options.confidence_threshold = 0.2
options.almost_detection_confidence_threshold = options.confidence_threshold - 0.05
options.output_dir = os.path.join(output_folder, 'preview')
options.md_results_file = output_json  # Set the path to the detections.json file

# Process results
print("Post-processing results...")
ppresults = process_batch_results(options)
html_output_file = ppresults.output_html_file

print(f"Generated HTML preview at {html_output_file}")

# Open the HTML preview (optional)
path_utils.open_file(html_output_file, attempt_to_open_in_wsl_host=True, browser_name='chrome')
