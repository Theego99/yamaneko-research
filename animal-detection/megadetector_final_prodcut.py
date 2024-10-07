import os
import cv2
import json
import shutil
import tempfile
from megadetector.detection import video_utils
from megadetector.detection.run_detector_batch import load_detector, process_images

# Input directory specified by the user
input_folder = r"D:\DCIM\100BMCIM"  # Path to the videos to be processed

# Derive output_base and tracking_file from input_folder
output_base = input_folder + "_processed"
tracking_file = os.path.join(output_base, 'video_confidence_tracking.json')

# Create output directory
if not os.path.exists(output_base):
    os.makedirs(output_base)

model_file = 'MDV5A'  # Ensure this points to your actual model file path

every_n_frames = 33
confidence_threshold = 0.3

# Load data
if os.path.exists(tracking_file):
    with open(tracking_file, 'r') as f:
        video_confidence_dict = json.load(f)
else:
    video_confidence_dict = {}

# Load the detector once
detector = load_detector(model_file)
print("動物認識AIの読み込みが完了しました")

# Function to process videos using batch detection
def process_video(video_path):
    cap = cv2.VideoCapture(video_path)
    frame_count = 0
    max_confidence = 0
    best_frame = None
    best_frame_results = None
    category_one_detected = False

    temp_dir = tempfile.mkdtemp()
    frame_files = []
    frame_indices = []

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
        frame_count += 1
        if frame_count % every_n_frames == 15:
            frame_filename = os.path.join(temp_dir, f'frame_{frame_count}.jpg')
            cv2.imwrite(frame_filename, frame)
            frame_files.append(frame_filename)
            frame_indices.append(frame_count)

    cap.release()

    if not frame_files:
        print(f"{video_path}の処理するコマがありません")
        shutil.rmtree(temp_dir)
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

    # Process the results
    for i, result in enumerate(results):
        frame_idx = frame_indices[i]
        frame_filename = frame_files[i]
        frame = cv2.imread(frame_filename)

        # Update max confidence and best frame if necessary
        if 'max_detection_conf' in result and result['max_detection_conf'] > max_confidence:
            max_confidence = result['max_detection_conf']
            best_frame = frame.copy()
            best_frame_results = result

        # Check for detections of category '1' above the confidence threshold
        for detection in result.get('detections', []):
            if detection['category'] == '1' and detection['conf'] > confidence_threshold:
                category_one_detected = True

    # Clean up temporary files
    shutil.rmtree(temp_dir)

    # Update the video confidence dictionary
    video_relpath = os.path.relpath(video_path, input_folder).replace('\\', '/')
    video_confidence_dict[video_relpath] = max_confidence

    # If no relevant detections, do not save anything
    if not category_one_detected:
        print(f"{video_path}に動物が確認されませんでした")
        return

    # Create output directory
    output_dir = os.path.join(output_base, os.path.splitext(video_relpath)[0])
    os.makedirs(output_dir, exist_ok=True)

    # Get the detections from best_frame_results
    detections = best_frame_results.get('detections', [])

    # Find the detection with the highest confidence among category '1' detections
    best_detection = None
    max_confidence_detection = 0

    for detection in detections:
        if detection['category'] == '1' and detection['conf'] > confidence_threshold:
            if detection['conf'] > max_confidence_detection:
                max_confidence_detection = detection['conf']
                best_detection = detection

    if best_detection is not None:
        # Draw detections on best_frame
        output_image_path = os.path.join(output_dir, 'best_frame_detections.jpg')
        draw_detections_on_image(best_frame.copy(), detections, confidence_threshold, output_image_path)

        # Crop the image based on the bounding box of the best detection
        cropped_image = crop_image_with_bbox_image(best_frame, best_detection['bbox'])

        # Save the cropped image
        cropped_image_path = os.path.join(output_dir, 'cropped_image.jpg')
        cv2.imwrite(cropped_image_path, cropped_image)
        print(f"{cropped_image_path}にクロップした画像を保存しました")
    else:
        print("クロップする適切な検出が見つかりませんでした。")

    # Rename the original video file
    video_dir = os.path.dirname(video_path)
    video_name = os.path.basename(video_path)
    new_video_name = "animal_" + video_name
    new_video_path = os.path.join(video_dir, new_video_name)

    # Check if the new video name already exists
    if os.path.exists(new_video_path):
        print(f"ファイル {new_video_path} はすでに存在します。名前を変更できません。")
    else:
        try:
            os.rename(video_path, new_video_path)
            print(f"ファイルを {video_path} から {new_video_path} に名前を変更しました。")
        except Exception as e:
            print(f"ファイルの名前変更中にエラーが発生しました: {e}")

# Function to draw detections on an image
def draw_detections_on_image(image, detections, confidence_threshold, output_path):
    """
    Draws detections on the image and saves it to output_path.
    """
    for detection in detections:
        bbox = detection['bbox']
        confidence = detection['conf']
        if confidence > confidence_threshold:
            height, width, _ = image.shape
            x_min, y_min, bbox_width, bbox_height = bbox
            x_min_pixel = int(x_min * width)
            y_min_pixel = int(y_min * height)
            x_max_pixel = int((x_min + bbox_width) * width)
            y_max_pixel = int((y_min + bbox_height) * height)

            cv2.rectangle(image, (x_min_pixel, y_min_pixel), (x_max_pixel, y_max_pixel), (20, 0, 255), 2)
            label = f'{confidence:.2f}'
            cv2.putText(image, label, (x_min_pixel, y_min_pixel - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 255), 2)

    cv2.imwrite(output_path, image)
    print(f"{output_path}に認識ボックスの描いた画像を保存しました")

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

def save_video_confidence_dict():
    with open(tracking_file, 'w') as f:
        json.dump(video_confidence_dict, f, indent=2)
    print(f"{tracking_file}に正確性トラッキングデータを保存しました")

def main():
    # Get list of video files
    video_filenames = video_utils.find_videos(input_folder, recursive=True)
    video_paths = [os.path.join(input_folder, fn) for fn in video_filenames]

    # Process each video
    for video_path in video_paths:
        print(f"{video_path}を処理中")
        process_video(video_path)

    # Save the video confidence tracking file
    save_video_confidence_dict()

if __name__ == "__main__":
    main()
