import os
from collections import defaultdict
import shutil
import cv2
import json
import torch
from megadetector.utils import path_utils
from megadetector.detection import video_utils
import json
from megadetector.detection.run_detector_batch import load_and_run_detector_batch
import numpy as np
import tensorflow as tf

# Load the binary classification model
classification_model = tf.keras.models.load_model('../animal-clasification/animal_classifier_binary_model.h5')

# Define the class names for binary classification
class_names = ['bird', 'other']

# Input directory for the files to be processed
input_folder = r"C:/yamaneko-kenkyu/data"

# Derive output_base and tracking_file from input_folder
output_base = input_folder.replace("data", "p_data")
tracking_file = os.path.join(output_base, 'video_confidence_tracking.json')

# Create the output directory if it doesn't exist
if not os.path.exists(output_base):
    os.makedirs(output_base)

model_file = 'MDV5A'

every_n_frames = 20
recursive = True
overwrite = True
parallelization_uses_threads = True
n_threads = 8
confidence_threshold = 0.8

# Load existing tracking data or create a new one
if os.path.exists(tracking_file):
    with open(tracking_file, 'r') as f:
        video_confidence_dict = json.load(f)
else:
    video_confidence_dict = {}

# Check if we should overwrite existing directories or files
def prompt_overwrite(path):
    while True:
        response = input(f"'{path}' already exists. Do you want to overwrite it? (y/n): ").lower()
        if response in ['y', 'n']:
            return response == 'y'

# Recursively search for images and create folders for them
def process_images(input_folder):
    for root, dirs, files in os.walk(input_folder):
        for file in files:
            if file.lower().endswith(('.png', '.jpg', '.jpeg')):
                image_path = os.path.join(root, file)
                image_folder = os.path.join(output_base, os.path.splitext(file)[0])
                if not os.path.exists(image_folder):
                    os.makedirs(image_folder)
                
                # Move the image to the new folder
                new_image_path = os.path.join(image_folder, file)
                shutil.copy2(image_path, new_image_path)
                
                # Run MegaDetector on the image
                results, all_images = run_megadetector(image_folder, every_n_frames)
                if results and all_images:
                    process_detections(image_folder, results, all_images, every_n_frames)
                else:
                    print(f"Skipping processing for {image_folder} as MegaDetector did not run.")

# Run MegaDetector on the image directory
def run_megadetector(directory_path, every_n_frames):
    output_json = os.path.join(directory_path, 'detections.json')
    if os.path.exists(output_json) and not prompt_overwrite(output_json):
        print(f"Skipping writing results to '{output_json}'")
        return None, None
    
    print(f"Enumerating image files in {directory_path}")
    all_images = sorted(path_utils.find_images(directory_path, recursive=False, convert_slashes=True))
    print(f"Enumerated {len(all_images)} image files in {directory_path}")

    if not all_images:
        return None, None

    use_gpu = torch.cuda.is_available()
    gpu_device = 0 if use_gpu else None
    print(f"Using GPU: {use_gpu}")

    print("Running MegaDetector...")
    results = load_and_run_detector_batch(model_file=model_file,
                                          image_file_names=all_images,
                                          checkpoint_path=None,
                                          confidence_threshold=confidence_threshold,
                                          checkpoint_frequency=None,
                                          results=None,
                                          n_cores=1,
                                          use_image_queue=False,
                                          quiet=True,
                                          image_size=None)

    # Save the detection results to a JSON file
    with open(output_json, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"Wrote results to {output_json}")

    return results, all_images

# Process detections and run classification on the detected animals
def process_detections(directory_path, results, all_images, every_n_frames):
    output_json = os.path.join(directory_path, 'detections.json')
    
    detection_above_threshold = False

    for result in results:
        if 'max_detection_conf' in result and result['max_detection_conf'] > confidence_threshold:
            detection_above_threshold = True
            break

    if not detection_above_threshold:
        shutil.rmtree(directory_path)
        print(f"Deleted folder '{directory_path}' as no detections exceeded the confidence threshold.")
        return

    # Classify detected animals if detections exceed the threshold
    for image in all_images:
        draw_detections_on_frame(image)

# Draw detections on the frame and run classification
def draw_detections_on_frame(frame_path):
    detections_json = os.path.dirname(frame_path) + '/detections.json'
    with open(detections_json, 'r') as file:
        detections = json.load(file)[0]['detections']

    for detection in detections:
        bbox = detection['bbox']
        confidence = detection['conf']
        if confidence > confidence_threshold:
            cropped_image = crop_image_with_bbox(frame_path, bbox)
            predicted_class, probability = classify_cropped_image(cropped_image)
            if predicted_class:
                print(f"Classified as: {predicted_class} with probability: {probability:.5f}")

# Run binary classification on the cropped image
def classify_cropped_image(cropped_image):
    if cropped_image is None:
        return None, None

    img = cv2.cvtColor(cropped_image, cv2.COLOR_BGR2GRAY)
    img = cv2.resize(img, (150, 150))
    img = img.astype('float32') / 255.0
    img = np.expand_dims(img, axis=-1)
    img = np.expand_dims(img, axis=0)

    predictions = classification_model.predict(img)
    predicted_class = 1 if predictions[0] > 0.5 else 0
    return class_names[predicted_class], predictions[0]

# Crop image based on bounding box
def crop_image_with_bbox(image_path, bbox):
    image = cv2.imread(image_path)
    if image is None:
        return None

    height, width, _ = image.shape
    x_min, y_min, bbox_width, bbox_height = bbox

    x_min_pixel = int(x_min * width)
    y_min_pixel = int(y_min * height)
    x_max_pixel = int((x_min + bbox_width) * width)
    y_max_pixel = int((y_min + bbox_height) * height)

    cropped_image = image[y_min_pixel:y_max_pixel, x_min_pixel:x_max_pixel]
    return cropped_image

def main():
    process_images(input_folder)
    save_video_confidence_dict()

if __name__ == "__main__":
    main()
