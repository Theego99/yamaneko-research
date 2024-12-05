import sys
import os
import cv2
import json
import shutil
import tempfile
import subprocess
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QFileDialog, QLabel, QLineEdit,
    QPushButton, QVBoxLayout, QHBoxLayout, QProgressBar, QWidget,
    QTextEdit, QCheckBox, QSpinBox, QDoubleSpinBox, QMessageBox, QSizePolicy, QScrollArea
)
from PyQt5.QtCore import QThread, pyqtSignal, Qt, QSize
from PyQt5.QtGui import QIcon, QFont, QPalette, QColor
from megadetector.detection.run_detector_batch import load_detector

from megadetector.detection import video_utils
from megadetector.detection.run_detector_batch import load_detector, process_images
from torch import Size



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
    rename_images=False, delete_no_detections=False, hito_prefix="hito_", animal_prefix="nekokamo_"
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

    for detection in valid_detections:
        if detection['category'] == '1':
            prefix = animal_prefix
        else:
            prefix = hito_prefix


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

    # Save detections only if output_base is not None
    if output_base is not None:
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
    else:
        log("Detection data saving is disabled.")

    log("Image processing complete")


def process_video_file(
    video_file, detector, confidence_threshold, output_base, log, 
    every_n_frames=16, max_duration_seconds=10, save_all_detections=False,
    rename_videos=False, delete_no_detections=False, hito_prefix="hito_", animal_prefix="nekokamo_"
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
                prefix = ""
                # Update detection types for renaming
                for detection in valid_detections:
                    if detection['category'] == '1':
                        prefix = animal_prefix
                    else:
                        prefix = hito_prefix

                if save_all_detections and output_base is not None:
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

        # Save detections only if output_base is not None
        if output_base is not None:
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
            elif best_detection is not None and best_frame is not None:
                # Save best frame and cropped image
                output_image_path = os.path.join(output_dir, 'best_frame_with_detections.jpg')
                draw_detections_on_image(best_frame.copy(), [best_detection], confidence_threshold, output_image_path)

                cropped_image = crop_image_with_bbox_image(best_frame, best_detection['bbox'])
                cropped_image_path = os.path.join(output_dir, 'cropped_image.jpg')
                cv2.imwrite(cropped_image_path, cropped_image)

                log(f"Saved best frame with detection to {output_image_path}")
                log(f"Saved cropped image to {cropped_image_path}")
            else:
                log("No frames to save.")
        else:
            log("Detection data saving is disabled.")

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
        create_detection_data, delete_no_detection,
        processing_duration_seconds, save_all_checkbox, rename_files_checkbox,
        hito_prefix, animal_prefix
    ):
        super().__init__()
        self.input_folder = input_folder
        self.every_n_frames = every_n_frames
        self.confidence_threshold = confidence_threshold
        self.create_detection_data = create_detection_data
        self.delete_no_detection = delete_no_detection
        self.processing_duration_seconds = processing_duration_seconds
        self.save_all_checkbox = save_all_checkbox
        self.rename_files_checkbox = rename_files_checkbox
        self.hito_prefix = hito_prefix
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
            prefixes = [self.hito_prefix, self.animal_prefix]  # Use user-defined prefixes

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
        self.setGeometry(100, 100, 1200, 800)  # Full-screen optimized

        # Initialize languages and default language
        self.languages = ['Japanese', 'Spanish', 'Chinese', 'English', 'Korean']
        self.current_language_index = 0
        self.language = self.languages[self.current_language_index]

        # Initialize text for file dialog
        self.select_input_folder_text = "処理対象フォルダーを選択"  # Default to Japanese

        self.initUI()

    def initUI(self):
        # Main layout
        main_widget = QWidget()
        main_layout = QHBoxLayout()
        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)

        # Left sidebar
        self.sidebar = QWidget()
        self.sidebar_layout = QVBoxLayout()
        self.sidebar.setLayout(self.sidebar_layout)
        self.sidebar.setFixedWidth(50)  # Adjusted width
        self.sidebar.setStyleSheet("background-color: #252525;")
        main_layout.addWidget(self.sidebar)

        # Settings button with icon
        self.settings_button = QPushButton()
        settings_icon = QIcon('assets/settings_icon.png')  # Ensure this icon exists
        self.settings_button.setIcon(settings_icon)
        self.settings_button.setIconSize(QSize(32, 32))
        self.settings_button.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
            }
            QPushButton:hover {
                background-color: #3A3A3A;
                border-radius: 5px;
            }
        """)
        self.settings_button.clicked.connect(self.toggle_settings_panel)
        self.sidebar_layout.addWidget(self.settings_button)

        # Language toggle button with icon
        self.language_button = QPushButton()
        language_icon = QIcon('assets/language_icon.png')  # Ensure this icon exists
        self.language_button.setIcon(language_icon)
        self.language_button.setIconSize(QSize(32, 32))
        self.language_button.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
            }
            QPushButton:hover {
                background-color: #3A3A3A;
                border-radius: 5px;
            }
        """)
        self.language_button.clicked.connect(self.toggle_language)
        self.sidebar_layout.addWidget(self.language_button)

        # Add stretch to push items to the bottom
        self.sidebar_layout.addStretch()

        # Settings panel (initially hidden)
        self.settings_panel = QWidget()
        self.settings_panel_layout = QVBoxLayout()
        self.settings_panel.setLayout(self.settings_panel_layout)
        self.settings_panel.setFixedWidth(300)  # Fixed width
        self.settings_panel.setStyleSheet("background-color: #1E1E1E;")
        self.settings_panel.hide()
        # Insert settings panel right after the sidebar
        main_layout.addWidget(self.settings_panel)

        # Settings widgets
        self.initSettingsPanel()

        # Main area
        self.main_area = QWidget()
        self.main_area_layout = QVBoxLayout()
        self.main_area_layout.setSpacing(10)  # Consistent spacing
        self.main_area.setLayout(self.main_area_layout)
        main_layout.addWidget(self.main_area)

        # Input directory selection
        input_dir_layout = QHBoxLayout()
        self.input_dir_label = QLabel("処理対象フォルダー:")
        self.input_dir_label.setStyleSheet("font-size: 18px; color: #FFFFFF;")
        self.input_dir_line_edit = QLineEdit()
        self.input_dir_line_edit.setStyleSheet("font-size: 16px; color: #FFFFFF; background-color: #2E2E2E; border: none; padding: 5px;")
        self.browse_button = QPushButton("参照")
        self.browse_button.setStyleSheet("""
            QPushButton {
                font-size: 16px; 
                color: #FFFFFF; 
                background-color: #FF9800; 
                border: none;
                padding: 10px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #FB8C00;
            }
        """)
        self.browse_button.clicked.connect(self.browse_input_directory)
        input_dir_layout.addWidget(self.input_dir_label)
        input_dir_layout.addWidget(self.input_dir_line_edit)
        input_dir_layout.addWidget(self.browse_button)
        self.main_area_layout.addLayout(input_dir_layout)

        # Start processing button
        self.start_button = QPushButton("処理開始")
        self.start_button.setStyleSheet("""
            QPushButton {
                font-size: 18px; 
                padding: 10px; 
                color: #FFFFFF; 
                background-color: #009688; 
                border: none;
                border-radius: 10px;
            }
            QPushButton:hover {
                background-color: #00796B;
            }
        """)
        self.start_button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.start_button.setMaximumWidth(200)  # Set a maximum width
        self.start_button.clicked.connect(self.start_processing)
        self.main_area_layout.addWidget(self.start_button, alignment=Qt.AlignLeft)

        # Open external app button
        self.open_external_app_button = QPushButton("動画再生APPを開く")
        self.open_external_app_button.setStyleSheet("""
            QPushButton {
                font-size: 18px; 
                color: #FFFFFF; 
                background-color: #9C27B0; 
                border: none;
                padding: 10px;
                border-radius: 10px;
            }
            QPushButton:hover {
                background-color: #7B1FA2;
            }
        """)
        self.open_external_app_button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.open_external_app_button.setMaximumWidth(200)  # Set a maximum width
        self.open_external_app_button.clicked.connect(self.open_external_application)
        self.main_area_layout.addWidget(self.open_external_app_button, alignment=Qt.AlignLeft)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("%v/%m")
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: rgba(62,62,62,255);
                border: none;
                color: #f0f0f0;
                text-align: center;
                height: 30px;
                border-radius: 5px;
            }
            QProgressBar::chunk {
                background-color: #4CAF50;
                border-radius: 5px;
            }
        """)
        self.progress_bar.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.progress_bar.setMaximumWidth(400)
        self.main_area_layout.addWidget(self.progress_bar, alignment=Qt.AlignLeft)

        # Show logs label
        self.show_logs_label = QLabel("<a href='#'>ログを表示</a>")
        self.show_logs_label.setOpenExternalLinks(False)
        self.show_logs_label.linkActivated.connect(self.toggle_logs)
        self.show_logs_label.setStyleSheet("font-size: 18px; color: #FFFFFF;")
        self.main_area_layout.addWidget(self.show_logs_label, alignment=Qt.AlignLeft)

        # Log text edit
        self.log_text_edit = QTextEdit()
        self.log_text_edit.setReadOnly(True)
        self.log_text_edit.hide()  # Initially hidden
        self.log_text_edit.setStyleSheet("""
            QTextEdit {
                background-color: #2E2E2E;
                color: #FFFFFF;
                border: 1px solid #4E4E4E;
                border-radius: 5px;
                font-size: 14px;
            }
        """)
        self.log_text_edit.setFixedHeight(200)  # Set a fixed height
        self.main_area_layout.addWidget(self.log_text_edit)

        # Apply styles
        self.applyStyles()

    def initSettingsPanel(self):
        # Use a QScrollArea to keep the settings panel size consistent
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        settings_content = QWidget()
        settings_layout = QVBoxLayout(settings_content)
        settings_layout.setSpacing(10)  # Consistent spacing between rows
        scroll_area.setWidget(settings_content)

        # Settings widgets
        self.frame_interval_label = QLabel("コマ間隔 (コマ何枚に１枚処理するか):")
        self.frame_interval_spinbox = QSpinBox()
        self.frame_interval_spinbox.setRange(1, 1000)
        self.frame_interval_spinbox.setValue(16)

        self.confidence_threshold_label = QLabel("確信度のしきい値:")
        self.confidence_threshold_spinbox = QDoubleSpinBox()
        self.confidence_threshold_spinbox.setRange(0.0, 1.0)
        self.confidence_threshold_spinbox.setSingleStep(0.01)
        self.confidence_threshold_spinbox.setValue(0.4)

        self.processing_duration_label = QLabel("動画の何秒まで処理:")
        self.processing_duration_spinbox = QSpinBox()
        self.processing_duration_spinbox.setRange(1, 3600)
        self.processing_duration_spinbox.setValue(5)

        self.create_detection_data_checkbox = QCheckBox("'detection_data'フォルダーを作成する")
        self.create_detection_data_checkbox.setChecked(False)

        self.delete_no_detection_checkbox = QCheckBox("認識情報がない動画を削除する")
        self.delete_no_detection_checkbox.setChecked(False)

        self.save_all_checkbox = QCheckBox("すべてのフレームを保存")
        self.save_all_checkbox.setChecked(False)

        self.rename_files_checkbox = QCheckBox("タグで動画・画像の名前を変更")
        self.rename_files_checkbox.setChecked(False)

        self.hito_prefix_label = QLabel("人・車のタグ:")
        self.hito_prefix_line_edit = QLineEdit()
        self.hito_prefix_line_edit.setText("hito_")

        self.animal_prefix_label = QLabel("鳥以外の動物のタグ:")
        self.animal_prefix_line_edit = QLineEdit()
        self.animal_prefix_line_edit.setText("nekokamo_")

        # Remove prefixes button
        self.remove_prefixes_button = QPushButton("すべてのファイル名からタグを消す")
        self.remove_prefixes_button.clicked.connect(self.remove_prefixes_from_files)
        self.remove_prefixes_button.setStyleSheet("""
            QPushButton {
                font-size: 16px; 
                color: #FFFFFF; 
                background-color: #FF4081; 
                border: none;
                border-radius: 10px;
                padding: 10px;
            }
            QPushButton:hover {
                background-color: #F50057;
            }
        """)
        self.remove_prefixes_button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.remove_prefixes_button.setMaximumWidth(250)

        # Apply styles to settings widgets
        settings_widgets = [
            self.frame_interval_label, self.frame_interval_spinbox,
            self.confidence_threshold_label, self.confidence_threshold_spinbox,
            self.processing_duration_label, self.processing_duration_spinbox,
            self.create_detection_data_checkbox, self.delete_no_detection_checkbox,
            self.save_all_checkbox, self.rename_files_checkbox,
            self.hito_prefix_label, self.hito_prefix_line_edit,
            self.animal_prefix_label, self.animal_prefix_line_edit,
            self.remove_prefixes_button
        ]

        for widget in settings_widgets:
            widget.setStyleSheet("font-size: 16px; color: #FFFFFF;")
            settings_layout.addWidget(widget)

        # Add the scroll area to the settings panel
        self.settings_panel_layout.addWidget(scroll_area)

    def applyStyles(self):
        # Set the main window's background color
        self.setStyleSheet("background-color: #1E1E1E;")
        # Set fonts and colors globally if needed

    def toggle_settings_panel(self):
        if self.settings_panel.isVisible():
            self.settings_panel.hide()
        else:
            self.settings_panel.show()

    def toggle_language(self):
        # Rotate through available languages
        self.current_language_index = (self.current_language_index + 1) % len(self.languages)
        self.language = self.languages[self.current_language_index]
        self.update_language()

    def update_language(self):
        # Define translations for each language
        translations = {
            'Japanese': {
                'input_dir_label': "処理対象フォルダー:",
                'browse_button': "参照",
                'start_button': "処理開始",
                'open_external_app_button': "動画再生APPを開く",
                'show_logs_label_show': "<a href='#'>ログを表示</a>",
                'show_logs_label_hide': "<a href='#'>ログを隠す</a>",
                'frame_interval_label': "コマ間隔 (コマ何枚に１枚処理するか):",
                'confidence_threshold_label': "確信度のしきい値:",
                'processing_duration_label': "動画の何秒まで処理:",
                'create_detection_data_checkbox': "'detection_data'フォルダーを作成する",
                'delete_no_detection_checkbox': "認識情報がない動画を削除する",
                'save_all_checkbox': "すべてのフレームを保存",
                'rename_files_checkbox': "タグで動画・画像の名前を変更",
                'hito_prefix_label': "人・車のタグ:",
                'animal_prefix_label': "鳥以外の動物のタグ:",
                'remove_prefixes_button': "すべてのファイル名からタグを消す",
                'select_input_folder': "処理対象フォルダーを選択"
            },
            'Spanish': {
                'input_dir_label': "Carpeta de entrada:",
                'browse_button': "Examinar",
                'start_button': "Iniciar procesamiento",
                'open_external_app_button': "Abrir reproductor de videos",
                'show_logs_label_show': "<a href='#'>Mostrar registros</a>",
                'show_logs_label_hide': "<a href='#'>Ocultar registros</a>",
                'frame_interval_label': "Intervalo de cuadros:",
                'confidence_threshold_label': "Umbral de confianza:",
                'processing_duration_label': "Procesar videos hasta (segundos):",
                'create_detection_data_checkbox': "Crear carpeta 'detection_data'",
                'delete_no_detection_checkbox': "Eliminar videos sin detecciones",
                'save_all_checkbox': "Guardar todos los cuadros",
                'rename_files_checkbox': "Renombrar archivos con etiquetas",
                'hito_prefix_label': "Etiqueta para humanos/vehículos:",
                'animal_prefix_label': "Etiqueta para animales no aves:",
                'remove_prefixes_button': "Eliminar etiquetas de nombres de archivos",
                'select_input_folder': "Seleccionar carpeta de entrada"
            },
            'Chinese': {
                'input_dir_label': "输入文件夹:",
                'browse_button': "浏览",
                'start_button': "开始处理",
                'open_external_app_button': "打开视频播放器",
                'show_logs_label_show': "<a href='#'>显示日志</a>",
                'show_logs_label_hide': "<a href='#'>隐藏日志</a>",
                'frame_interval_label': "帧间隔:",
                'confidence_threshold_label': "置信度阈值:",
                'processing_duration_label': "处理视频时长 (秒):",
                'create_detection_data_checkbox': "创建'detection_data'文件夹",
                'delete_no_detection_checkbox': "删除没有检测的文件",
                'save_all_checkbox': "保存所有帧",
                'rename_files_checkbox': "用标签重命名文件",
                'hito_prefix_label': "人/车辆标签:",
                'animal_prefix_label': "非鸟类动物标签:",
                'remove_prefixes_button': "从文件名中删除标签",
                'select_input_folder': "选择输入文件夹"
            },
            'English': {
                'input_dir_label': "Input Folder:",
                'browse_button': "Browse",
                'start_button': "Start Processing",
                'open_external_app_button': "Open Video Player App",
                'show_logs_label_show': "<a href='#'>Show Logs</a>",
                'show_logs_label_hide': "<a href='#'>Hide Logs</a>",
                'frame_interval_label': "Frame Interval:",
                'confidence_threshold_label': "Confidence Threshold:",
                'processing_duration_label': "Process Videos Up To (seconds):",
                'create_detection_data_checkbox': "Create 'detection_data' Folder",
                'delete_no_detection_checkbox': "Delete Videos Without Detections",
                'save_all_checkbox': "Save All Frames",
                'rename_files_checkbox': "Rename Files with Tags",
                'hito_prefix_label': "Human/Vehicle Tag:",
                'animal_prefix_label': "Non-Bird Animal Tag:",
                'remove_prefixes_button': "Remove Tags from All File Names",
                'select_input_folder': "Select Input Folder"
            },
            'Korean': {
                'input_dir_label': "입력 폴더:",
                'browse_button': "찾아보기",
                'start_button': "처리 시작",
                'open_external_app_button': "비디오 플레이어 앱 열기",
                'show_logs_label_show': "<a href='#'>로그 보기</a>",
                'show_logs_label_hide': "<a href='#'>로그 숨기기</a>",
                'frame_interval_label': "프레임 간격:",
                'confidence_threshold_label': "신뢰도 임계값:",
                'processing_duration_label': "비디오 처리 시간 (초):",
                'create_detection_data_checkbox': "'detection_data' 폴더 생성",
                'delete_no_detection_checkbox': "감지되지 않은 비디오 삭제",
                'save_all_checkbox': "모든 프레임 저장",
                'rename_files_checkbox': "태그로 파일 이름 바꾸기",
                'hito_prefix_label': "사람/차량 태그:",
                'animal_prefix_label': "새가 아닌 동물 태그:",
                'remove_prefixes_button': "모든 파일 이름에서 태그 제거",
                'select_input_folder': "입력 폴더 선택"
            }
        }

        # Get the translation dictionary for the current language
        trans = translations.get(self.language, translations['English'])  # Default to English

        # Update labels and texts
        self.input_dir_label.setText(trans['input_dir_label'])
        self.browse_button.setText(trans['browse_button'])
        self.start_button.setText(trans['start_button'])
        self.open_external_app_button.setText(trans['open_external_app_button'])
        if self.log_text_edit.isVisible():
            self.show_logs_label.setText(trans['show_logs_label_hide'])
        else:
            self.show_logs_label.setText(trans['show_logs_label_show'])
        self.frame_interval_label.setText(trans['frame_interval_label'])
        self.confidence_threshold_label.setText(trans['confidence_threshold_label'])
        self.processing_duration_label.setText(trans['processing_duration_label'])
        self.create_detection_data_checkbox.setText(trans['create_detection_data_checkbox'])
        self.delete_no_detection_checkbox.setText(trans['delete_no_detection_checkbox'])
        self.save_all_checkbox.setText(trans['save_all_checkbox'])
        self.rename_files_checkbox.setText(trans['rename_files_checkbox'])
        self.hito_prefix_label.setText(trans['hito_prefix_label'])
        self.animal_prefix_label.setText(trans['animal_prefix_label'])
        self.remove_prefixes_button.setText(trans['remove_prefixes_button'])
        self.select_input_folder_text = trans['select_input_folder']

    def toggle_logs(self):
        if self.log_text_edit.isVisible():
            self.log_text_edit.hide()
        else:
            self.log_text_edit.show()
        self.update_language()  # Update the show/hide logs text based on visibility

    def browse_input_directory(self):
        dir_name = QFileDialog.getExistingDirectory(self, self.select_input_folder_text, "")
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

        # Use settings variables
        every_n_frames = self.frame_interval_spinbox.value()
        confidence_threshold = self.confidence_threshold_spinbox.value()
        create_detection_data = self.create_detection_data_checkbox.isChecked()
        delete_no_detection = self.delete_no_detection_checkbox.isChecked()
        processing_duration_seconds = self.processing_duration_spinbox.value()
        save_all_checkbox = self.save_all_checkbox.isChecked()
        rename_files_checkbox = self.rename_files_checkbox.isChecked()

        # Get user-defined prefixes
        hito_prefix = self.hito_prefix_line_edit.text()
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
            processing_duration_seconds=processing_duration_seconds,
            save_all_checkbox=save_all_checkbox,
            rename_files_checkbox=rename_files_checkbox,
            hito_prefix=hito_prefix,
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
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(processed)
        self.progress_bar.setFormat(f"{processed}/{total}")
        self.log(f"Progress: {processed}/{total}")

    def processing_finished(self):
        self.log("Processing complete")
        self.start_button.setEnabled(True)

    def open_external_application(self):
        """
        Opens the external application specified by the path.
        Passes the selected folder as an argument if one is selected.
        """
        script_path = r"C:\yamaneko-kenkyu\animal-detection\exclusive_player\video_player.py"  # Adjust the path
        python_executable = sys.executable  # Path to the current Python interpreter

        # Get the selected folder path from the input field
        input_folder = self.input_dir_line_edit.text()

        # Build the command arguments
        if input_folder and os.path.isdir(input_folder):
            args = [python_executable, script_path, input_folder]
            self.log(f"Opening external application with folder: {input_folder}")
        else:
            args = [python_executable, script_path]
            self.log(f"Opening external application without folder argument.")

        try:
            subprocess.Popen(args, cwd=os.path.dirname(script_path))
            self.log(f"Opened external application: {script_path}")
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

        # Get user-defined prefixes from settings variables
        hito_prefix = self.hito_prefix_line_edit.text()
        animal_prefix = self.animal_prefix_line_edit.text()
        prefixes = [hito_prefix, animal_prefix]

        # Confirm renaming
        message_box = QMessageBox(self)
        message_box.setWindowTitle("Confirm Prefix Removal")
        message_box.setText(f"This will remove the prefixes {prefixes} from file names in the selected folder.\nAre you sure you want to proceed?")
        message_box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        message_box.setStyleSheet("""
            QMessageBox {
                background-color: #2E2E2E;
                color: #FFFFFF;
            }
            QLabel {
                color: #FFFFFF;
            }
            QPushButton {
                font-size: 16px;
                padding: 5px;
                border-radius: 5px;
                background-color: #3A3A3A;
                color: #FFFFFF;
            }
            QPushButton:hover {
                background-color: #4A4A4A;
            }
        """)

        reply = message_box.exec_()

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

if __name__ == '__main__':
    app = QApplication(sys.argv)

    # Apply custom font if desired
    font = QFont("Segoe UI", 10)
    app.setFont(font)

    # Adjust application palette for better contrast
    palette = QPalette()
    palette.setColor(QPalette.WindowText, QColor(240, 240, 240))
    palette.setColor(QPalette.Button, QColor(53, 53, 53))
    palette.setColor(QPalette.Light, QColor(180, 180, 180))
    palette.setColor(QPalette.Midlight, QColor(90, 90, 90))
    palette.setColor(QPalette.Dark, QColor(35, 35, 35))
    palette.setColor(QPalette.Text, QColor(240, 240, 240))
    palette.setColor(QPalette.BrightText, QColor(240, 240, 240))
    palette.setColor(QPalette.ButtonText, QColor(240, 240, 240))
    palette.setColor(QPalette.Base, QColor(42, 42, 42))
    palette.setColor(QPalette.Window, QColor(53, 53, 53))
    palette.setColor(QPalette.Shadow, QColor(20, 20, 20))
    palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
    palette.setColor(QPalette.HighlightedText, QColor(240, 240, 240))
    app.setPalette(palette)

    window = VideoDetectionApp()
    window.showMaximized()  # Show the window maximized for full-screen experience
    sys.exit(app.exec_())
