import os
from megadetector.detection.run_detector_batch import load_and_run_detector_batch, write_results_to_file
from megadetector.utils import path_utils

# Define the folder containing images and the output file
image_folder = os.path.expanduser("C:\dataset\yamaneko")
output_file = os.path.expanduser('C:\dataset\megadetector_output_test.json')

# Recursively find all images in the folder
image_file_names = path_utils.find_images(image_folder, recursive=True)

# Load the detector model (this will automatically download MDv5a if not already downloaded)
model_filename = 'MDV5A'  # or specify the path to your local model file if you have one
results = load_and_run_detector_batch(model_filename, image_file_names)

# Write results to the output file
write_results_to_file(results, output_file, relative_path_base=image_folder, detector_file=model_filename)

print(f'Results written to {output_file}')
