import sys
import os
import ctypes
import logging
import whisper
import torch
import warnings
import subprocess
from pydub import AudioSegment

from PyQt5 import QtWidgets, QtGui, QtCore
from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QPushButton,
    QLabel,
    QTextEdit,
    QFileDialog,
    QMessageBox,
    QComboBox,
    QProgressBar,
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer

# 特定の警告を抑制してログと出力をクリーンに保つ
warnings.filterwarnings("ignore", category=FutureWarning, module='torch')
warnings.filterwarnings("ignore", category=UserWarning, module='whisper')


def resource_path(relative_path):
    """
    Get absolute path to resource, works for dev and PyInstaller.
    """
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath(".")
    full_path = os.path.join(base_path, relative_path)
    logging.debug(f"Resolved resource path: {full_path}")
    return full_path



class TranscriptionThread(QThread):
    transcription_updated = pyqtSignal(str)
    transcription_started = pyqtSignal()
    transcription_finished = pyqtSignal()
    error_occurred = pyqtSignal(str)

    def __init__(self, model, audio_file, transcription_file, language, chunk_duration=5):
        super().__init__()
        self.model = model
        self.audio_file = audio_file
        self.transcription_file = transcription_file
        self.language = language
        self.chunk_duration = chunk_duration  # チャンクの長さ（秒）

    def run(self):
        try:
            self.transcription_started.emit()
            # 音声ファイルを読み込み
            audio = AudioSegment.from_file(self.audio_file)
            total_duration = len(audio) / 1000.0  # ミリ秒を秒に変換
            num_chunks = int(total_duration // self.chunk_duration) + 1

            transcription_text = ""
            for i in range(num_chunks):
                start_ms = i * self.chunk_duration * 1000
                end_ms = min((i + 1) * self.chunk_duration * 1000, len(audio))
                chunk = audio[start_ms:end_ms]
                chunk_filename = os.path.join(os.path.dirname(self.audio_file), f"temp_chunk_{i}.wav")
                chunk.export(chunk_filename, format="wav")

                # Whisperで文字起こし
                result = self.model.transcribe(
                    chunk_filename,
                    verbose=False,
                    language=self.language  # 言語を指定
                )
                chunk_transcription = result.get("text", "").strip()
                transcription_text += chunk_transcription + " "

                # 一時ファイルを削除
                os.remove(chunk_filename)

                # シグナルを通じてリアルタイムでGUIに送信
                self.transcription_updated.emit(transcription_text.strip())

            # 最終的な文字起こしを保存
            with open(self.transcription_file, 'w', encoding='utf-8') as f:
                f.write(transcription_text.strip())

            self.transcription_finished.emit()
        except Exception as e:
            self.error_occurred.emit(str(e))


class SpeechRecognizerGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Whisper音声認識")
        self.setGeometry(100, 100, 800, 600)
        self.audio_file = ""
        self.transcription_text = ""
        self.model = None
        self.device = "cpu"  # デフォルトデバイス
        self.audio_duration = 0  # 音声ファイルの長さ（秒）
        self.start_time = 0      # 文字起こし開始時刻

        self.init_ui()
        self.setup_logging()
        self.load_ffmpeg()
        self.load_model()

        # タイマーの設定
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_progress_bar)

    def init_ui(self):
        # 音声ファイル選択ボタン
        self.select_button = QPushButton("音声ファイルを選択", self)
        self.select_button.setGeometry(50, 50, 200, 40)
        self.select_button.clicked.connect(self.select_file)

        # モデル選択コンボボックス
        self.model_label = QLabel("モデルを選択:", self)
        self.model_label.setGeometry(50, 110, 100, 30)

        self.model_combo = QComboBox(self)
        self.model_combo.setGeometry(160, 110, 200, 30)
        self.model_combo.addItems(["tiny", "base", "small", "medium", "large"])
        self.model_combo.setCurrentText("tiny")
        self.model_combo.currentTextChanged.connect(self.load_model)

        # 言語選択コンボボックス
        self.language_label = QLabel("言語を選択:", self)
        self.language_label.setGeometry(50, 160, 100, 30)

        self.language_combo = QComboBox(self)
        self.language_combo.setGeometry(160, 160, 200, 30)
        self.language_combo.addItems(["Japanese", "Chinese", "Spanish", "Korean", "English"])
        self.language_combo.setCurrentText("Japanese")  # デフォルトは日本語
        self.language_combo.currentTextChanged.connect(self.change_language)

        # 文字起こしボタン
        self.transcribe_button = QPushButton("文字起こし", self)
        self.transcribe_button.setGeometry(50, 210, 200, 40)
        self.transcribe_button.clicked.connect(self.transcribe_audio)
        self.transcribe_button.setEnabled(False)  # ファイル選択まで無効

        # 文字起こし保存ボタン
        self.save_button = QPushButton("文字起こしを保存", self)
        self.save_button.setGeometry(300, 210, 200, 40)
        self.save_button.clicked.connect(self.save_transcription)
        self.save_button.setEnabled(False)  # 文字起こし完了まで無効

        # プログレスバー
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setGeometry(550, 210, 200, 40)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setAlignment(Qt.AlignCenter)
        self.progress_bar.hide()  # 初期状態では非表示

        # 文字起こし結果表示ラベル
        self.transcription_label = QLabel("文字起こし結果:", self)
        self.transcription_label.setGeometry(50, 270, 200, 30)

        # 文字起こし結果表示テキストエリア
        self.transcription_display = QTextEdit(self)
        self.transcription_display.setGeometry(50, 310, 700, 250)
        self.transcription_display.setReadOnly(True)

    def setup_logging(self):
        log_file = resource_path("app.log")
        logging.basicConfig(
            level=logging.DEBUG,
            filename=log_file,
            filemode='w',
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        logging.debug("Logging initialized.")

    def load_ffmpeg(self):
        """
        Load FFmpeg binaries from the bundled resources.
        """
        try:
            ffmpeg_bin_path = resource_path(os.path.join("ffmpeg", "bin"))
            logging.debug(f"FFmpeg bin path: {ffmpeg_bin_path}")

            # Add FFmpeg bin to PATH
            os.environ['PATH'] = ffmpeg_bin_path + os.pathsep + os.environ.get('PATH', '')
            logging.debug(f"Updated PATH with FFmpeg: {os.environ['PATH']}")

            # Verify ffmpeg.exe exists
            ffmpeg_exe = resource_path(os.path.join("ffmpeg", "bin", "ffmpeg.exe"))
            ffprobe_exe = resource_path(os.path.join("ffmpeg", "bin", "ffprobe.exe"))
            
            logging.debug(f"ffmpeg.exe path: {ffmpeg_exe}")
            logging.debug(f"ffprobe.exe path: {ffprobe_exe}")

            if not os.path.exists(ffmpeg_exe):
                raise FileNotFoundError(f"ffmpeg.exe not found at {ffmpeg_exe}")
            if not os.path.exists(ffprobe_exe):
                raise FileNotFoundError(f"ffprobe.exe not found at {ffprobe_exe}")

            # Test FFmpeg functionality
            result = subprocess.run([ffmpeg_exe, "-version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if result.returncode != 0:
                raise RuntimeError("ffmpeg.exe is not functioning properly.")
            
            logging.debug("FFmpeg loaded successfully.")
        except Exception as e:
            logging.exception("Failed to load FFmpeg.")
            QMessageBox.critical(self, "FFmpeg エラー", f"FFmpeg のロードに失敗しました: {e}")
            sys.exit(1)


    def load_model(self):
        """
        選択された Whisper モデルをロードし、利用可能な場合は GPU を使用します。
        """
        try:
            selected_model = self.model_combo.currentText()
            logging.debug(f"Selected Whisper model: {selected_model}")

            # GPU の利用可能性をチェック
            if torch.cuda.is_available():
                self.device = "cuda"
                logging.debug("CUDA is available. Using GPU for transcription.")
            else:
                self.device = "cpu"
                logging.debug("CUDA not available. Using CPU for transcription.")

            # Whisper モデルをロード
            self.model = whisper.load_model(selected_model, device=self.device)
            logging.debug(f"Whisper model '{selected_model}' loaded successfully on {self.device}.")
        except Exception as e:
            logging.exception("Failed to load Whisper model.")
            QMessageBox.critical(self, "モデルエラー", f"Whisper モデルのロードに失敗しました: {e}")
            sys.exit(1)

    def change_language(self, language):
        """
        ユーザーが選択した言語を設定します。
        """
        self.selected_language = language
        logging.debug(f"Selected language: {self.selected_language}")

    def select_file(self):
        """
        音声ファイルを選択するためのファイルダイアログを開きます。
        """
        options = QFileDialog.Options()
        options |= QFileDialog.ReadOnly
        file_filter = "音声ファイル (*.mp3 *.wav *.m4a *.flac *.aac)"
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "音声ファイルを選択",
            "",
            file_filter,
            options=options
        )
        if file_path:
            self.audio_file = file_path
            self.transcribe_button.setEnabled(True)
            self.transcription_display.clear()
            self.save_button.setEnabled(False)
            self.progress_bar.setValue(0)
            self.progress_bar.hide()
            logging.debug(f"Selected audio file: {self.audio_file}")
            QMessageBox.information(self, "ファイル選択完了", f"選択されたファイル:\n{self.audio_file}")

            # 音声ファイルの長さを取得
            self.audio_duration = self.get_audio_duration(self.audio_file)
            logging.debug(f"Audio duration: {self.audio_duration} seconds")

    def get_audio_duration(self, audio_file):
        """
        ffprobeを使用して音声ファイルの再生時間を取得します。
        """
        try:
            ffprobe_path = resource_path(os.path.join("ffmpeg", "bin", "ffprobe.exe"))
            cmd = [
                ffprobe_path,
                "-v", "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                audio_file
            ]
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            duration = float(result.stdout.strip())
            return duration
        except Exception as e:
            logging.error(f"Failed to get audio duration: {e}")
            return 0

    def transcribe_audio(self):
        """
        文字起こしプロセスを別スレッドで開始します。
        """
        if not self.audio_file:
            QMessageBox.warning(self, "ファイル未選択", "まず音声ファイルを選択してください。")
            return

        if self.audio_duration == 0:
            QMessageBox.warning(self, "音声ファイルエラー", "音声ファイルの長さを取得できませんでした。")
            return

        try:
            # 文字起こしファイル名を自動で設定
            base_name = os.path.splitext(os.path.basename(self.audio_file))[0]
            transcription_file = os.path.join(os.path.dirname(self.audio_file), f"{base_name}.txt")
            logging.debug(f"Transcription will be saved to: {transcription_file}")

            # 文字起こし中はボタンを無効化
            self.transcribe_button.setEnabled(False)
            self.select_button.setEnabled(False)
            self.save_button.setEnabled(False)

            # プログレスバーを表示し、初期化
            self.progress_bar.setValue(0)
            self.progress_bar.setFormat("文字起こし中... 0%")
            self.progress_bar.setMaximum(100)
            self.progress_bar.show()

            # 文字起こし開始時刻を記録
            self.start_time = QtCore.QDateTime.currentDateTime().toMSecsSinceEpoch() / 1000.0  # 秒単位

            # タイマーを開始
            self.timer.start(500)  # 0.5秒ごとに更新

            # 言語選択
            language_map = {
                "Japanese": "ja",
                "Chinese": "zh",
                "Spanish": "es",
                "Korean": "ko",
                "English": "en"
            }
            selected_language = language_map.get(self.language_combo.currentText(), "ja")  # デフォルトは日本語

            # 文字起こしスレッドを開始
            self.thread = TranscriptionThread(
                self.model,
                self.audio_file,
                transcription_file,
                language=selected_language,
                chunk_duration=5
            )
            self.thread.transcription_updated.connect(self.on_transcription_updated)
            self.thread.transcription_started.connect(self.on_transcription_started)
            self.thread.transcription_finished.connect(self.on_transcription_finished)
            self.thread.error_occurred.connect(self.on_error)
            self.thread.start()

            logging.debug("Transcription thread started.")
        except Exception as e:
            logging.exception("Failed to start transcription.")
            QMessageBox.critical(self, "文字起こしエラー", f"文字起こしの開始に失敗しました: {e}")

    def update_progress_bar(self):
        """
        タイマーによって定期的に呼び出され、プログレスバーを更新します。
        """
        current_time = QtCore.QDateTime.currentDateTime().toMSecsSinceEpoch() / 1000.0  # 秒単位
        elapsed_time = current_time - self.start_time
        progress = (elapsed_time / self.audio_duration) * 100
        progress = min(progress, 100)  # 100%を超えないように

        self.progress_bar.setValue(int(progress))
        self.progress_bar.setFormat(f"文字起こし中... {int(progress)}%")

    def on_transcription_started(self):
        """
        文字起こしの開始をハンドルします。
        """
        self.progress_bar.setFormat("文字起こし中... 0%")
        self.progress_bar.setValue(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.show()
        logging.debug("Transcription started.")

    def on_transcription_updated(self, transcription):
        """
        文字起こしの進行中に結果を更新します。
        """
        self.transcription_text = transcription
        self.transcription_display.setPlainText(self.transcription_text)
        logging.debug("Transcription updated.")

    def on_transcription_completed(self, transcription):
        """
        文字起こしの完了をハンドルします。
        """
        self.transcription_text = transcription
        self.transcription_display.setPlainText(self.transcription_text)
        self.save_button.setEnabled(True)
        logging.debug("Transcription completed successfully.")
        # 各チャンクごとのポップアップは削除

    def on_transcription_finished(self):
        """
        文字起こしの終了をハンドルします。
        """
        self.progress_bar.setValue(100)
        self.progress_bar.setFormat("文字起こし完了")
        self.timer.stop()
        self.progress_bar.hide()
        self.transcribe_button.setEnabled(True)
        self.select_button.setEnabled(True)
        logging.debug("Transcription thread finished and UI updated.")
        QMessageBox.information(self, "文字起こし完了", "全ての文字起こしが完了しました。")

    def on_error(self, error_message):
        """
        文字起こし中にエラーが発生した場合をハンドルします。
        """
        QMessageBox.critical(self, "文字起こしエラー", f"文字起こし中にエラーが発生しました:\n{error_message}")
        logging.error(f"Transcription error: {error_message}")
        self.transcribe_button.setEnabled(True)
        self.select_button.setEnabled(True)
        self.progress_bar.hide()
        self.timer.stop()

    def save_transcription(self):
        """
        文字起こしテキストをファイルに保存します。
        """
        if not self.transcription_text:
            QMessageBox.warning(self, "文字起こしなし", "保存する文字起こしがありません。")
            return

        try:
            # 文字起こしファイル名を自動で設定
            base_name = os.path.splitext(os.path.basename(self.audio_file))[0]
            default_save_path = os.path.join(os.path.dirname(self.audio_file), f"{base_name}.txt")

            # デフォルトファイル名で保存ダイアログを開く
            options = QFileDialog.Options()
            save_path, _ = QFileDialog.getSaveFileName(
                self,
                "文字起こしを保存",
                default_save_path,
                "テキストファイル (*.txt)",
                options=options
            )
            if save_path:
                with open(save_path, 'w', encoding='utf-8') as f:
                    f.write(self.transcription_text)
                logging.debug(f"Transcription saved to: {save_path}")
                QMessageBox.information(self, "保存完了", f"文字起こしが保存されました:\n{save_path}")
        except Exception as e:
            logging.exception("Failed to save transcription.")
            QMessageBox.critical(self, "保存エラー", f"文字起こしの保存に失敗しました: {e}")


def main():
    app = QApplication(sys.argv)
    window = SpeechRecognizerGUI()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
