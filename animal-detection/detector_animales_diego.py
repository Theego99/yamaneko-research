import sys
import os
import cv2
import json
import shutil
import tempfile
from PyQt5.QtWidgets import (
    QApplication, QWidget, QMainWindow, QFileDialog, QLabel, QLineEdit,
    QPushButton, QVBoxLayout, QHBoxLayout, QSpinBox, QDoubleSpinBox, QCheckBox,
    QTextEdit, QProgressBar
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
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
    print(f"{output_path}に認識ボックスを保存しました")

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
        self.setWindowTitle("動画　ー　動物認識・処理")
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

        self.include_category_0_2_checkbox = QCheckBox("人や車が映った動画を残す ( 'hito_ + 元の名前'で名前を変更)")
        self.include_category_0_2_checkbox.setChecked(False)
        
        self.save_all_checkbox = QCheckBox("Save all detections")
        self.save_all_checkbox.setChecked(False)

        self.start_button = QPushButton("処理開始")
        self.start_button.clicked.connect(self.start_processing)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("%v/%m")  # Set initial format to show current/maximum

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
        layout.addWidget(self.include_category_0_2_checkbox)
        layout.addWidget(self.save_all_checkbox)
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
            self.log("処理対象フォルダーを選択してください")
            return
        if not os.path.isdir(input_folder):
            self.log("選択されたフォルダーは存在しません")
            return
        every_n_frames = self.frame_interval_spinbox.value()
        confidence_threshold = self.confidence_threshold_spinbox.value()
        create_detection_data = self.create_detection_data_checkbox.isChecked()
        delete_no_detection = self.delete_no_detection_checkbox.isChecked()
        include_category_0_2 = self.include_category_0_2_checkbox.isChecked()
        processing_duration_seconds = self.processing_duration_spinbox.value()  # *** Retrieve New Parameter ***
        save_all_checkbox = self.save_all_checkbox.isChecked()

        # Disable the start button to prevent multiple clicks
        self.start_button.setEnabled(False)
        # Reset progress bar
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("%v/%m ")  # Reset format

        # Start the processing in a separate thread
        self.processing_thread = ProcessingThread(
            input_folder=input_folder,
            every_n_frames=every_n_frames,
            confidence_threshold=confidence_threshold,
            create_detection_data=create_detection_data,
            delete_no_detection=delete_no_detection,
            include_category_0_2=include_category_0_2,
            save_all_checkbox = self.save_all_checkbox,
            processing_duration_seconds=processing_duration_seconds  # *** Pass New Parameter ***
        )
        # Connect signals
        self.processing_thread.log_signal.connect(self.log)
        self.processing_thread.progress_signal.connect(self.update_progress)
        self.processing_thread.finished.connect(self.processing_finished)
        self.processing_thread.start()

    def log(self, message):
        self.log_text_edit.append(message)

    def update_progress(self, processed, total):
        print("processed ",processed)
        """
        Update the progress bar with the number of processed videos and total videos.
        """
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(processed)
        # The format "%v/%m" will automatically display "processed/total"
        # Ensure that the format is set correctly
        self.progress_bar.setFormat(f"{processed}/{total}")

    def processing_finished(self):
        self.log("処理完了")
        self.start_button.setEnabled(True)

class ProcessingThread(QThread):
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int, int)  # *** Updated to emit processed and total ***

    finished = pyqtSignal()

    def __init__(
        self, input_folder, every_n_frames, confidence_threshold,
        create_detection_data, delete_no_detection, include_category_0_2,
        processing_duration_seconds  # *** New Parameter ***
    ):
        super().__init__()
        self.input_folder = input_folder
        self.every_n_frames = every_n_frames
        self.confidence_threshold = confidence_threshold
        self.create_detection_data = create_detection_data
        self.delete_no_detection = delete_no_detection
        self.include_category_0_2 = include_category_0_2
        self.processing_duration_seconds = processing_duration_seconds  # *** Store New Parameter ***

    def run(self):
        # Main processing code goes here
        self.process_videos()
        self.finished.emit()

    def log(self, message):
        self.log_signal.emit(message)

    def update_progress(self, processed, total):
        self.progress_signal.emit(processed, total)

    def process_videos(self):
        input_folder = self.input_folder
        every_n_frames = self.every_n_frames
        confidence_threshold = self.confidence_threshold
        create_detection_data = self.create_detection_data
        delete_no_detection = self.delete_no_detection
        include_category_0_2 = self.include_category_0_2
        processing_duration_seconds = self.processing_duration_seconds  # *** Use New Parameter ***

        if create_detection_data:
            output_base = os.path.join(input_folder, "detection_data")
            tracking_file = os.path.join(output_base, 'video_confidence_tracking.json')

            # Create output directory
            os.makedirs(output_base, exist_ok=True)
            self.log(f"出力データを {output_base}　に保存します")

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
            self.log("選択されたフォルダーに処理対象の .MOV　動画が見つかりませんでした")
            return

        total_videos = len(video_paths)
        self.log(f"\n {total_videos} 本の動画が見つかりました　\n")

        # Emit initial progress
        self.update_progress(processed_videos, total_videos)

        

        def process_video(video_path):
            global processed_videos
            processed_videos += 1
            self.update_progress(processed_videos, total_videos)  # *** Emit progress with processed and total ***
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                self.log(f"動画 {video_path} を開くことができませんでした")
                return

            fps = cap.get(cv2.CAP_PROP_FPS)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            duration_seconds = total_frames / fps
            max_frames = int(processing_duration_seconds * fps)

            self.log(f"動画のFPS: {fps}, 総フレーム数: {total_frames}, 処理する最大フレーム数: {max_frames}")

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

                # Check if we've reached the maximum frames to process
                if frame_count > max_frames:
                    self.log(f"{processing_duration_seconds}秒に達したため、{video_path}の処理を終了します")
                    break

                if frame_count % every_n_frames == 0:
                    frame_filename = os.path.join(temp_dir, f'frame_{frame_count}.jpg')
                    cv2.imwrite(frame_filename, frame)
                    frame_files.append(frame_filename)
                    frame_indices.append(frame_count)

            cap.release()

            if not frame_files:
                self.log(f"{video_path}に処理するコマがありません")
                shutil.rmtree(temp_dir)
                if delete_no_detection:
                    try:
                        os.remove(video_path)
                        self.log(f"動物を認識できなかったため、 {video_path}を削除します")
                    except Exception as e:
                        self.log(f"{video_path}の削除エラー: {e}")
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
                    self.log(f" {frame_filename}のコマを読み込めませんでした")
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
                                
            if best_detection is None and not (include_category_0_2 and category_0_2_detected):
                self.log(f"{video_path}に有効な認識データがありません")
                shutil.rmtree(temp_dir)
                if delete_no_detection:
                    try:
                        os.remove(video_path)
                        self.log(f"{video_path}認識データなかったため、削除しました")
                    except Exception as e:
                        self.log(f"{video_path}の削除エラー: {e}")
                return

            # Update tracking data
            if create_detection_data:
                video_confidence_dict[video_path] = max_confidence_detection

            # Determine prefix based on detection condition
            if category_0_2_detected and include_category_0_2:
                prefix = ""#hito_
                best_detection = best_detection_0_2
                best_frame = best_frame_0_2
                best_frame_detections = best_frame_detections_0_2
            elif detection_in_upper_small:
                prefix = ""#tori_
            else:
                prefix = ""#nekokamo_

            # Rename the original video file
            video_dir = os.path.dirname(video_path)
            video_name = os.path.basename(video_path)
            new_video_name = prefix + video_name
            new_video_path = os.path.join(video_dir, new_video_name)

            # Check if the new video name already exists
            if os.path.exists(new_video_path):
                self.log(f"{new_video_path} フォルダーはすでに存在します。{video_path}の名前を変更できません")
            else:
                try:
                    os.rename(video_path, new_video_path)
                    self.log(f"{video_path} を {new_video_path}に名前変更しました")
                except Exception as e:
                    self.log(f"{video_path}の名前変更エラー: {e}")

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
                self.log(f"{cropped_image_path}に切り取られた画像を保存しました")

            # Clean up temporary files
            shutil.rmtree(temp_dir)

        def save_video_confidence_dict():
            if create_detection_data:
                with open(tracking_file, 'w') as f:
                    json.dump(video_confidence_dict, f, indent=2)
                self.log(f"動画の確信度データを{tracking_file}に保存しました")

        # Process each video
        for video_path in video_paths:
            print(processed_videos)
            self.log(f"{video_path}を処理中...")
            process_video(video_path)
            self.log("-" * 50)

        # Save the video confidence tracking file
        save_video_confidence_dict()
        self.log("\n=== 処理完了 ===")
        # Ensure progress bar is at 100% after processing
        self.update_progress(total_videos, total_videos)  # *** Set progress to total ***

    # Removed duplicate progress update from process_video

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = VideoDetectionApp()
    window.show()
    sys.exit(app.exec_())
