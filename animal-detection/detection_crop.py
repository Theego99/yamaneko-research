import os
import json
from PIL import Image

# Define the base path for the input images and JSON file
input_base_path = r"C:\yamaneko-kenkyu\p_data\20240531\34.6245436-129.3455148\tsushimaten.mp4"
json_file_path = os.path.join(input_base_path, "detections.json")

# Load the JSON file
with open(json_file_path, 'r') as f:
    detections = json.load(f)

# Process each image and its detections
for detection in detections:
    image_file = detection['file']
    image_path = os.path.join(input_base_path, image_file)

    # Load the image
    with Image.open(image_path) as img:
        img_width, img_height = img.size

        # Create the detections directory if it doesn't exist
        detections_dir = os.path.join(input_base_path, "detections")
        os.makedirs(detections_dir, exist_ok=True)

        # Process each bounding box in the detections
        for idx, det in enumerate(detection['detections']):
            bbox = det['bbox']
            category = det['category']
            conf = det['conf']

            # Only proceed if the confidence is greater than 0.15
            if conf > 0.15:
                # Convert bbox from relative to absolute coordinates
                x, y, w, h = bbox
                left = int(x * img_width)
                top = int(y * img_height)
                right = int((x + w) * img_width)
                bottom = int((y + h) * img_height)

                # Crop the image
                cropped_img = img.crop((left, top, right, bottom))

                # Define the output path for the cropped image
                cropped_img_filename = f"{os.path.splitext(image_file)[0]}_det{idx}_cat{category}_conf{conf:.2f}.jpg"
                cropped_img_path = os.path.join(detections_dir, cropped_img_filename)

                # Save the cropped image
                cropped_img.save(cropped_img_path)
                print(f"Saved cropped image to {cropped_img_path}")
