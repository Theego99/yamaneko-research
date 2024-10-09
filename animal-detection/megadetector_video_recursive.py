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
class_names = ['tori', 'honyurui']

# 入力ディレクトリはユーザーが決める
input_folder = r"D:\DCIM/100BMCIM"  # 処理したい動画の回収日パス

# Derive output_base and tracking_file from input_folder
output_base = input_folder+"_processed"
tracking_file = os.path.join(output_base, 'video_confidence_tracking.json')

# 出力ディレクトリを作成
if not os.path.exists(output_base):
    os.makedirs(output_base)

model_file = 'MDV5A'

every_n_frames = 33
recursive = True
overwrite = True
parallelization_uses_threads = True
n_threads = 8
confidence_threshold = 0.3

# データを読み込む
if os.path.exists(tracking_file):
    with open(tracking_file, 'r') as f:
        video_confidence_dict = json.load(f)
else:
    video_confidence_dict = {}

# ディレクトリーが存在したら続けるかどうかを尋ねる
def prompt_overwrite(path):
    while True:
        response = input(f"'{path}' already exists. Do you want to overwrite it? (y/n): ").lower()
        if response in ['y', 'n']:
            return response == 'y'
    return True

#動画をコマに分ける
def split_videos():
    if os.path.exists(tracking_file):
        print(f"Skipping saving video confidence tracking to '{output_base}'")
        return    
    frame_filenames_by_video, fs_by_video, video_filenames = \
        video_utils.video_folder_to_frames(input_folder=input_folder,
                                           output_folder_base=output_base,
                                           recursive=recursive,
                                           overwrite=overwrite,
                                           n_threads=n_threads,
                                           every_n_frames=every_n_frames,
                                           parallelization_uses_threads=parallelization_uses_threads)
    return frame_filenames_by_video, fs_by_video, video_filenames

#コマをフォーマットの通りに保存
def list_videos():
    frame_files = path_utils.find_images(output_base, True)
    frame_files = [s.replace('\\', '/') for s in frame_files]
    print('Enumerated {} total frames'.format(len(frame_files)))

    folder_to_frame_files = defaultdict(list)
    for fn in frame_files:
        folder_name = os.path.dirname(fn)
        folder_name = os.path.relpath(folder_name, output_base)
        folder_to_frame_files[folder_name].append(fn)

    print('Found {} folders for {} files'.format(len(folder_to_frame_files), len(frame_files)))

    video_filenames = video_utils.find_videos(input_folder, recursive=True)
    video_filenames = [os.path.relpath(fn, input_folder) for fn in video_filenames]
    print('Input folder contains {} videos'.format(len(video_filenames)))

    return video_filenames, folder_to_frame_files

#コマに問題あるか確認
def problem_check(video_filenames, folder_to_frame_files):
    missing_videos = [fn for fn in video_filenames if fn not in folder_to_frame_files]
    print('{} of {} folders are missing frames entirely'.format(len(missing_videos), len(video_filenames)))

    min_frames_for_valid_video = 10
    low_frame_videos = [folder_name for folder_name, frame_files in folder_to_frame_files.items()
                        if len(frame_files) < min_frames_for_valid_video]
    print('{} of {} folders have fewer than {} frames'.format(len(low_frame_videos), len(video_filenames), min_frames_for_valid_video))

    print('Videos that could not be decoded:\n', '\n'.join(missing_videos))
    print('\nVideos with fewer than {} decoded frames:\n'.format(min_frames_for_valid_video), '\n'.join(low_frame_videos))

#AIモデルを実行
def run_megadetector(directory_path, every_n_frames):
    output_json = os.path.join(directory_path, 'detections.json')
    # Do not run MegaDetector if detection box file already exists
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

#認識結果を処理
def process_detections(directory_path, results, all_images, every_n_frames):
    output_json = os.path.join(directory_path, 'detections.json')

    # Initialize variables
    max_confidence = 0
    best_frame = None
    best_frame_results = None
    detection_above_threshold = False
    category_one_detected = False  # New variable to track category '1' detections

    for result in results:
        # Update max confidence and best frame
        if 'max_detection_conf' in result and result['max_detection_conf'] > max_confidence:
            max_confidence = result['max_detection_conf']
            best_frame = result['file']
            best_frame_results = result
        
        # Check if any detection exceeds the confidence threshold
        if 'max_detection_conf' in result and result['max_detection_conf'] > confidence_threshold:
            detection_above_threshold = True

        # Check each detection in the result
        for detection in result.get('detections', []):
            # Check if the detection is of category '1' and exceeds the threshold
            if detection['category'] == '1' and detection['conf'] > confidence_threshold:
                category_one_detected = True

    # Update the video confidence dictionary
    video_path = os.path.relpath(directory_path, output_base).replace('\\', '/')
    video_confidence_dict[video_path] = max_confidence

    # Delete frames and folder if no detection exceeds threshold or category is not '1'
    if not detection_above_threshold or not category_one_detected:
        shutil.rmtree(directory_path)
        print(f"Deleted all frames and folder '{directory_path}' because no detections of category '1' exceeded the confidence threshold of {confidence_threshold}")
        return

    # Keep only the frame with the highest confidence score and delete the rest
    if best_frame:
        for image in all_images:
            if os.path.basename(image) != os.path.basename(best_frame):
                os.remove(image)
        print(f"Kept only the frame with the highest confidence: {best_frame}")

        # Write results to file with the best frame's detections only
        best_frame_results['file'] = os.path.basename(best_frame)
        with open(output_json, 'w') as f:
            json.dump([best_frame_results], f, indent=2)
        print(f"Wrote results for the best frame to {output_json}")
    else:
        print("No frames had detections")

#船頭がの動物認識情報をJsonに保存
def save_video_confidence_dict():
    if os.path.exists(tracking_file) and not prompt_overwrite(tracking_file):
        print(f"Skipping saving video confidence tracking to '{tracking_file}'")
        return
    with open(tracking_file, 'w') as f:
        json.dump(video_confidence_dict, f, indent=2)
    print(f"Saved video confidence tracking to {tracking_file}")

#認識できなかった動画のみAIモデルを再実行
def split_videos_with_new_interval(directory_path, new_every_n_frames):
    print(f"Splitting videos with a new frame interval of {new_every_n_frames}")
    video_filenames, fs_by_video = \
        video_utils.video_to_frames(input_video_file=directory_path,
                                    output_folder=directory_path,
                                    overwrite=True,
                                    every_n_frames=new_every_n_frames)

# Crop image based on bounding box
def crop_image_with_bbox(image_path, bbox):
    """
    Crops the image based on the bounding box and returns the cropped image.
    """
    image = cv2.imread(image_path)
    if image is None:
        print(f"Could not load image {image_path}")
        return None

    height, width, _ = image.shape
    x_min, y_min, bbox_width, bbox_height = bbox

    x_min_pixel = int(x_min * width)
    y_min_pixel = int(y_min * height)
    x_max_pixel = int((x_min + bbox_width) * width)
    y_max_pixel = int((y_min + bbox_height) * height)

    cropped_image = image[y_min_pixel:y_max_pixel, x_min_pixel:x_max_pixel]
    return cropped_image

# Run binary classification on the cropped image
def classify_cropped_image(cropped_image):
    """
    Classifies the cropped image using the binary classification model.
    """
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

# Detectionボックスを描画
def draw_detections_on_frame(frame_path):
    """
    Draws detections on the frame and crops the detected regions.
    Classifies each cropped region using the binary classification model.

    Parameters:
    - frame_path: Path to the frame image.
    """
    detections_json = os.path.dirname(frame_path) + '/detections.json'
    with open(detections_json, 'r') as file:
        detections = json.load(file)[0]['detections']

    image = cv2.imread(frame_path)
    if image is None:
        print(f"Could not load image {frame_path}")
        return

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

            cropped_image = crop_image_with_bbox(frame_path, bbox)
            predicted_class, probability = classify_cropped_image(cropped_image)
            if predicted_class:
                probability = float(probability[0])  # Convert NumPy array to float

                #threshold for bird clasification
                if probability <= 0.75:
                    predicted_class = 'bird'
                print(f"Classified as: {predicted_class} with probability: {probability:.5f}")
                
                # Save the cropped image with classification result as file name
                cropped_image_filename = f"{predicted_class}_{probability:.2f}.jpg"
                cropped_image_path = os.path.join(os.path.dirname(frame_path), cropped_image_filename)
                cv2.imwrite(cropped_image_path, cropped_image)
                print(f"Saved cropped image to {cropped_image_path}")

    output_path = frame_path.replace('.jpg', '_detections.jpg')
    cv2.imwrite(output_path, image)
    print(f"Saved image with detections to {output_path}")

def main():
    split_videos()
    video_filenames, folder_to_frame_files = list_videos()
    problem_check(video_filenames, folder_to_frame_files)
    
    for root, dirs, files in os.walk(output_base):
        for directory in dirs:
            directory_path = os.path.join(root, directory)
            print(f"Processing directory: {directory_path}")
            jpeg_files = path_utils.find_images(directory_path, recursive=False, convert_slashes=True)

            if jpeg_files:
                results, all_images = run_megadetector(directory_path, every_n_frames)
                if results and all_images:
                    process_detections(directory_path, results, all_images, every_n_frames)
                    
                    # Check if the directory still exists
                    if os.path.exists(directory_path):
                        jpeg_files = path_utils.find_images(directory_path, recursive=False, convert_slashes=True)
                        if jpeg_files:
                            draw_detections_on_frame(jpeg_files[0])
                        else:
                            print(f"No images found in {directory_path}")
                    else:
                        print(f"Directory {directory_path} has been deleted.")
                else:
                    print(f"Skipping processing for {directory_path} as MegaDetector did not run.")
            else:
                print(f"No images found in {directory_path}")


    save_video_confidence_dict()    

if __name__ == "__main__":
    main()
