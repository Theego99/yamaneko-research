"""
manage_local_batch_simplified.py

Simplified process for managing a local MegaDetector job, including
basic postprocessing steps.

This script can be run from top to bottom in a Python environment.
"""

#Imports and constants

import os
import json
import datetime
import torch
from megadetector.detection.run_detector_batch import load_and_run_detector_batch, write_results_to_file
from megadetector.utils import path_utils
from tqdm import tqdm

# Paths and job configuration
input_base_path = "C:/yamaneko-kenkyu/p_data/20240531"  # Base path to start recursion
output_base = 'C:/yamaneko-kenkyu/p_data'

#Traverse directories and process images
for root, dirs, files in os.walk(input_base_path):
    for directory in dirs:
        directory_path = os.path.join(root, directory)
        # Check if the directory contains any .jpg or .jpeg files
        jpeg_files = path_utils.find_images(directory_path, recursive=False, convert_slashes=True)
        if jpeg_files:
            print(directory_path)
