import sys
import os
import ctypes
import logging

from PyQt5 import QtWidgets, QtGui, QtCore
from PyQt5.QtWidgets import (
    QFileDialog,
    QVBoxLayout,
    QHBoxLayout,
    QComboBox,
    QPushButton,
    QLabel,
    QWidget,
    QMessageBox
)

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    filename='app.log',
    filemode='w',
    format='%(asctime)s - %(levelname)s - %(message)s'
)

try:
    # Determine the base path
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
        logging.debug("Running in a bundled executable.")
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
        logging.debug("Running in development mode.")

    # VLC directory within your application
    vlc_path = os.path.join(base_path, 'vlc')
    logging.debug(f"VLC path set to: {vlc_path}")

    # Path to libvlc.dylib
    libvlc_lib = os.path.join(vlc_path, 'libvlc.dylib')
    logging.debug(f"libvlc library path set to: {libvlc_lib}")

    # Set environment variables for VLC
    os.environ['PYTHON_VLC_LIB_PATH'] = vlc_path
    os.environ['VLC_PLUGIN_PATH'] = os.path.join(vlc_path, 'plugins')
    logging.debug(f"Set PYTHON_VLC_LIB_PATH: {vlc_path}")
    logging.debug(f"Set VLC_PLUGIN_PATH: {os.environ['VLC_PLUGIN_PATH']}")

    # Try loading libvlc.dylib to check for missing dependencies
    try:
        ctypes.CDLL(libvlc_lib)
        logging.debug(f"Successfully loaded {libvlc_lib}")
    except OSError as e:
        logging.error(f"Failed to load {libvlc_lib}: {e}")
        sys.exit(1)

except Exception as e:
    logging.exception("An unexpected error occurred during initialization.")
    sys.exit(1)

# Now import vlc
import vlc

class VideoPlayer(QtWidgets.QMainWindow):
    def __init__(self):
        super(VideoPlayer, self).__init__()
        self.setWindowTitle("DiegoMOV プレーヤー")
        self.setGeometry(100, 100, 800, 600)

        try:
            # Determine the base path
            if getattr(sys, 'frozen', False):
                base_path = sys._MEIPASS
                logging.debug("Running in a bundled executable.")
            else:
                base_path = os.path.dirname(os.path.abspath(__file__))
                logging.debug("Running in development mode.")

            # Path to the icon file
            icon_path = os.path.join(base_path, 'assets', 'app_icon.icns')
            self.setWindowIcon(QtGui.QIcon(icon_path))

            # VLC directory
            vlc_path = os.path.join(base_path, 'vlc')
            logging.debug(f"VLC path set to: {vlc_path}")

            # Path to libvlc.dylib
            libvlc_path = os.path.join(vlc_path, 'libvlc.dylib')
            logging.debug(f"libvlc library path set to: {libvlc_path}")

            # Check if libvlc.dylib exists
            if not os.path.exists(libvlc_path):
                error_msg = f"libvlc.dylib not found at {libvlc_path}. Please ensure the VLC directory is bundled correctly."
                logging.error(error_msg)
                QMessageBox.critical(
                    self,
                    "VLC Library Not Found",
                    error_msg
                )
                sys.exit(1)

            # Load libvlc.dylib using ctypes
            try:
                ctypes.CDLL(libvlc_path)
                logging.debug(f"Successfully loaded libvlc.dylib from {libvlc_path}")
            except Exception as e:
                error_msg = f"Failed to load libvlc.dylib: {e}"
                logging.error(error_msg)
                QMessageBox.critical(
                    self,
                    "Failed to Load VLC Library",
                    error_msg
                )
                sys.exit(1)

            # Set the VLC plugin path environment variable
            plugins_path = os.path.join(vlc_path, 'plugins')
            os.environ['VLC_PLUGIN_PATH'] = plugins_path
            logging.debug(f"VLC_PLUGIN_PATH set to: {plugins_path}")

            # Initialize VLC instance with the plugin path
            try:
                self.instance = vlc.Instance(['--no-xlib', f'--plugin-path={plugins_path}'])
                if self.instance is None:
                    raise ValueError("vlc.Instance() returned None.")
                logging.debug("VLC Instance created successfully.")
            except Exception as e:
                error_msg = f"Failed to create VLC Instance: {e}"
                logging.error(error_msg)
                QMessageBox.critical(
                    self,
                    "VLC Initialization Error",
                    error_msg
                )
                sys.exit(1)

            # Initialize media player
            try:
                self.media_player = self.instance.media_player_new()
                if self.media_player is None:
                    raise ValueError("Failed to create media player.")
                logging.debug("Media player initialized successfully.")
            except Exception as e:
                error_msg = f"Failed to create media player: {e}"
                logging.error(error_msg)
                QMessageBox.critical(
                    self,
                    "Media Player Initialization Error",
                    error_msg
                )
                sys.exit(1)

            self.current_folder = ""
            self.video_files = []
            self.current_video_index = -1

            # Set up UI components
            self.init_ui()

            # Handle command-line arguments
            # On macOS, files opened via double-clicking are sent via FileOpen events
            # We'll handle that in a custom QApplication subclass
            if len(sys.argv) > 1:
                file_path = sys.argv[1]
                if os.path.isfile(file_path):
                    self.open_file(file_path)
                else:
                    logging.warning(f"File does not exist: {file_path}")
            else:
                logging.debug("No command-line arguments provided.")

        except Exception as e:
            error_msg = f"An unexpected error occurred during initialization: {e}"
            logging.exception(error_msg)
            QMessageBox.critical(
                self,
                "Initialization Error",
                error_msg
            )
            sys.exit(1)

    def init_ui(self):
        # Video frame widget
        self.video_frame = QtWidgets.QFrame(self)
        self.setCentralWidget(self.video_frame)

        # Controls layout
        controls_layout = QHBoxLayout()

        # Open Button
        self.open_button = QPushButton("ビデオを開く")
        self.open_button.clicked.connect(self.open_file)
        self.open_button.setFixedHeight(50)
        controls_layout.addWidget(self.open_button)

        # Previous Button
        self.prev_button = QPushButton("⏪")
        self.prev_button.clicked.connect(self.prev_video)
        self.prev_button.setFixedHeight(50)
        controls_layout.addWidget(self.prev_button)

        # Play/Pause Button
        self.play_pause_button = QPushButton("⏯")
        self.play_pause_button.clicked.connect(self.play_pause)
        self.play_pause_button.setFixedHeight(50)
        controls_layout.addWidget(self.play_pause_button)

        # Replay Button
        self.replay_button = QPushButton("🔁")
        self.replay_button.clicked.connect(self.replay_video)
        self.replay_button.setFixedHeight(50)
        controls_layout.addWidget(self.replay_button)

        # Next Button
        self.next_button = QPushButton("⏭️")
        self.next_button.clicked.connect(self.next_video)
        self.next_button.setFixedHeight(50)
        controls_layout.addWidget(self.next_button)

        # Speed Control Label
        self.speed_label = QLabel("再生速度:")
        self.speed_label.setAlignment(Qt.AlignCenter)
        controls_layout.addWidget(self.speed_label)

        # Speed Control ComboBox
        self.speed_combo = QComboBox(self)
        self.speed_combo.addItems([str(i / 2) for i in range(2, 11)])  # 1.0 to 5.0
        self.speed_combo.setCurrentText("1.0")  # Default speed
        self.speed_combo.currentTextChanged.connect(self.change_speed)
        self.speed_combo.setFixedHeight(50)
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
        self.media_player.set_nsobject(int(self.video_frame.winId()))

    def open_file(self, file_path=None):
        if not file_path:
            file_path, _ = QFileDialog.getOpenFileName(
                self, 
                "ビデオファイルを選択", 
                "", 
                "ビデオファイル (*.mp4 *.avi *.mov *.mkv)"
            )
        if file_path:
            self.current_folder = os.path.dirname(file_path)
            self.load_videos_from_folder()
            normalized_file_path = os.path.normpath(file_path)
            try:
                self.current_video_index = self.video_files.index(normalized_file_path)
                self.play_video()
            except ValueError:
                QtWidgets.QMessageBox.warning(
                    self, 
                    "ファイルが見つかりません", 
                    f"選択したファイルがリストに存在しません:\n{file_path}"
                )

    def load_videos_from_folder(self):
        # Get all video files in the folder, sorted alphabetically
        self.video_files = sorted(
            [
                os.path.normpath(os.path.join(self.current_folder, f))
                for f in os.listdir(self.current_folder)
                if f.lower().endswith((".mp4", ".avi", ".mov", ".mkv"))
            ]
        )
        logging.debug("Loaded video files: %s", self.video_files)  # Debugging statement

    def play_video(self):
        if self.video_files and self.current_video_index >= 0:
            video_path = self.video_files[self.current_video_index]
            media = self.instance.media_new(video_path)
            self.media_player.set_media(media)
            self.media_player.play()

            # Update the window title with the video name
            video_name = os.path.basename(video_path)
            self.setWindowTitle(f"DiegoMOV プレーヤー - {video_name}")
            logging.debug(f"Playing video: {video_path}")  # Debugging statement

    def play_pause(self):
        if self.media_player.is_playing():
            self.media_player.pause()
            logging.debug("Video paused")  # Debugging statement
        else:
            self.media_player.play()
            logging.debug("Video playing")  # Debugging statement

    def prev_video(self):
        if self.current_video_index > 0:
            self.current_video_index -= 1
            logging.debug(f"Switching to previous video: Index {self.current_video_index}")  # Debugging
            self.play_video()

    def next_video(self):
        if self.current_video_index < len(self.video_files) - 1:
            self.current_video_index += 1
            logging.debug(f"Switching to next video: Index {self.current_video_index}")  # Debugging
            self.play_video()

    def replay_video(self):
        logging.debug("Replay button clicked")  # Debugging statement
        if self.media_player.get_media():
            self.media_player.stop()
            self.media_player.play()
            logging.debug("Video replayed using stop() and play()")  # Debugging

    def change_speed(self, speed_text):
        speed = float(speed_text)
        # VLC requires the media to be playing to change speed
        if self.media_player.is_playing():
            self.media_player.set_rate(speed)
            logging.debug(f"Playback speed changed to: {speed}x")  # Debugging statement
        else:
            self.media_player.set_rate(speed)
            self.media_player.play()
            logging.debug(f"Playback speed set to: {speed}x and video playing")  # Debugging

# Custom QApplication to handle file open events on macOS
class MyApplication(QtWidgets.QApplication):
    def __init__(self, *args, **kwargs):
        super(MyApplication, self).__init__(*args, **kwargs)
        self.file_to_open = None

    def event(self, e):
        if e.type() == QtCore.QEvent.FileOpen:
            self.file_to_open = e.file()
            return True
        return super(MyApplication, self).event(e)

if __name__ == "__main__":
    try:
        app = MyApplication(sys.argv)
        
        # Determine the base path
        if getattr(sys, 'frozen', False):
            base_path = sys._MEIPASS
        else:
            base_path = os.path.dirname(os.path.abspath(__file__))
        
        # Path to the icon file
        icon_path = os.path.join(base_path, 'assets', 'app_icon.icns')
        
        # Set the application icon
        app.setWindowIcon(QtGui.QIcon(icon_path))
        
        player = VideoPlayer()
        player.show()

        # Check if there is a file to open (for macOS FileOpen events)
        if app.file_to_open:
            player.open_file(app.file_to_open)

        sys.exit(app.exec_())
    except Exception as e:
        logging.exception("An unexpected error occurred: %s", e)
        input("Press Enter to exit.")
