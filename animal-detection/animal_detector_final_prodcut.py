import os
import cv2
import json
import shutil
import tempfile
import video_utils
from run_detector_batch import load_detector, process_images

def get_user_input(prompt, default=None, input_type=str, condition=lambda x: True, error_message="Invalid input."):
    """
    Helper function to get validated user input.
    """
    while True:
        user_input = input(prompt)
        if not user_input and default is not None:
            return default
        try:
            value = input_type(user_input)
            if condition(value):
                return value
            else:
                print(error_message)
        except ValueError:
            print(error_message)

# Function to draw detections on an image
def draw_detections_on_image(image, detections, confidence_threshold, output_path):
    """
    Draws detections on the image and saves it to output_path.
    """
    height, width, _ = image.shape

    for detection in detections:
        bbox = detection['bbox']
        confidence = detection['conf']
        if confidence > confidence_threshold:
            x_min, y_min, bbox_width, bbox_height = bbox
            x_min_pixel = int(x_min * width)
            y_min_pixel = int(y_min * height)
            x_max_pixel = int((x_min + bbox_width) * width)
            y_max_pixel = int((y_min + bbox_height) * height)

            cv2.rectangle(image, (x_min_pixel, y_min_pixel), (x_max_pixel, y_max_pixel), (20, 0, 255), 2)
            label = f'{confidence:.2f}'
            cv2.putText(image, label, (x_min_pixel, y_min_pixel - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 255), 2)

    cv2.imwrite(output_path, image)
    print(f"Saved detection boxes image to {output_path}")

# Crop image based on bounding box
def crop_image_with_bbox_image(image, bbox):
    """
    Crops the image based on the bounding box and returns the cropped image.
    """
    height, width, _ = image.shape
    x_min, y_min, bbox_width, bbox_height = bbox

    x_min_pixel = int(x_min * width)
    y_min_pixel = int(y_min * height)
    x_max_pixel = int((x_min + bbox_width) * width)
    y_max_pixel = int((y_min + bbox_height) * height)

    # Ensure the coordinates are within the image bounds
    x_min_pixel = max(0, x_min_pixel)
    y_min_pixel = max(0, y_min_pixel)
    x_max_pixel = min(width, x_max_pixel)
    y_max_pixel = min(height, y_max_pixel)

    cropped_image = image[y_min_pixel:y_max_pixel, x_min_pixel:x_max_pixel]
    return cropped_image

def main():
    # User Prompts
    print("=== Video Detection and Management Script ===\n")

    input_folder = input("Enter the input directory containing videos (default: D:\\DCIM\\test): ").strip()
    if not input_folder:
        input_folder = r"D:\DCIM\test"

    while not os.path.isdir(input_folder):
        print("The specified directory does not exist. Please try again.")
        input_folder = input("Enter the input directory containing videos: ").strip()

    # Get user-defined parameters
    every_n_frames = get_user_input(
        prompt="Enter the frame interval (every_n_frames, default: 33): ",
        default=33,
        input_type=int,
        condition=lambda x: x > 0,
        error_message="Please enter a positive integer."
    )

    confidence_threshold = get_user_input(
        prompt="Enter the confidence threshold (0.0 to 1.0, default: 0.20): ",
        default=0.20,
        input_type=float,
        condition=lambda x: 0.0 <= x <= 1.0,
        error_message="Please enter a float between 0.0 and 1.0."
    )

    # Prompt to create detection_data folder
    create_detection_data = get_user_input(
        prompt="Do you want to create the 'detection_data' folder? (y/n, default: y): ",
        default='y',
        input_type=str,
        condition=lambda x: x.lower() in ['y', 'n', 'yes', 'no'],
        error_message="Please enter 'y' or 'n'."
    ).lower() in ['y', 'yes']

    # Prompt to delete videos without detections
    delete_no_detection = get_user_input(
        prompt="Do you want to delete videos that have no detections? (y/n, default: n): ",
        default='n',
        input_type=str,
        condition=lambda x: x.lower() in ['y', 'n', 'yes', 'no'],
        error_message="Please enter 'y' or 'n'."
    ).lower() in ['y', 'yes']

    if create_detection_data:
        output_base = os.path.join(input_folder, "detection_data")
        tracking_file = os.path.join(output_base, 'video_confidence_tracking.json')

        # Create output directory
        os.makedirs(output_base, exist_ok=True)
        print(f"Created/Verified output directory at {output_base}")

    model_file = r'C:\yamaneko-kenkyu\animal-detection\md_v5b.0.0.pt'  # Ensure this points to your actual model file path

    # Load data
    if create_detection_data and os.path.exists(tracking_file):
        with open(tracking_file, 'r') as f:
            video_confidence_dict = json.load(f)
    else:
        video_confidence_dict = {}

    # Load the detector once
    detector = load_detector(model_file)
    print("動物認識AIの読み込みが完了しました")

    def process_video(video_path, create_output, delete_if_no_detection):
        cap = cv2.VideoCapture(video_path)
        frame_count = 0
        max_confidence_detection = 0
        best_frame = None
        best_detection = None
        best_frame_detections = []
        detection_in_upper_small = False  # Flag for 'tori' condition

        temp_dir = tempfile.mkdtemp()
        frame_files = []
        frame_indices = []

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            frame_count += 1
            if frame_count % every_n_frames == int(every_n_frames / 2):
                frame_filename = os.path.join(temp_dir, f'frame_{frame_count}.jpg')
                cv2.imwrite(frame_filename, frame)
                frame_files.append(frame_filename)
                frame_indices.append(frame_count)

        cap.release()

        if not frame_files:
            print(f"No frames to process in {video_path}")
            shutil.rmtree(temp_dir)
            if delete_if_no_detection:
                try:
                    os.remove(video_path)
                    print(f"Deleted video without detections: {video_path}")
                except Exception as e:
                    print(f"Error deleting {video_path}: {e}")
            return

        # Process frames in batch using process_images
        results = process_images(
            im_files=frame_files,
            detector=detector,
            confidence_threshold=0.0,
            use_image_queue=False,
            quiet=True,
            image_size=None,
            checkpoint_queue=None,
            include_image_size=False,
            include_image_timestamp=False,
            include_exif_data=False
        )

        for i, result in enumerate(results):
            frame_idx = frame_indices[i]
            frame_filename = frame_files[i]
            frame = cv2.imread(frame_filename)

            if frame is None:
                print(f"Could not read frame {frame_filename}")
                continue

            detections = result.get('detections', [])
            frame_valid_detections = []

            for detection in detections:
                if detection['category'] == '1' and detection['conf'] > confidence_threshold:
                    height, width, _ = frame.shape
                    x_min, y_min, bbox_width, bbox_height = detection['bbox']
                    x_min_pixel = int(x_min * width)
                    y_min_pixel = int(y_min * height)
                    x_max_pixel = int((x_min + bbox_width) * width)
                    y_max_pixel = int((y_min + bbox_height) * height)

                    bbox_width_pixels = x_max_pixel - x_min_pixel
                    bbox_height_pixels = y_max_pixel - y_min_pixel

                    # Check for 'tori' condition
                    if (y_max_pixel <= height / 2 and bbox_width_pixels + bbox_height_pixels < 180) or (bbox_width_pixels < 60 and bbox_height_pixels < 60):
                        detection_in_upper_small = True

                    frame_valid_detections.append(detection)

                    # Update max confidence and best detection
                    if detection['conf'] > max_confidence_detection:
                        max_confidence_detection = detection['conf']
                        best_detection = detection
                        best_frame = frame.copy()
                        best_frame_detections = frame_valid_detections.copy()

        if best_detection is None:
            print(f"No detections found in {video_path}")
            shutil.rmtree(temp_dir)
            if delete_if_no_detection:
                try:
                    os.remove(video_path)
                    print(f"Deleted video without detections: {video_path}")
                except Exception as e:
                    print(f"Error deleting {video_path}: {e}")
            return

        # Update tracking data
        video_confidence_dict[video_path] = max_confidence_detection

        # Determine prefix based on detection condition
        if detection_in_upper_small:
            prefix = "tori_"
        else:
            prefix = "nekokamo_"

        # Rename the original video file
        video_dir = os.path.dirname(video_path)
        video_name = os.path.basename(video_path)
        new_video_name = prefix + video_name
        new_video_path = os.path.join(video_dir, new_video_name)

        # Check if the new video name already exists
        if os.path.exists(new_video_path):
            print(f"File {new_video_path} already exists. Cannot rename {video_path}.")
        else:
            try:
                os.rename(video_path, new_video_path)
                print(f"Renamed {video_path} to {new_video_path}.")
            except Exception as e:
                print(f"Error renaming {video_path}: {e}")

        if create_output:
            # Create output directory
            output_folder_name = prefix + os.path.splitext(video_name)[0]
            output_dir = os.path.join(output_base, output_folder_name)
            os.makedirs(output_dir, exist_ok=True)

            # Draw detections on best_frame
            output_image_path = os.path.join(output_dir, 'best_frame_detections.jpg')
            draw_detections_on_image(best_frame.copy(), best_frame_detections, confidence_threshold, output_image_path)

            # Crop the image based on the bounding box of the best detection
            cropped_image = crop_image_with_bbox_image(best_frame, best_detection['bbox'])

            # Save the cropped image
            cropped_image_path = os.path.join(output_dir, 'cropped_image.jpg')
            cv2.imwrite(cropped_image_path, cropped_image)
            print(f"Saved cropped image to {cropped_image_path}")

        # Clean up temporary files
        shutil.rmtree(temp_dir)

    def save_video_confidence_dict():
        if create_detection_data:
            with open(tracking_file, 'w') as f:
                json.dump(video_confidence_dict, f, indent=2)
            print(f"Saved video confidence tracking data to {tracking_file}")

    # Load video filenames
    video_filenames = video_utils.find_videos(input_folder, recursive=True)
    video_paths = [os.path.join(input_folder, fn) for fn in video_filenames]

    if not video_paths:
        print("No video files found in the specified directory.")
        return

    print(f"\nFound {len(video_paths)} video(s) to process.\n")

    # Process each video
    for video_path in video_paths:
        print(f"Processing {video_path}...")
        process_video(
            video_path=video_path,
            create_output=create_detection_data,
            delete_if_no_detection=delete_no_detection
        )
        print("-" * 50)

    # Save the video confidence tracking file
    save_video_confidence_dict()
    print("\n=== Processing Completed ===")

if __name__ == "__main__":
    main()
