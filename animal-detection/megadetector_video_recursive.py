import sys
import os
import cv2
import json
import shutil
import tempfile
import subprocess  # Import subprocess to open external applications
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QFileDialog, QLabel, QLineEdit,
    QPushButton, QVBoxLayout, QHBoxLayout, QSpinBox, QDoubleSpinBox, QCheckBox,
    QTextEdit, QProgressBar, QWidget, QMessageBox  # Import QMessageBox for confirmations
)
from PyQt5.QtCore import QThread, pyqtSignal
from megadetector.detection import video_utils
from megadetector.detection.run_detector_batch import load_detector, process_images


processed_videos = 0


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
    print(f"Saved detection boxes to {output_path}")


# Function to crop images
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

    x_min_pixel = max(0, x_min_pixel)
    y_min_pixel = max(0, y_min_pixel)
    x_max_pixel = min(width, x_max_pixel)
    y_max_pixel = min(height, y_max_pixel)

    cropped_image = image[y_min_pixel:y_max_pixel, x_min_pixel:x_max_pixel]
    return cropped_image


def process_image_file(
    image_file, detector, confidence_threshold, output_base, log,
    rename_images=False, delete_no_detections=False, hito_prefix="hito_", tori_prefix="tori_", animal_prefix="nekokamo_"
):
    """
    Process a single image file.
    """
    image_path = image_file
    image_file_name = os.path.basename(image_file)
    log(f"Processing image: {image_path}")

    image = cv2.imread(image_path)
    if image is None:
        log(f"Could not read {image_path}")
        return

    results = process_images(
        im_files=[image_path],
        detector=detector,
        confidence_threshold=0.0,
        use_image_queue=False,
        quiet=True
    )

    detections = results[0].get('detections', [])
    valid_detections = [d for d in detections if d['conf'] > confidence_threshold]

    if not valid_detections:
        log(f"No valid detections in {image_path}")
        if delete_no_detections:
            try:
                os.remove(image_path)
                log(f"Deleted image: {image_path}")
            except Exception as e:
                log(f"Failed to delete {image_path}: {str(e)}")
        return  # Do not proceed further

    # Determine prefix based on detection type
    prefix = ""
    detection_in_upper_small = False  # For 'tori_' condition
    category_0_2_detected = False  # For 'hito_' condition

    for detection in valid_detections:
        if detection['category'] == '1':
            height, width, _ = image.shape
            x_min, y_min, bbox_width, bbox_height = detection['bbox']
            x_min_pixel = int(x_min * width)
            y_min_pixel = int(y_min * height)
            x_max_pixel = int((x_min + bbox_width) * width)
            y_max_pixel = int((y_min + bbox_height) * height)

            # Check 'tori_' condition
            bbox_width_pixels = x_max_pixel - x_min_pixel
            bbox_height_pixels = y_max_pixel - y_min_pixel
            if (y_max_pixel <= height / 2 and bbox_width_pixels + bbox_height_pixels < 180) or \
               (bbox_width_pixels < 60 and bbox_height_pixels < 60):
                detection_in_upper_small = True
        elif detection['category'] in ['0', '2']:
            category_0_2_detected = True

    if category_0_2_detected:
        prefix = hito_prefix
    elif detection_in_upper_small:
        prefix = tori_prefix
    else:
        prefix = animal_prefix

    # Rename image file if enabled
    if rename_images:
        image_dir = os.path.dirname(image_path)
        new_image_name = prefix + image_file_name
        new_image_path = os.path.join(image_dir, new_image_name)

        if os.path.exists(new_image_path):
            log(f"Cannot rename {image_path}: File {new_image_name} already exists")
        else:
            os.rename(image_path, new_image_path)
            log(f"Renamed image: {image_path} -> {new_image_path}")
            image_file_name = new_image_name  # Update for consistency

    # Save detections
    output_folder_name = f"{prefix}detection_data_{os.path.splitext(image_file_name)[0]}"
    output_dir = os.path.join(output_base, output_folder_name)
    os.makedirs(output_dir, exist_ok=True)

    output_image_path = os.path.join(output_dir, 'detections.jpg')
    draw_detections_on_image(image.copy(), valid_detections, confidence_threshold, output_image_path)
    log(f"Saved detection image to {output_image_path}")

    for i, detection in enumerate(valid_detections):
        cropped_image = crop_image_with_bbox_image(image, detection['bbox'])
        cropped_image_path = os.path.join(output_dir, f'cropped_image_{i}.jpg')
        cv2.imwrite(cropped_image_path, cropped_image)

        log(f"Saved cropped image to {cropped_image_path}")

    log("Image processing complete")


def process_video_file(
    video_file, detector, confidence_threshold, output_base, log, 
    every_n_frames=16, max_duration_seconds=10, save_all_detections=False,
    rename_videos=False, delete_no_detections=False, hito_prefix="hito_", tori_prefix="tori_", animal_prefix="nekokamo_"
):
    """
    Process a single video file.
    """
    video_path = video_file
    video_file_name = os.path.basename(video_file)
    log(f"Processing video: {video_path}")

    # Load the video
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        log(f"Could not open video {video_path}")
        return

    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    max_frames = int(max_duration_seconds * fps)

    log(f"Video FPS: {fps}, Total Frames: {total_frames}, Max Frames to Process: {max_frames}")

    frame_count = 0
    temp_dir = tempfile.mkdtemp()
    frame_files = []
    frame_indices = []

    # Variables to track the highest confidence detection
    best_detection = None
    best_frame = None
    max_confidence = -1  # Initialize with a value lower than any confidence score

    # Variables to track detection types
    detection_in_upper_small = False  # For 'tori_' condition
    category_0_2_detected = False  # For 'hito_' condition

    # List to store frames with detections when save_all_detections is True
    frames_with_detections = []

    # Flag to indicate if any detections were found
    detections_found = False

    try:
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            frame_count += 1
            if frame_count > max_frames:
                log(f"Reached max duration ({max_duration_seconds} seconds) for {video_path}")
                break

            if frame_count % every_n_frames == 0:
                frame_filename = os.path.join(temp_dir, f'frame_{frame_count}.jpg')
                cv2.imwrite(frame_filename, frame)
                frame_files.append(frame_filename)
                frame_indices.append(frame_count)

        cap.release()

        if not frame_files:
            log(f"No frames extracted from {video_path}")
            return

        # Process frames using the detector
        results = process_images(
            im_files=frame_files,
            detector=detector,
            confidence_threshold=0.0,
            use_image_queue=False,
            quiet=True
        )

        for i, result in enumerate(results):
            detections = result.get('detections', [])
            valid_detections = [d for d in detections if d['conf'] > confidence_threshold]

            if valid_detections:
                detections_found = True  # At least one detection over the threshold found
                frame_path = frame_files[i]
                frame = cv2.imread(frame_path)

                # Update detection types for renaming
                for detection in valid_detections:
                    if detection['category'] == '1':
                        height, width, _ = frame.shape
                        x_min, y_min, bbox_width, bbox_height = detection['bbox']
                        x_min_pixel = int(x_min * width)
                        y_min_pixel = int(y_min * height)
                        x_max_pixel = int((x_min + bbox_width) * width)
                        y_max_pixel = int((y_min + bbox_height) * height)

                        # Check 'tori_' condition
                        bbox_width_pixels = x_max_pixel - x_min_pixel
                        bbox_height_pixels = y_max_pixel - y_min_pixel
                        if (y_max_pixel <= height / 2 and bbox_width_pixels + bbox_height_pixels < 180) or \
                           (bbox_width_pixels < 60 and bbox_height_pixels < 60):
                            detection_in_upper_small = True
                    elif detection['category'] in ['0', '2']:
                        category_0_2_detected = True

                if save_all_detections:
                    # Collect frames with detections
                    frames_with_detections.append((frame_path, valid_detections))
                else:
                    # Update max confidence and best detection
                    for detection in valid_detections:
                        if detection['conf'] > max_confidence:
                            max_confidence = detection['conf']
                            best_detection = detection
                            best_frame = frame.copy()

        if not detections_found:
            log(f"No valid detections in {video_path}")
            if delete_no_detections:
                try:
                    os.remove(video_path)
                    log(f"Deleted video: {video_path}")
                except Exception as e:
                    log(f"Failed to delete {video_path}: {str(e)}")
            return  # Do not proceed further

        # Determine prefix based on detection type
        prefix = ""
        if category_0_2_detected:
            prefix = hito_prefix
        elif detection_in_upper_small:
            prefix = tori_prefix
        else:
            prefix = animal_prefix

        # Rename video file if enabled
        if rename_videos:
            video_dir = os.path.dirname(video_path)
            new_video_name = prefix + video_file_name
            new_video_path = os.path.join(video_dir, new_video_name)

            if os.path.exists(new_video_path):
                log(f"Cannot rename {video_path}: File {new_video_name} already exists")
            else:
                os.rename(video_path, new_video_path)
                log(f"Renamed video: {video_path} -> {new_video_path}")
                video_file_name = new_video_name  # Update for consistency
                video_path = new_video_path       # Update video_path as well

        # Save detections
        output_folder_name = f"{prefix}detection_data_{os.path.splitext(video_file_name)[0]}"
        output_dir = os.path.join(output_base, output_folder_name)
        os.makedirs(output_dir, exist_ok=True)

        if save_all_detections and frames_with_detections:
            for idx, (frame_path, detections) in enumerate(frames_with_detections):
                frame = cv2.imread(frame_path)
                frame_with_detections = frame.copy()
                output_image_path = os.path.join(output_dir, f"frame_{idx}_with_detections.jpg")
                draw_detections_on_image(frame_with_detections, detections, confidence_threshold, output_image_path)
                log(f"Saved frame with detections to {output_image_path}")

                # Save cropped images for each detection
                for j, detection in enumerate(detections):
                    cropped_image = crop_image_with_bbox_image(frame, detection['bbox'])
                    cropped_image_path = os.path.join(output_dir, f"frame_{idx}_cropped_{j}.jpg")
                    cv2.imwrite(cropped_image_path, cropped_image)
                    log(f"Saved cropped image to {cropped_image_path}")

            log(f"Saved all detections for video {video_file_name} to {output_dir}")
        else:
            # Save best frame and cropped image
            output_image_path = os.path.join(output_dir, 'best_frame_with_detections.jpg')
            draw_detections_on_image(best_frame.copy(), [best_detection], confidence_threshold, output_image_path)

            cropped_image = crop_image_with_bbox_image(best_frame, best_detection['bbox'])
            cropped_image_path = os.path.join(output_dir, 'cropped_image.jpg')
            cv2.imwrite(cropped_image_path, cropped_image)

            log(f"Saved best frame with detection to {output_image_path}")
            log(f"Saved cropped image to {cropped_image_path}")

        log("Video processing complete")

    finally:
        # Ensure the temporary directory is deleted
        shutil.rmtree(temp_dir)


class ProcessingThread(QThread):
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int, int)  # Emits (processed_count, total_count)
    finished = pyqtSignal()

    def __init__(
        self, input_folder, every_n_frames, confidence_threshold,
        create_detection_data, delete_no_detection, include_category_0_2,
        processing_duration_seconds, save_all_checkbox, rename_files_checkbox,
        hito_prefix, tori_prefix, animal_prefix
    ):
        super().__init__()
        self.input_folder = input_folder
        self.every_n_frames = every_n_frames
        self.confidence_threshold = confidence_threshold
        self.create_detection_data = create_detection_data
        self.delete_no_detection = delete_no_detection
        self.include_category_0_2 = include_category_0_2
        self.processing_duration_seconds = processing_duration_seconds
        self.save_all_checkbox = save_all_checkbox
        self.rename_files_checkbox = rename_files_checkbox
        self.hito_prefix = hito_prefix
        self.tori_prefix = tori_prefix
        self.animal_prefix = animal_prefix
        self.total_files = 0  # Initialize total files count
        self.processed_count = 0  # Track processed files


    def log(self, message):
        self.log_signal.emit(message)

    def update_progress(self):
        """
        Emit the progress signal with the current state.
        """
        self.progress_signal.emit(self.processed_count, self.total_files)

    def run(self):
        """
        Entry point for the thread. Calls the main processing function.
        """
        self.log("Thread is running...")
        self.process_data()
        self.finished.emit()

    def process_data(self):
        """
        Main processing function. Processes images and videos, while tracking progress.
        """
        try:
            self.log("Starting processing...")
            if self.create_detection_data:
                output_base = os.path.join(self.input_folder, "detection_data")
                os.makedirs(output_base, exist_ok=True)
                self.log(f"Output will be saved to {output_base}")
            else:
                output_base = None  # Or set to some default

            self.log("Loading AI detector model...")
            try:
                detector = load_detector('md_v5b.0.0.pt')  # Adjust path as needed
                self.log("Detector loaded successfully.")
            except Exception as e:
                self.log(f"Failed to load detector: {str(e)}")
                return

            self.log("AI detector model loaded successfully")

            self.log("Counting files in input folder...")
            image_extensions = ['.jpg', '.jpeg', '.png']
            video_extensions = ['.mp4', '.avi', '.mov', '.mkv']
            prefixes = [self.hito_prefix, self.tori_prefix, self.animal_prefix]  # Use user-defined prefixes

            image_files = []
            video_files = []

            for root, dirs, files in os.walk(self.input_folder):
                for f in files:
                    ext = os.path.splitext(f)[1].lower()
                    if ext in image_extensions:
                        if not any(f.startswith(prefix) for prefix in prefixes):
                            image_files.append(os.path.join(root, f))
                    elif ext in video_extensions:
                        if not any(f.startswith(prefix) for prefix in prefixes):
                            video_files.append(os.path.join(root, f))

            self.total_files = len(image_files) + len(video_files)
            self.log(f"Found {len(image_files)} images and {len(video_files)} videos")

            # Process images
            self.log("Processing images...")
            for image_file in image_files:
                self.log(f"Processing image: {image_file}")
                process_image_file(
                    image_file=image_file,
                    detector=detector,
                    confidence_threshold=self.confidence_threshold,
                    output_base=output_base,
                    log=self.log,
                    rename_images=self.rename_files_checkbox,
                    delete_no_detections=self.delete_no_detection,
                    hito_prefix=self.hito_prefix,
                    tori_prefix=self.tori_prefix,
                    animal_prefix=self.animal_prefix
                )
                self.processed_count += 1
                self.update_progress()

            # Process videos
            self.log("Processing videos...")
            for video_file in video_files:
                self.log(f"Processing video: {video_file}")
                process_video_file(
                    video_file=video_file,
                    detector=detector,
                    confidence_threshold=self.confidence_threshold,
                    output_base=output_base,
                    log=self.log,
                    every_n_frames=self.every_n_frames,
                    max_duration_seconds=self.processing_duration_seconds,
                    save_all_detections=self.save_all_checkbox,
                    rename_videos=self.rename_files_checkbox,
                    delete_no_detections=self.delete_no_detection,
                    hito_prefix=self.hito_prefix,
                    tori_prefix=self.tori_prefix,
                    animal_prefix=self.animal_prefix
                )
                self.processed_count += 1
                self.update_progress()

            self.log("Processing completed successfully.")
        except Exception as e:
            self.log(f"Error during processing: {str(e)}")
        finally:
            self.finished.emit()

class VideoDetectionApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Animal Detection Tool")
        self.initUI()

    def initUI(self):
        # Create widgets
        self.input_dir_label = QLabel("処理対象フォルダー:")
        self.input_dir_line_edit = QLineEdit()
        self.browse_button = QPushButton("参照")
        self.browse_button.clicked.connect(self.browse_input_directory)

        self.frame_interval_label = QLabel("コマ間隔 (コマ何枚に１枚処理するか):")
        self.frame_interval_spinbox = QSpinBox()
        self.frame_interval_spinbox.setRange(1, 1000)
        self.frame_interval_spinbox.setValue(16)

        self.confidence_threshold_label = QLabel("確信度のしきい値:")
        self.confidence_threshold_spinbox = QDoubleSpinBox()
        self.confidence_threshold_spinbox.setRange(0.0, 1.0)
        self.confidence_threshold_spinbox.setSingleStep(0.01)
        self.confidence_threshold_spinbox.setValue(0.4)

        # *** New GUI Elements Start Here ***
        self.processing_duration_label = QLabel("動画の何秒まで処理:")
        self.processing_duration_spinbox = QSpinBox()
        self.processing_duration_spinbox.setRange(1, 3600)  # 1 second to 1 hour
        self.processing_duration_spinbox.setValue(5)  # Default value
        # *** New GUI Elements End Here ***

        self.create_detection_data_checkbox = QCheckBox("'detection_data'フォルダーを作成する")
        self.create_detection_data_checkbox.setChecked(False)

        self.delete_no_detection_checkbox = QCheckBox("認識情報がない動画を削除する")
        self.delete_no_detection_checkbox.setChecked(False)
        self.open_external_app_button = QPushButton("動画再生APPを開く")
        self.open_external_app_button.clicked.connect(self.open_external_application)

        self.remove_prefixes_button = QPushButton("Remove Prefixes from File Names")
        self.remove_prefixes_button.clicked.connect(self.remove_prefixes_from_files)

        # Prefix for people/cars detection
        self.hito_prefix_label = QLabel("Prefix for people/cars detection:")
        self.hito_prefix_line_edit = QLineEdit()
        self.hito_prefix_line_edit.setText("hito_")  # Default value

        # Prefix for bird detection
        self.tori_prefix_label = QLabel("Prefix for bird detection:")
        self.tori_prefix_line_edit = QLineEdit()
        self.tori_prefix_line_edit.setText("tori_")  # Default value

        # Prefix for animal detection
        self.animal_prefix_label = QLabel("Prefix for animal detection:")
        self.animal_prefix_line_edit = QLineEdit()
        self.animal_prefix_line_edit.setText("nekokamo_")  # Default value

        
        self.save_all_checkbox = QCheckBox("Save all detections")
        self.save_all_checkbox.setChecked(False)

        self.rename_files_checkbox = QCheckBox("Rename videos based on detection type")
        self.rename_files_checkbox.setChecked(False)



        self.start_button = QPushButton("処理開始")
        self.start_button.clicked.connect(self.start_processing)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("%v/%m")  # Set initial format to show current/maximum

        self.log_text_edit = QTextEdit()
        self.log_text_edit.setReadOnly(True)
        
        # Layouts
        prefix_layout = QVBoxLayout()
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

        # *** New Layout for Processing Duration ***
        processing_duration_layout = QHBoxLayout()
        processing_duration_layout.addWidget(self.processing_duration_label)
        processing_duration_layout.addWidget(self.processing_duration_spinbox)
        # *** End of New Layout ***

        layout.addLayout(input_dir_layout)
        layout.addLayout(frame_interval_layout)
        layout.addLayout(confidence_threshold_layout)
        layout.addLayout(processing_duration_layout)  # Add new layout here
        layout.addWidget(self.create_detection_data_checkbox)
        layout.addWidget(self.delete_no_detection_checkbox)
        layout.addWidget(self.save_all_checkbox)
        layout.addWidget(self.open_external_app_button)
        layout.addWidget(self.remove_prefixes_button)
        # Add prefix inputs
        layout.addLayout(prefix_layout)

        layout.addWidget(self.start_button)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.log_text_edit)
        hito_prefix_layout = QHBoxLayout()
        hito_prefix_layout.addWidget(self.hito_prefix_label)
        hito_prefix_layout.addWidget(self.hito_prefix_line_edit)

        tori_prefix_layout = QHBoxLayout()
        tori_prefix_layout.addWidget(self.tori_prefix_label)
        tori_prefix_layout.addWidget(self.tori_prefix_line_edit)

        animal_prefix_layout = QHBoxLayout()
        animal_prefix_layout.addWidget(self.animal_prefix_label)
        animal_prefix_layout.addWidget(self.animal_prefix_line_edit)

        prefix_layout.addLayout(hito_prefix_layout)
        prefix_layout.addLayout(tori_prefix_layout)
        prefix_layout.addLayout(animal_prefix_layout)
        layout.addWidget(self.rename_files_checkbox)
        layout.addWidget(self.start_button)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.log_text_edit)

        central_widget = QWidget()
        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)

    def browse_input_directory(self):
        dir_name = QFileDialog.getExistingDirectory(self, "処理対象フォルダーを選択", "")
        if dir_name:
            self.input_dir_line_edit.setText(dir_name)

    def start_processing(self):
        # Get parameters from UI
        input_folder = self.input_dir_line_edit.text()
        if not input_folder:
            self.log("Please select a folder to process")
            return
        if not os.path.isdir(input_folder):
            self.log("Selected folder does not exist")
            return

        self.log("Starting processing thread...")
        every_n_frames = self.frame_interval_spinbox.value()
        confidence_threshold = self.confidence_threshold_spinbox.value()
        create_detection_data = self.create_detection_data_checkbox.isChecked()
        delete_no_detection = self.delete_no_detection_checkbox.isChecked()
        processing_duration_seconds = self.processing_duration_spinbox.value()
        save_all_checkbox = self.save_all_checkbox.isChecked()
        rename_files_checkbox = self.rename_files_checkbox.isChecked()

        # Get user-defined prefixes
        hito_prefix = self.hito_prefix_line_edit.text()
        tori_prefix = self.tori_prefix_line_edit.text()
        animal_prefix = self.animal_prefix_line_edit.text()

        # Disable the start button to prevent multiple clicks
        self.start_button.setEnabled(False)
        self.progress_bar.setValue(0)

        self.processing_thread = ProcessingThread(
            input_folder=input_folder,
            every_n_frames=every_n_frames,
            confidence_threshold=confidence_threshold,
            create_detection_data=create_detection_data,
            delete_no_detection=delete_no_detection,
            save_all_checkbox=save_all_checkbox,
            processing_duration_seconds=processing_duration_seconds,
            rename_files_checkbox=rename_files_checkbox,
            hito_prefix=hito_prefix,
            tori_prefix=tori_prefix,
            animal_prefix=animal_prefix
        )


        # Connect signals
        self.processing_thread.log_signal.connect(self.log)
        self.processing_thread.progress_signal.connect(self.update_progress)
        self.processing_thread.finished.connect(self.processing_finished)

        # Start thread
        self.processing_thread.start()
        self.log("Processing thread started.")

    def log(self, message):
        self.log_text_edit.append(message)

    def update_progress(self, processed, total):
        """
        Update the progress bar based on the current progress.
        """
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(processed)
        # Display progress as "Processed/Total"
        self.progress_bar.setFormat(f"{processed}/{total}")
        self.log(f"Progress: {processed}/{total}")

    def open_external_application(self):
        """
        Opens the external application specified by the path.
        """
        external_app_path = r"C:\Users\dalca\OneDrive - nkz.ac.jp\Escritorio\internship-MIT\MOV_player\DiegoMOV_Player1.2.exe"
        try:
            subprocess.Popen(external_app_path)
            self.log(f"Opened external application: {external_app_path}")
        except Exception as e:
            self.log(f"Failed to open external application: {str(e)}")

    def remove_prefixes_from_files(self):
        """
        Removes specified prefixes from file names in the selected folder.
        """
        input_folder = self.input_dir_line_edit.text()
        if not input_folder:
            self.log("Please select a folder first.")
            return
        if not os.path.isdir(input_folder):
            self.log("Selected folder does not exist.")
            return

        # Get user-defined prefixes
        hito_prefix = self.hito_prefix_line_edit.text()
        tori_prefix = self.tori_prefix_line_edit.text()
        animal_prefix = self.animal_prefix_line_edit.text()
        prefixes = [hito_prefix, tori_prefix, animal_prefix]

        # Confirm renaming
        reply = QMessageBox.question(
            self,
            "Confirm Prefix Removal",
            f"This will remove the prefixes {prefixes} from file names in the selected folder.\nAre you sure you want to proceed?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.No:
            self.log("Prefix removal canceled.")
            return

        # Proceed with renaming
        renamed_files = []
        for root, dirs, files in os.walk(input_folder):
            for file in files:
                for prefix in prefixes:
                    if file.startswith(prefix):
                        original_file_path = os.path.join(root, file)
                        new_file_name = file[len(prefix):]  # Remove the prefix
                        new_file_path = os.path.join(root, new_file_name)

                        # Check if a file with the new name already exists
                        if os.path.exists(new_file_path):
                            self.log(f"Cannot rename {original_file_path} to {new_file_name}: File already exists.")
                            continue

                        try:
                            os.rename(original_file_path, new_file_path)
                            renamed_files.append((original_file_path, new_file_path))
                        except Exception as e:
                            self.log(f"Failed to rename {original_file_path}: {str(e)}")

        self.log(f"Renamed {len(renamed_files)} files by removing prefixes.")
        for original, new in renamed_files:
            self.log(f"Renamed: {original} -> {new}")


        def processing_finished(self):
            self.log("Processing complete")
            self.start_button.setEnabled(True)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = VideoDetectionApp()
    window.show()
    sys.exit(app.exec_())
