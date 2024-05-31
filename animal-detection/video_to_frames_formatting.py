"""
manage_video_batch.py

Simplified process to split videos into frames and handle .mov and .avi files.
"""

#%% Imports and constants

import os
from collections import defaultdict
from megadetector.utils import path_utils
from megadetector.detection import video_utils
import datetime

input_folder = r"C:/yamaneko-kenkyu/data/30052024"
frame_folder_base = r'C:/yamaneko-kenkyu/p_data/' + str(datetime.date.today()).replace('-','')

os.makedirs(frame_folder_base, exist_ok=True)

every_n_frames = 20
recursive = True
overwrite = True
parallelization_uses_threads = True
n_threads = 8

def split_videos():
    # Split videos into frames
    frame_filenames_by_video, fs_by_video, video_filenames = \
        video_utils.video_folder_to_frames(input_folder=input_folder,
                                           output_folder_base=frame_folder_base,
                                           recursive=recursive,
                                           overwrite=overwrite,
                                           n_threads=n_threads,
                                           every_n_frames=every_n_frames,
                                           parallelization_uses_threads=parallelization_uses_threads)

def list_videos():
    # List frame files, break into folders
    frame_files = path_utils.find_images(frame_folder_base, True)
    frame_files = [s.replace('\\', '/') for s in frame_files]
    print('Enumerated {} total frames'.format(len(frame_files)))

    # Find unique (relative) folders
    folder_to_frame_files = defaultdict(list)
    for fn in frame_files:
        folder_name = os.path.dirname(fn)
        folder_name = os.path.relpath(folder_name, frame_folder_base)
        folder_to_frame_files[folder_name].append(fn)

    print('Found {} folders for {} files'.format(len(folder_to_frame_files), len(frame_files)))

    # List videos
    video_filenames = video_utils.find_videos(input_folder, recursive=True)
    video_filenames = [os.path.relpath(fn, input_folder) for fn in video_filenames]
    print('Input folder contains {} videos'.format(len(video_filenames)))

    return video_filenames, folder_to_frame_files

def problem_check(video_filenames, folder_to_frame_files):
    # Check for videos that don't have corresponding frame folder
    missing_videos = [fn for fn in video_filenames if fn not in folder_to_frame_files]
    print('{} of {} folders are missing frames entirely'.format(len(missing_videos), len(video_filenames)))

    # Check for videos with very few frames
    min_frames_for_valid_video = 10
    low_frame_videos = [folder_name for folder_name, frame_files in folder_to_frame_files.items()
                        if len(frame_files) < min_frames_for_valid_video]
    print('{} of {} folders have fewer than {} frames'.format(len(low_frame_videos), len(video_filenames), min_frames_for_valid_video))

    # Print the list of problematic videos
    print('Videos that could not be decoded:\n', '\n'.join(missing_videos))
    print('\nVideos with fewer than {} decoded frames:\n'.format(min_frames_for_valid_video), '\n'.join(low_frame_videos))

def main():
    split_videos()
    video_filenames, folder_to_frame_files = list_videos()
    problem_check(video_filenames, folder_to_frame_files)

if __name__ == "__main__":
    main()

# Process images like we would for any other camera trap job

# This section is left for the actual image processing workflow,
# typically using manage_local_batch.py or similar scripts.
