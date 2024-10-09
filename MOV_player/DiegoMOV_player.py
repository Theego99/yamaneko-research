import sys
import os
import vlc
from PyQt5 import QtWidgets
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QFileDialog, QVBoxLayout, QHBoxLayout, QComboBox, QPushButton, QLabel, QWidget

class VideoPlayer(QtWidgets.QMainWindow):
    def __init__(self):
        super(VideoPlayer, self).__init__()
        self.setWindowTitle("DiegoMOV プレーヤー")
        self.setGeometry(100, 100, 800, 600)

        # Initialize VLC instance and variables
        self.instance = vlc.Instance()
        self.media_player = self.instance.media_player_new()
        self.current_folder = ""
        self.video_files = []
        self.current_video_index = -1

        # Set up UI components
        self.init_ui()

    def init_ui(self):
        # Video frame widget
        self.video_frame = QtWidgets.QFrame(self)
        self.setCentralWidget(self.video_frame)

        # Controls layout
        controls_layout = QHBoxLayout()
        self.open_button = QPushButton("ビデオを開く")
        self.open_button.clicked.connect(self.open_file)
        controls_layout.addWidget(self.open_button)

        self.prev_button = QPushButton("前のビデオ")
        self.prev_button.clicked.connect(self.prev_video)
        controls_layout.addWidget(self.prev_button)

        self.play_pause_button = QPushButton("再生/一時停止")
        self.play_pause_button.clicked.connect(self.play_pause)
        controls_layout.addWidget(self.play_pause_button)

        self.next_button = QPushButton("次のビデオ")
        self.next_button.clicked.connect(self.next_video)
        controls_layout.addWidget(self.next_button)

        # Speed control
        self.speed_label = QLabel("再生速度:")
        controls_layout.addWidget(self.speed_label)

        self.speed_combo = QComboBox(self)
        self.speed_combo.addItems([str(i / 2) for i in range(2, 11)])
        self.speed_combo.currentTextChanged.connect(self.change_speed)
        controls_layout.addWidget(self.speed_combo)

        # Main layout
        layout = QVBoxLayout()
        layout.addWidget(self.video_frame)
        layout.addLayout(controls_layout)

        # Container widget to apply layout
        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

        # VLC widget for video output
        if sys.platform == "darwin":
            self.media_player.set_nsobject(int(self.video_frame.winId()))
        elif sys.platform == "win32":
            self.media_player.set_hwnd(int(self.video_frame.winId()))
        else:
            self.media_player.set_xwindow(int(self.video_frame.winId()))

    def open_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "ビデオファイルを選択", "", "ビデオファイル (*.mp4 *.avi *.mov *.mkv)")
        if file_path:
            self.current_folder = os.path.dirname(file_path)
            self.load_videos_from_folder()
            self.current_video_index = self.video_files.index(file_path)
            self.play_video()

    def load_videos_from_folder(self):
        # Get all video files in the folder, sorted alphabetically
        self.video_files = sorted(
            [
                os.path.join(self.current_folder, f)
                for f in os.listdir(self.current_folder)
                if f.lower().endswith((".mp4", ".avi", ".mov", ".mkv"))
            ]
        )

    def play_video(self):
        if self.video_files and self.current_video_index >= 0:
            video_path = self.video_files[self.current_video_index]
            media = self.instance.media_new(video_path)
            self.media_player.set_media(media)
            self.media_player.play()

            # Update the window title with the video name
            video_name = os.path.basename(video_path)
            self.setWindowTitle(f"DiegoMOV プレーヤー - {video_name}")

    def play_pause(self):
        if self.media_player.is_playing():
            self.media_player.pause()
        else:
            self.media_player.play()

    def prev_video(self):
        if self.current_video_index > 0:
            self.current_video_index -= 1
            self.play_video()

    def next_video(self):
        if self.current_video_index < len(self.video_files) - 1:
            self.current_video_index += 1
            self.play_video()

    def change_speed(self, speed_text):
        speed = float(speed_text)
        self.media_player.set_rate(speed)

app = QtWidgets.QApplication(sys.argv)
player = VideoPlayer()
player.show()
sys.exit(app.exec_())
