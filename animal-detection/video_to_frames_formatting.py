import os
from collections import defaultdict
import datetime
import json
import torch
from megadetector.utils import path_utils
from megadetector.detection import video_utils
from megadetector.detection.run_detector_batch import load_and_run_detector_batch

input_folder = r"C:/yamaneko-kenkyu/data/30052024" #処理したい動画の回収日パス
output_base = r'C:/yamaneko-kenkyu/p_data/' + str(datetime.date.today()).replace('-','')
model_file = 'MDV5A'
tracking_file = r'C:/yamaneko-kenkyu/p_data/video_confidence_tracking.json'

os.makedirs(output_base, exist_ok=True)

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

def write_results_to_file_with_filenames(results, output_json):
    for result in results:
        result['file'] = os.path.basename(result['file'])
    
    with open(output_json, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"Wrote results to {output_json}")

def process_images_in_directory(directory_path):
    print(f"Enumerating image files in {directory_path}")
    all_images = sorted(path_utils.find_images(directory_path, recursive=False, convert_slashes=True))
    print(f"Enumerated {len(all_images)} image files in {directory_path}")

    if not all_images:
        return

    output_json = os.path.join(directory_path, 'detections.json')

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

    write_results_to_file_with_filenames(results, output_json)
    print(f"Wrote results to {output_json}")

    # Track highest confidence score for each video
    max_confidence = max((result.get('max_detection_conf', 0) for result in results), default=0)
    video_path = os.path.relpath(directory_path, output_base)
    video_confidence_dict[video_path] = max_confidence

def save_video_confidence_dict():
    with open(tracking_file, 'w') as f:
        json.dump(video_confidence_dict, f, indent=2)
    print(f"Saved video confidence tracking to {tracking_file}")

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
                process_images_in_directory(directory_path)
            else:
                print(f"No images found in {directory_path}")

    save_video_confidence_dict()

if __name__ == "__main__":
    main()
