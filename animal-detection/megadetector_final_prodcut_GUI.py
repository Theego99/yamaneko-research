import sys
import os
import cv2
import json
import shutil
import tempfile
from PyQt5.QtWidgets import (QApplication, QWidget, QMainWindow, QFileDialog, QLabel, QLineEdit,
                             QPushButton, QVBoxLayout, QHBoxLayout, QSpinBox, QDoubleSpinBox, QCheckBox,
                             QTextEdit, QProgressBar)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from megadetector.detection import video_utils
from megadetector.detection.run_detector_batch import load_detector, process_images

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

class VideoDetectionApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Video Detection and Management")
        self.initUI()

    def initUI(self):
        # Create widgets
        self.input_dir_label = QLabel("Input Directory:")
        self.input_dir_line_edit = QLineEdit()
        self.browse_button = QPushButton("Browse")
        self.browse_button.clicked.connect(self.browse_input_directory)

        self.frame_interval_label = QLabel("Frame Interval (every_n_frames):")
        self.frame_interval_spinbox = QSpinBox()
        self.frame_interval_spinbox.setRange(1, 1000)
        self.frame_interval_spinbox.setValue(33)

        self.confidence_threshold_label = QLabel("Confidence Threshold:")
        self.confidence_threshold_spinbox = QDoubleSpinBox()
        self.confidence_threshold_spinbox.setRange(0.0, 1.0)
        self.confidence_threshold_spinbox.setSingleStep(0.01)
        self.confidence_threshold_spinbox.setValue(0.20)

        self.create_detection_data_checkbox = QCheckBox("Create 'detection_data' folder")
        self.create_detection_data_checkbox.setChecked(True)

        self.delete_no_detection_checkbox = QCheckBox("Delete videos with no detections")
        self.delete_no_detection_checkbox.setChecked(False)

        self.include_category_0_2_checkbox = QCheckBox("Include videos with category 0 or 2 detections (rename to 'hito_ + original name')")
        self.include_category_0_2_checkbox.setChecked(False)

        self.start_button = QPushButton("Start Processing")
        self.start_button.clicked.connect(self.start_processing)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)

        self.log_text_edit = QTextEdit()
        self.log_text_edit.setReadOnly(True)

        # Layouts
        layout = QVBoxLayout()
        input_dir_layout = QHBoxLayout()
        input_dir_layout.addWidget(self.input_dir_label)
        input_dir_layout.addWidget(self.input_dir_line_edit)
        input_dir_layout.addWidget(self.browse_button)

        frame_interval_layout = QHBoxLayout()
        frame_interval_layout.addWidget(self.frame_interval_label)
        frame_interval_layout.addWidget(self.frame_interval_spinbox)

        confidence_threshold_layout = QHBoxLayout()
        confidence_threshold_layout.addWidget(self.confidence_threshold_label)
        confidence_threshold_layout.addWidget(self.confidence_threshold_spinbox)

        layout.addLayout(input_dir_layout)
        layout.addLayout(frame_interval_layout)
        layout.addLayout(confidence_threshold_layout)
        layout.addWidget(self.create_detection_data_checkbox)
        layout.addWidget(self.delete_no_detection_checkbox)
        layout.addWidget(self.include_category_0_2_checkbox)
        layout.addWidget(self.start_button)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.log_text_edit)

        central_widget = QWidget()
        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)

    def browse_input_directory(self):
        dir_name = QFileDialog.getExistingDirectory(self, "Select Input Directory", "")
        if dir_name:
            self.input_dir_line_edit.setText(dir_name)

    def start_processing(self):
        # Get parameters from UI
        input_folder = self.input_dir_line_edit.text()
        if not input_folder:
            self.log("Please select an input directory.")
            return
        if not os.path.isdir(input_folder):
            self.log("The specified directory does not exist.")
            return
        every_n_frames = self.frame_interval_spinbox.value()
        confidence_threshold = self.confidence_threshold_spinbox.value()
        create_detection_data = self.create_detection_data_checkbox.isChecked()
        delete_no_detection = self.delete_no_detection_checkbox.isChecked()
        include_category_0_2 = self.include_category_0_2_checkbox.isChecked()
        # Disable the start button to prevent multiple clicks
        self.start_button.setEnabled(False)
        # Reset progress bar
        self.progress_bar.setValue(0)
        # Start the processing in a separate thread
        self.processing_thread = ProcessingThread(
            input_folder=input_folder,
            every_n_frames=every_n_frames,
            confidence_threshold=confidence_threshold,
            create_detection_data=create_detection_data,
            delete_no_detection=delete_no_detection,
            include_category_0_2=include_category_0_2
        )
        self.processing_thread.log_signal.connect(self.log)
        self.processing_thread.progress_signal.connect(self.update_progress)
        self.processing_thread.finished.connect(self.processing_finished)
        self.processing_thread.start()

    def log(self, message):
        self.log_text_edit.append(message)

    def update_progress(self, value):
        self.progress_bar.setValue(value)

    def processing_finished(self):
        self.log("Processing completed.")
        self.start_button.setEnabled(True)

class ProcessingThread(QThread):
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int)
    finished = pyqtSignal()

    def __init__(self, input_folder, every_n_frames, confidence_threshold, create_detection_data, delete_no_detection, include_category_0_2):
        super().__init__()
        self.input_folder = input_folder
        self.every_n_frames = every_n_frames
        self.confidence_threshold = confidence_threshold
        self.create_detection_data = create_detection_data
        self.delete_no_detection = delete_no_detection
        self.include_category_0_2 = include_category_0_2

    def run(self):
        # Main processing code goes here
        self.process_videos()
        self.finished.emit()

    def log(self, message):
        self.log_signal.emit(message)

    def update_progress(self, value):
        self.progress_signal.emit(value)

    def process_videos(self):
        input_folder = self.input_folder
        every_n_frames = self.every_n_frames
        confidence_threshold = self.confidence_threshold
        create_detection_data = self.create_detection_data
        delete_no_detection = self.delete_no_detection
        include_category_0_2 = self.include_category_0_2

        if create_detection_data:
            output_base = os.path.join(input_folder, "detection_data")
            tracking_file = os.path.join(output_base, 'video_confidence_tracking.json')

            # Create output directory
            os.makedirs(output_base, exist_ok=True)
            self.log(f"Created/Verified output directory at {output_base}")

        model_file = r'md_v5b.0.0.pt'  # Ensure this points to your actual model file path

        # Load data
        if create_detection_data and os.path.exists(tracking_file):
            with open(tracking_file, 'r') as f:
                video_confidence_dict = json.load(f)
        else:
            video_confidence_dict = {}

        # Load the detector once
        detector = load_detector(model_file)
        self.log("動物認識AIの読み込みが完了しました")

        # Load video filenames
        video_filenames = video_utils.find_videos(input_folder, recursive=True)
        video_paths = [os.path.join(input_folder, fn) for fn in video_filenames]

        if not video_paths:
            self.log("No video files found in the specified directory.")
            return

        total_videos = len(video_paths)
        self.log(f"\nFound {total_videos} video(s) to process.\n")

        processed_videos = 0

        def process_video(video_path):
            nonlocal processed_videos
            cap = cv2.VideoCapture(video_path)
            frame_count = 0
            max_confidence_detection = 0
            best_frame = None
            best_detection = None
            best_frame_detections = []
            detection_in_upper_small = False  # Flag for 'tori' condition
            category_0_2_detected = False  # Flag for category 0 or 2 detections
            max_confidence_0_2 = 0
            best_detection_0_2 = None
            best_frame_0_2 = None
            best_frame_detections_0_2 = []

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
                self.log(f"No frames to process in {video_path}")
                shutil.rmtree(temp_dir)
                if delete_no_detection:
                    try:
                        os.remove(video_path)
                        self.log(f"Deleted video without detections: {video_path}")
                    except Exception as e:
                        self.log(f"Error deleting {video_path}: {e}")
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
                    self.log(f"Could not read frame {frame_filename}")
                    continue

                detections = result.get('detections', [])
                frame_valid_detections = []
                frame_valid_detections_0_2 = []

                for detection in detections:
                    if detection['conf'] > confidence_threshold:
                        if detection['category'] == '1':
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
                        elif detection['category'] in ['0', '2']:
                            category_0_2_detected = True
                            frame_valid_detections_0_2.append(detection)

                            if detection['conf'] > max_confidence_0_2:
                                max_confidence_0_2 = detection['conf']
                                best_detection_0_2 = detection
                                best_frame_0_2 = frame.copy()
                                best_frame_detections_0_2 = frame_valid_detections_0_2.copy()

                # Handle the category 0 or 2 detection
                # if category_0_2_detected and include_category_0_2:
                #     # If including category 0 or 2 detections, set a prefix
                #     prefix = "hito_"
                # else:
                #     prefix = None

            if best_detection is None and not (include_category_0_2 and category_0_2_detected):
                self.log(f"No valid detections found in {video_path}")
                shutil.rmtree(temp_dir)
                if delete_no_detection:
                    try:
                        os.remove(video_path)
                        self.log(f"Deleted video without detections: {video_path}")
                    except Exception as e:
                        self.log(f"Error deleting {video_path}: {e}")
                return

            # Update tracking data
            if create_detection_data:
                video_confidence_dict[video_path] = max_confidence_detection

            # Determine prefix based on detection condition
            if category_0_2_detected and include_category_0_2:
                prefix = "hito_"
                best_detection = best_detection_0_2
                best_frame = best_frame_0_2
                best_frame_detections = best_frame_detections_0_2
            elif detection_in_upper_small:
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
                self.log(f"File {new_video_path} already exists. Cannot rename {video_path}.")
            else:
                try:
                    os.rename(video_path, new_video_path)
                    self.log(f"Renamed {video_path} to {new_video_path}.")
                except Exception as e:
                    self.log(f"Error renaming {video_path}: {e}")

            if create_detection_data and best_detection is not None:
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
                self.log(f"Saved cropped image to {cropped_image_path}")

            # Clean up temporary files
            shutil.rmtree(temp_dir)

            processed_videos += 1
            progress_percent = int((processed_videos / total_videos) * 100)
            self.update_progress(progress_percent)

        def save_video_confidence_dict():
            if create_detection_data:
                with open(tracking_file, 'w') as f:
                    json.dump(video_confidence_dict, f, indent=2)
                self.log(f"Saved video confidence tracking data to {tracking_file}")

        # Process each video
        for video_path in video_paths:
            self.log(f"Processing {video_path}...")
            process_video(video_path)
            self.log("-" * 50)

        # Save the video confidence tracking file
        save_video_confidence_dict()
        self.log("\n=== Processing Completed ===")
        # Ensure progress bar is at 100% after processing
        self.update_progress(100)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = VideoDetectionApp()
    window.show()
    sys.exit(app.exec_())
