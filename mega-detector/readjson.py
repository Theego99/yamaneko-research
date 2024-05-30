import json
import os
from PIL import Image, ImageDraw
from megadetector.visualization import visualization_utils as vis_utils

# Define the folder containing images
image_folder = os.path.expanduser("C:\dataset\yamaneko")

# Load the results from the output JSON file
with open(os.path.expanduser('C:\dataset\megadetector_output_test.json'), 'r') as f:
    results = json.load(f)

# Function to draw detections on an image
def draw_detections(image_path, detections, output_path):
    image = Image.open(image_path).convert("RGB")
    draw = ImageDraw.Draw(image)
    for detection in detections:
        bbox = detection['bbox']
        category = detection['category']
        conf = detection['conf']
        
        # Convert bbox to pixel coordinates
        width, height = image.size
        left = bbox[0] * width
        top = bbox[1] * height
        right = left + bbox[2] * width
        bottom = top + bbox[3] * height
        
        # Draw the bounding box
        draw.rectangle([left, top, right, bottom], outline='red', width=2)
        draw.text((left, top), f"{results['detection_categories'][category]}: {conf:.2f}", fill='red')

    # Save the image with detections
    image.save(output_path)

# Create a folder to save the output images
output_folder = os.path.expanduser('C:\dataset\megadetector_output_images')
os.makedirs(output_folder, exist_ok=True)

# Process each image in the results
for image_info in results['images']:
    image_file = image_info['file']
    detections = image_info['detections']
    input_path = os.path.join(image_folder, image_file)
    output_path = os.path.join(output_folder, image_file)
    draw_detections(input_path, detections, output_path)

print(f"Annotated images saved to {output_folder}")
