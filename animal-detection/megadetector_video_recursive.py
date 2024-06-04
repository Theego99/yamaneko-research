import os
from collections import defaultdict
import shutil
import cv2
import json
import torch
from megadetector.utils import path_utils
from megadetector.detection import video_utils
from megadetector.detection.run_detector_batch import load_and_run_detector_batch

# User sets the input_folder
input_folder = r"C:/yamaneko-kenkyu/data/30052024"  # 処理したい動画の回収日パス

# Derive output_base and tracking_file from input_folder
output_base = input_folder.replace("data", "p_data")
tracking_file = os.path.join(output_base, 'video_confidence_tracking.json')

# Create the output directory if it does not exist
if not os.path.exists(output_base):
    os.makedirs(output_base)

model_file = 'MDV5A'

every_n_frames = 20
recursive = True
overwrite = True
parallelization_uses_threads = True
n_threads = 8

# Load existing tracking data if it exists
if os.path.exists(tracking_file):
    with open(tracking_file, 'r') as f:
        video_confidence_dict = json.load(f)
else:
    video_confidence_dict = {}

# Prompt if a file or directory already exists
def prompt_overwrite(path):
    while True:
        response = input(f"'{path}' already exists. Do you want to overwrite it? (y/n): ").lower()
        if response in ['y', 'n']:
            return response == 'y'

def split_videos():    
    frame_filenames_by_video, fs_by_video, video_filenames = \
        video_utils.video_folder_to_frames(input_folder=input_folder,
                                           output_folder_base=output_base,
                                           recursive=recursive,
                                           overwrite=overwrite,
                                           n_threads=n_threads,
                                           every_n_frames=every_n_frames,
                                           parallelization_uses_threads=parallelization_uses_threads)
    return frame_filenames_by_video, fs_by_video, video_filenames

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

def problem_check(video_filenames, folder_to_frame_files):
    missing_videos = [fn for fn in video_filenames if fn not in folder_to_frame_files]
    print('{} of {} folders are missing frames entirely'.format(len(missing_videos), len(video_filenames)))

    min_frames_for_valid_video = 10
    low_frame_videos = [folder_name for folder_name, frame_files in folder_to_frame_files.items()
                        if len(frame_files) < min_frames_for_valid_video]
    print('{} of {} folders have fewer than {} frames'.format(len(low_frame_videos), len(video_filenames), min_frames_for_valid_video))

    print('Videos that could not be decoded:\n', '\n'.join(missing_videos))
    print('\nVideos with fewer than {} decoded frames:\n'.format(min_frames_for_valid_video), '\n'.join(low_frame_videos))

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
                                          confidence_threshold=None,
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

def process_detections(directory_path, results, all_images, every_n_frames):
    output_json = os.path.join(directory_path, 'detections.json')
    confidence_threshold = 0.7
    min_frames_interval = 3  # Minimum frame interval to prevent infinite recursion

    # Track highest confidence score and check if any detection exceeds 0.15
    max_confidence = 0
    best_frame = None
    best_frame_results = None
    detection_above_threshold = False

    for result in results:
        if 'max_detection_conf' in result and result['max_detection_conf'] > max_confidence:
            max_confidence = result['max_detection_conf']
            best_frame = result['file']
            best_frame_results = result
        if 'max_detection_conf' in result and result['max_detection_conf'] > confidence_threshold:
            detection_above_threshold = True

    video_path = os.path.relpath(directory_path, output_base).replace('\\', '/')
    video_confidence_dict[video_path] = max_confidence

    # If no detection exceeds the threshold, triple the frames and run again
    if not detection_above_threshold and every_n_frames > min_frames_interval:
        new_every_n_frames = every_n_frames // 3
        print(f"Tripling frames and re-running detector for {directory_path} with new interval: {new_every_n_frames}")
        split_videos_with_new_interval(directory_path.replace('p_data','data'), new_every_n_frames)
        results, all_images = run_megadetector(directory_path, new_every_n_frames)
        if results:
            process_detections(directory_path, results, all_images, new_every_n_frames)
        return

    # Delete all frames and the folder if no detection exceeds the threshold
    if not detection_above_threshold:
        shutil.rmtree(directory_path)
        print(f"Deleted all frames and folder '{directory_path}' as no detections exceeded the confidence threshold of {confidence_threshold}")
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

def save_video_confidence_dict():
    if os.path.exists(tracking_file) and not prompt_overwrite(tracking_file):
        print(f"Skipping saving video confidence tracking to '{tracking_file}'")
        return
    with open(tracking_file, 'w') as f:
        json.dump(video_confidence_dict, f, indent=2)
    print(f"Saved video confidence tracking to {tracking_file}")

def split_videos_with_new_interval(directory_path, new_every_n_frames):
    print(f"Splitting videos with a new frame interval of {new_every_n_frames}")
    video_filenames,fs_by_video = \
        video_utils.video_to_frames(input_video_file=directory_path,
                                           output_folder=directory_path.replace('data','p_data'),
                                           overwrite=True,
                                           every_n_frames=new_every_n_frames)

def draw_detections_on_frame(frame_path, detections):
    """
    Draws detections on the frame.

    Parameters:
    - frame_path: Path to the frame image.
    - detections: List of detections to be drawn, where each detection is a dictionary
                  containing 'bbox' (bounding box) and 'confidence' (confidence score).
                  The 'bbox' should be in the format [x_min, y_min, width, height].

        # Example usage
    frame_path = "path/to/frame.jpg"
    detections = [
        {'bbox': [50, 50, 100, 150], 'confidence': 0.95},
        {'bbox': [200, 200, 120, 180], 'confidence': 0.85}
    ]

    draw_detections_on_frame(frame_path, detections)

    """
    # Load the image
    image = cv2.imread(frame_path)
    
    if image is None:
        print(f"Could not load image {frame_path}")
        return

    for detection in detections:
        bbox = detection['bbox']
        confidence = detection['confidence']
        
        # Extract the coordinates
        x_min, y_min, width, height = bbox
        x_max = x_min + width
        y_max = y_min + height

        # Draw the bounding box
        cv2.rectangle(image, (int(x_min), int(y_min)), (int(x_max), int(y_max)), (0, 255, 0), 2)
        
        # Put the confidence score
        label = f'{confidence:.2f}'
        cv2.putText(image, label, (int(x_min), int(y_min) - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)

    # Save the image with detections
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
                else:
                    print(f"Skipping processing for {directory_path} as MegaDetector did not run.")
            else:
                print(f"No images found in {directory_path}")

    save_video_confidence_dict()

if __name__ == "__main__":
    main()

